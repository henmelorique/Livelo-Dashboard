"""Grava o resultado do scraper no banco (parceiros + histórico)."""
from __future__ import annotations

import logging

from models import Partner, PointsHistory, ScrapeLog, db, utcnow
from scraper import ScrapedPartner, scrape_partners

logger = logging.getLogger(__name__)


def _values_changed(partner: Partner, sp: ScrapedPartner) -> bool:
    return (
        partner.current_points != sp.points
        or partner.current_points_is_up_to != sp.points_is_up_to
        or partner.current_points_clube != sp.points_clube
        or partner.is_promo != sp.is_promo
    )


def ingest_once(app=None) -> ScrapeLog:
    """Executa o scraper uma vez e persiste os resultados. Retorna o ScrapeLog criado."""
    log = ScrapeLog(status="running")
    db.session.add(log)
    db.session.commit()

    try:
        scraped = scrape_partners()
        new_count = 0
        changed_count = 0
        now = utcnow()

        existing = {p.slug: p for p in Partner.query.all()}

        for sp in scraped:
            partner = existing.get(sp.slug)
            is_new = partner is None
            if is_new:
                partner = Partner(slug=sp.slug, first_seen_at=now)
                db.session.add(partner)
                existing[sp.slug] = partner
                new_count += 1

            changed = is_new or _values_changed(partner, sp)

            partner.code = sp.code
            partner.name = sp.name
            partner.partner_url = sp.partner_url
            partner.currency = sp.currency
            partner.current_points = sp.points
            partner.current_points_is_up_to = sp.points_is_up_to
            partner.current_points_previous = sp.points_previous
            partner.current_points_clube = sp.points_clube
            partner.current_points_clube_previous = sp.points_clube_previous
            partner.is_promo = sp.is_promo
            partner.is_new_partner = sp.is_new
            partner.last_seen_at = now
            partner.last_checked_at = now

            if changed:
                changed_count += 1

            # Sempre grava um snapshot no histórico (1x/dia é pouco volume de dados,
            # e permite reconstruir a série temporal completa, inclusive dias "sem mudança").
            db.session.add(
                PointsHistory(
                    partner=partner,
                    captured_at=now,
                    points=sp.points,
                    points_is_up_to=sp.points_is_up_to,
                    points_previous=sp.points_previous,
                    points_clube=sp.points_clube,
                    points_clube_previous=sp.points_clube_previous,
                    is_promo=sp.is_promo,
                )
            )

        log.finished_at = utcnow()
        log.partners_found = len(scraped)
        log.partners_new = new_count
        log.partners_changed = changed_count
        log.status = "success"
        db.session.commit()
        logger.info(
            "Ingest OK: %d encontrados, %d novos, %d alterados",
            len(scraped), new_count, changed_count,
        )
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        log.finished_at = utcnow()
        log.status = "error"
        log.error_message = str(exc)
        db.session.add(log)
        db.session.commit()
        logger.exception("Falha no ingest")

    return log
