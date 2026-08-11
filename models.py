"""Modelos de banco de dados do Livelo Points Dashboard."""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class Partner(db.Model):
    """Um parceiro Livelo (loja/marca que oferece pontos)."""

    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    code = db.Column(db.String(20), index=True)  # código curto usado pela Livelo (ex: MCL)
    name = db.Column(db.String(160), nullable=False, index=True)
    partner_url = db.Column(db.String(500))
    currency = db.Column(db.String(4), default="R$")  # R$ ou U$

    # Estado atual (última leitura), para consultas rápidas sem JOIN
    current_points = db.Column(db.Float)              # pontos padrão vigentes
    current_points_is_up_to = db.Column(db.Boolean, default=False)  # "Até X pontos"
    current_points_previous = db.Column(db.Float)      # "Eram X pontos" (se houver)
    current_points_clube = db.Column(db.Float)          # pontuação Clube Livelo, se houver
    current_points_clube_previous = db.Column(db.Float)
    is_promo = db.Column(db.Boolean, default=False, index=True)
    is_new_partner = db.Column(db.Boolean, default=False)  # selo "Nova"

    first_seen_at = db.Column(db.DateTime, default=utcnow)
    last_seen_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    last_checked_at = db.Column(db.DateTime, default=utcnow)

    history = db.relationship(
        "PointsHistory",
        backref="partner",
        lazy="dynamic",
        order_by="PointsHistory.captured_at",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "code": self.code,
            "name": self.name,
            "partner_url": self.partner_url,
            "currency": self.currency,
            "current_points": self.current_points,
            "current_points_is_up_to": self.current_points_is_up_to,
            "current_points_previous": self.current_points_previous,
            "current_points_clube": self.current_points_clube,
            "current_points_clube_previous": self.current_points_clube_previous,
            "is_promo": self.is_promo,
            "is_new_partner": self.is_new_partner,
            "variation_pct": self.variation_pct,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
        }

    @property
    def variation_pct(self):
        """% de variação em relação ao valor anterior ('Eram X pontos'), quando disponível."""
        if self.current_points_previous and self.current_points_previous > 0 and self.current_points:
            return round(
                ((self.current_points - self.current_points_previous) / self.current_points_previous) * 100,
                1,
            )
        return None


class PointsHistory(db.Model):
    """Um snapshot histórico da pontuação de um parceiro em um dado momento."""

    __tablename__ = "points_history"

    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("partners.id"), nullable=False, index=True)
    captured_at = db.Column(db.DateTime, default=utcnow, index=True)

    points = db.Column(db.Float, nullable=False)          # pontos padrão nesse snapshot
    points_is_up_to = db.Column(db.Boolean, default=False)
    points_previous = db.Column(db.Float)                   # "Eram X" nesse snapshot
    points_clube = db.Column(db.Float)
    points_clube_previous = db.Column(db.Float)
    is_promo = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "captured_at": self.captured_at.isoformat(),
            "points": self.points,
            "points_is_up_to": self.points_is_up_to,
            "points_clube": self.points_clube,
            "is_promo": self.is_promo,
        }


class ScrapeLog(db.Model):
    """Registro de cada execução do scraper, para diagnóstico."""

    __tablename__ = "scrape_logs"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=utcnow)
    finished_at = db.Column(db.DateTime)
    partners_found = db.Column(db.Integer, default=0)
    partners_new = db.Column(db.Integer, default=0)
    partners_changed = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="running")  # running | success | error
    error_message = db.Column(db.Text)
