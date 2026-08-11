"""
Scraper da página "Todos os parceiros" da Livelo.

A Livelo publica a lista de parceiros em:
    https://www.livelo.com.br/juntar-pontos/todos-os-parceiros

Cada card de parceiro contém, dentro de um único <a>, um texto no formato:

    [Nova][Promoção]Logo {Nome} [Até] **{N} pontos** por {R$|U$} {divisor}
    [Eram {M} pontos]
    [Clube [Até] **{N2} pontos** por {R$|U$} {divisor2} [Eram {M2} pontos]]
    Ir para regras do parceiro

Este módulo faz o parsing desse texto com regex. Como o layout de sites
muda com o tempo, todo o parsing fica centralizado aqui: se a Livelo mudar
o HTML, normalmente só é preciso ajustar `PARTNER_LINK_RE`/`_parse_card_text`.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LIST_URL = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

HEADERS = {
    # Um user-agent de navegador comum evita bloqueios triviais de bot.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Link de um parceiro "normal": /juntar-pontos/parceiros/{slug}/{CODE}
PARTNER_HREF_RE = re.compile(r"/juntar-pontos/parceiros/([^/?#]+)/([A-Za-z0-9]+)/?$")

NUM_RE = r"[\d\.,]+"


def _to_float(raw: str) -> Optional[float]:
    """Converte '1.234,5' ou '4' (formato PT-BR) em float."""
    if raw is None:
        return None
    raw = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "parceiro"


# Regex do card. O nome do parceiro NÃO entra aqui: no HTML da Livelo o nome
# vive no atributo alt="Logo {Nome}" da imagem, não em texto visível — então
# é extraído à parte em `_parse_card` a partir da tag <img>. Este regex cuida
# só dos selos (Nova/Promoção) e dos números de pontuação.
CARD_RE = re.compile(
    r"^(?P<nova>Nova)?\s*"
    r"(?P<promo>Promoção)?\s*"
    r"(?P<upto1>Até\s*)?"
    r"(?P<points>" + NUM_RE + r")\s*pontos?\s*por\s*"
    r"(?P<currency>R\$|U\$)\s*(?P<divisor>" + NUM_RE + r")"
    r"(?:\s*Eram\s*(?P<previous>" + NUM_RE + r")\s*pontos?)?"
    r"(?:\s*Clube\s*(?P<upto2>Até\s*)?"
    r"(?P<points_clube>" + NUM_RE + r")\s*pontos?\s*por\s*(?:R\$|U\$)\s*" + NUM_RE +
    r"(?:\s*Eram\s*(?P<previous_clube>" + NUM_RE + r")\s*pontos?)?)?",
    re.IGNORECASE,
)

NAME_FROM_ALT_RE = re.compile(r"^\s*Logo\s+(.+?)\s*$", re.IGNORECASE)


@dataclass
class ScrapedPartner:
    slug: str
    code: Optional[str]
    name: str
    partner_url: str
    currency: str
    points: Optional[float]
    points_is_up_to: bool
    points_previous: Optional[float]
    points_clube: Optional[float]
    points_clube_previous: Optional[float]
    is_promo: bool
    is_new: bool
    raw_text: str = field(repr=False, default="")


def _extract_name(a_tag) -> Optional[str]:
    """Nome do parceiro: tenta alt='Logo {Nome}' da imagem, depois aria-label/title,
    e por fim qualquer texto visível informativo dentro do link."""
    img = a_tag.find("img")
    if img:
        for attr in ("alt", "title"):
            val = img.get(attr)
            if val:
                m = NAME_FROM_ALT_RE.match(val)
                if m:
                    return m.group(1).strip()
                if val.strip():
                    return val.strip()
    for attr in ("aria-label", "title"):
        val = a_tag.get(attr)
        if val and val.strip():
            return val.strip()
    return None


def _parse_card_text(text: str) -> Optional[dict]:
    text = re.sub(r"\s+", " ", text).strip()
    m = CARD_RE.search(text)
    if not m:
        return None
    gd = m.groupdict()
    return {
        "currency": gd["currency"],
        "points": _to_float(gd["points"]),
        "points_is_up_to": bool(gd["upto1"]),
        "points_previous": _to_float(gd["previous"]),
        "points_clube": _to_float(gd["points_clube"]),
        "points_clube_previous": _to_float(gd["previous_clube"]),
        # promoção também é inferida por haver um valor "Eram X" (preço antigo),
        # já que a Livelo às vezes omite o selo "Promoção" mas mostra a variação.
        "is_promo": bool(gd["promo"]) or gd["previous"] is not None,
        "is_new": bool(gd["nova"]),
    }


def fetch_partners_html(url: str = LIST_URL, timeout: int = 30) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_partners(html: str) -> list[ScrapedPartner]:
    soup = BeautifulSoup(html, "html.parser")
    partners: list[ScrapedPartner] = []
    seen_hrefs = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/juntar-pontos/parceiros/" not in href and "produto/" not in href:
            continue
        text = a.get_text(" ", strip=True)
        if "pontos" not in text.lower() and "ponto" not in text.lower():
            continue
        if href in seen_hrefs:
            continue

        parsed = _parse_card_text(text)
        if not parsed or parsed["points"] is None:
            continue

        match = PARTNER_HREF_RE.search(href)
        if match:
            slug, code = match.group(1), match.group(2)
        else:
            slug, code = None, None

        name = _extract_name(a)
        if not name:
            # último recurso: deriva um nome legível a partir do slug da URL
            name = (slug or "").replace("-", " ").title() or None
        if not name:
            continue

        if not slug:
            slug = slugify(name)

        seen_hrefs.add(href)
        full_url = href if href.startswith("http") else f"https://www.livelo.com.br{href}"

        partners.append(
            ScrapedPartner(
                slug=slug,
                code=code,
                name=name,
                partner_url=full_url,
                currency=parsed["currency"],
                points=parsed["points"],
                points_is_up_to=parsed["points_is_up_to"],
                points_previous=parsed["points_previous"],
                points_clube=parsed["points_clube"],
                points_clube_previous=parsed["points_clube_previous"],
                is_promo=parsed["is_promo"],
                is_new=parsed["is_new"],
                raw_text=text,
            )
        )

    return partners


def fetch_partners_html_playwright(url: str = LIST_URL, timeout: int = 45) -> str:
    """
    Fallback usando um navegador headless (Playwright).

    Só é necessário se `fetch_partners_html` (requests puro) retornar 0
    parceiros — o que indicaria que a Livelo passou a montar a lista via
    JavaScript no cliente. Requer `pip install playwright && playwright
    install chromium`.
    """
    from playwright.sync_api import sync_playwright  # import tardio: dependência opcional

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        # A lista costuma paginar via botão "carregar mais"; clica até esgotar.
        for _ in range(40):
            try:
                btn = page.get_by_text(re.compile("carregar mais", re.I))
                if btn.count() == 0:
                    break
                btn.first.click()
                page.wait_for_timeout(600)
            except Exception:
                break
        html = page.content()
        browser.close()
        return html


def scrape_partners(url: str = LIST_URL, use_browser_fallback: bool = True) -> list[ScrapedPartner]:
    """Função de alto nível: baixa a página e devolve a lista de parceiros parseados."""
    html = fetch_partners_html(url)
    partners = parse_partners(html)

    if not partners and use_browser_fallback:
        logger.warning(
            "Nenhum parceiro encontrado via requests puro; tentando fallback com navegador headless."
        )
        try:
            html = fetch_partners_html_playwright(url)
            partners = parse_partners(html)
        except ImportError:
            logger.error(
                "Playwright não está instalado. Rode: pip install playwright && "
                "playwright install chromium"
            )

    logger.info("Scrape concluído: %d parceiros encontrados", len(partners))
    return partners


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for p in scrape_partners():
        flag = "PROMO" if p.is_promo else "     "
        print(f"[{flag}] {p.name:35s} {p.points:>6.1f} pts/{p.currency} (código={p.code})")
