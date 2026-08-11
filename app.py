"""
Livelo Points Dashboard
========================
Dashboard em Flask que acompanha a pontuação dos parceiros Livelo,
sinaliza promoções e mantém um histórico consultável por período.

Dois modos de operação (ver config.py):
- LIVELO_MODE=full (padrão): o próprio app faz o scraping e roda o
  agendador diário. Use assim na sua máquina local.
- LIVELO_MODE=readonly: o app nunca acessa livelo.com.br; ele sincroniza
  a partir de um snapshot JSON publicado no GitHub (gerado pelo GitHub
  Actions). Use assim em produção (ex.: PythonAnywhere free).

Rodar localmente:
    python app.py
Depois abra http://127.0.0.1:5000
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request

import config
from ingest import ingest_once
from models import Partner, PointsHistory, ScrapeLog, db
from remote_sync import sync_from_github

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def create_app(start_scheduler: bool = True) -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{config.DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False

    db.init_app(app)

    with app.app_context():
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        db.create_all()

    register_routes(app)

    if start_scheduler:
        if config.MODE == "readonly":
            register_readonly_sync(app)
        else:
            register_scheduler(app)

    return app


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

def register_routes(app: Flask) -> None:

    @app.route("/")
    def dashboard():
        return render_template("index.html")

    @app.route("/parceiro/<slug>")
    def partner_page(slug):
        partner = Partner.query.filter_by(slug=slug).first_or_404()
        return render_template("partner_history.html", partner=partner)

    # ---- API: lista de parceiros (tabela do dashboard) --------------------
    @app.route("/api/partners")
    def api_partners():
        sort = request.args.get("sort", "name")  # name | points | variation | updated
        order = request.args.get("order", "asc")
        promo_only = request.args.get("promo_only", "false").lower() == "true"
        search = request.args.get("q", "").strip()

        query = Partner.query
        if promo_only:
            query = query.filter(Partner.is_promo.is_(True))
        if search:
            query = query.filter(Partner.name.ilike(f"%{search}%"))

        partners = query.all()

        sort_key = {
            "name": lambda p: (p.name or "").lower(),
            "points": lambda p: p.current_points or 0,
            "variation": lambda p: p.variation_pct if p.variation_pct is not None else -9999,
            "updated": lambda p: p.last_checked_at or datetime.min,
        }.get(sort, lambda p: (p.name or "").lower())

        partners.sort(key=sort_key, reverse=(order == "desc"))

        last_log = ScrapeLog.query.filter_by(status="success").order_by(ScrapeLog.finished_at.desc()).first()

        return jsonify(
            {
                "partners": [p.to_dict() for p in partners],
                "count": len(partners),
                "promo_count": sum(1 for p in partners if p.is_promo),
                "last_updated": last_log.finished_at.isoformat() if last_log else None,
                "mode": config.MODE,
            }
        )

    # ---- API: histórico de um parceiro (gráfico de linhas) -----------------
    @app.route("/api/partner/<slug>/history")
    def api_partner_history(slug):
        partner = Partner.query.filter_by(slug=slug).first_or_404()

        days = request.args.get("days", type=int)
        start_param = request.args.get("start")
        end_param = request.args.get("end")

        query = PointsHistory.query.filter_by(partner_id=partner.id)

        if start_param:
            start_dt = datetime.fromisoformat(start_param)
            query = query.filter(PointsHistory.captured_at >= start_dt)
        elif days:
            start_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            query = query.filter(PointsHistory.captured_at >= start_dt)

        if end_param:
            end_dt = datetime.fromisoformat(end_param)
            query = query.filter(PointsHistory.captured_at <= end_dt)

        history = query.order_by(PointsHistory.captured_at.asc()).all()

        return jsonify(
            {
                "partner": partner.to_dict(),
                "history": [h.to_dict() for h in history],
            }
        )

    # ---- API: dispara uma atualização manual -------------------------------
    # Modo "full": faz o scraping direto na Livelo.
    # Modo "readonly": sincroniza a partir do snapshot publicado no GitHub
    # (não faz nenhuma requisição para livelo.com.br).
    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        if config.MODE == "readonly":
            try:
                stats = sync_from_github()
                return jsonify({"status": "success", "mode": "readonly", **stats})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha ao sincronizar com o GitHub")
                return jsonify({"status": "error", "mode": "readonly", "error": str(exc)}), 500

        log = ingest_once()
        return jsonify(
            {
                "status": log.status,
                "mode": "full",
                "partners_found": log.partners_found,
                "partners_new": log.partners_new,
                "partners_changed": log.partners_changed,
                "error": log.error_message,
            }
        ), (200 if log.status == "success" else 500)

    @app.route("/api/status")
    def api_status():
        last_log = ScrapeLog.query.order_by(ScrapeLog.started_at.desc()).first()
        total_partners = Partner.query.count()
        return jsonify(
            {
                "mode": config.MODE,
                "total_partners": total_partners,
                "last_scrape": {
                    "status": last_log.status,
                    "started_at": last_log.started_at.isoformat(),
                    "finished_at": last_log.finished_at.isoformat() if last_log.finished_at else None,
                    "partners_found": last_log.partners_found,
                    "error": last_log.error_message,
                }
                if last_log
                else None,
            }
        )


# ---------------------------------------------------------------------------
# Modo "full": agendador local (1x por dia) faz o scraping ele mesmo
# ---------------------------------------------------------------------------

def register_scheduler(app: Flask) -> None:
    scheduler = BackgroundScheduler(daemon=True)

    def job():
        with app.app_context():
            logger.info("Executando coleta agendada diária...")
            ingest_once()

    scheduler.add_job(job, "cron", hour=config.SCRAPE_HOUR, minute=0, id="daily_scrape")
    scheduler.start()

    # Na primeira vez que o app roda (banco vazio), popula os dados imediatamente
    # em vez de esperar até o próximo horário agendado.
    with app.app_context():
        if Partner.query.count() == 0:
            logger.info("Banco vazio: rodando a primeira coleta agora em background...")
            threading.Thread(target=job, daemon=True).start()


# ---------------------------------------------------------------------------
# Modo "readonly": sincroniza a partir do GitHub ao iniciar (sem scraping)
# ---------------------------------------------------------------------------

def register_readonly_sync(app: Flask) -> None:
    def job():
        with app.app_context():
            try:
                logger.info("Sincronizando snapshot inicial a partir do GitHub...")
                sync_from_github()
            except Exception:
                logger.exception("Falha ao sincronizar dados do GitHub na inicialização")

    threading.Thread(target=job, daemon=True).start()


# A criação do app no nível do módulo é necessária para o WSGI (PythonAnywhere
# faz `from app import app as application`). Mas scripts standalone (como
# scripts/run_scrape_and_export.py) também importam este arquivo, e não
# devem disparar o agendador nem a sincronização automática de novo — eles
# criam sua própria instância controlada via create_app(start_scheduler=False).
# LIVELO_SKIP_AUTOSTART evita esse efeito colateral duplo.
if os.environ.get("LIVELO_SKIP_AUTOSTART") == "1":
    app = None
else:
    app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
