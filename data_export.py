"""
Exporta e importa um snapshot completo do banco (parceiros + histórico) em
JSON. É a "ponte" entre o GitHub Actions (que faz a coleta de verdade,
com acesso livre à internet) e o app em modo "readonly" (que só lê esse
JSON de dentro de um ambiente com internet restrita, como a PythonAnywhere
free).

- `export_to_json`: usado pelo GitHub Actions depois de coletar, para
  publicar o snapshot no repositório.
- `import_from_dict`: usado tanto pelo GitHub Actions (para carregar o
  snapshot do dia anterior antes de coletar de novo, preservando o
  histórico) quanto pelo app em produção (para sincronizar a partir do
  JSON publicado no GitHub). É idempotente: rodar de novo com os mesmos
  dados não duplica histórico.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from models import Partner, PointsHistory, db, utcnow

logger = logging.getLogger(__name__)


def _parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s).replace(tzinfo=None)


def export_to_json(path: str | None = None) -> dict:
    """Serializa todos os parceiros + histórico completo. Se `path` for
    passado, também grava o arquivo."""
    data = {"exported_at": utcnow().isoformat(), "partners": []}

    for p in Partner.query.all():
        entry = p.to_dict()
        entry["first_seen_at"] = p.first_seen_at.isoformat() if p.first_seen_at else None
        entry["history"] = [
            h.to_dict() for h in p.history.order_by(PointsHistory.captured_at.asc()).all()
        ]
        data["partners"].append(entry)

    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    return data


def import_from_dict(data: dict) -> dict:
    """Importa um snapshot no formato de `export_to_json`. Idempotente:
    não duplica parceiros (upsert por slug) nem histórico (dedup por
    partner + captured_at)."""
    stats = {"partners_upserted": 0, "history_inserted": 0}
    existing = {p.slug: p for p in Partner.query.all()}

    for pdata in data.get("partners", []):
        slug = pdata["slug"]
        partner = existing.get(slug)
        is_new = partner is None
        if is_new:
            partner = Partner(slug=slug)
            db.session.add(partner)
            existing[slug] = partner

        partner.code = pdata.get("code")
        partner.name = pdata.get("name")
        partner.partner_url = pdata.get("partner_url")
        partner.currency = pdata.get("currency", "R$")
        partner.current_points = pdata.get("current_points")
        partner.current_points_is_up_to = pdata.get("current_points_is_up_to", False)
        partner.current_points_previous = pdata.get("current_points_previous")
        partner.current_points_clube = pdata.get("current_points_clube")
        partner.current_points_clube_previous = pdata.get("current_points_clube_previous")
        partner.is_promo = pdata.get("is_promo", False)
        partner.is_new_partner = pdata.get("is_new_partner", False)
        if pdata.get("last_checked_at"):
            partner.last_checked_at = _parse_dt(pdata["last_checked_at"])
        if is_new and pdata.get("first_seen_at"):
            partner.first_seen_at = _parse_dt(pdata["first_seen_at"])
        stats["partners_upserted"] += 1

        db.session.flush()  # garante partner.id disponível para o histórico

        already = {h.captured_at.isoformat() for h in partner.history}
        for h in pdata.get("history", []):
            ts_iso = h.get("captured_at")
            if not ts_iso or ts_iso in already:
                continue
            db.session.add(
                PointsHistory(
                    partner_id=partner.id,
                    captured_at=_parse_dt(ts_iso),
                    points=h.get("points"),
                    points_is_up_to=h.get("points_is_up_to", False),
                    points_clube=h.get("points_clube"),
                    is_promo=h.get("is_promo", False),
                )
            )
            already.add(ts_iso)
            stats["history_inserted"] += 1

    db.session.commit()
    logger.info("Import concluído: %s", stats)
    return stats
