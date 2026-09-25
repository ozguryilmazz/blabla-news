from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import UsageLog

# USD / 1M token (giriş, çıkış)
PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES_USD_PER_MTOK.get(model, (5.0, 25.0))  # bilinmeyen modelde temkinli
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def spent_this_month_eur(session: Session, now: datetime | None = None) -> float:
    total_usd = session.scalar(
        select(func.coalesce(func.sum(UsageLog.cost_usd), 0.0)).where(
            UsageLog.created_at >= month_start(now)
        )
    )
    return float(total_usd) * get_settings().usd_to_eur


def budget_status(session: Session) -> dict:
    s = get_settings()
    spent = spent_this_month_eur(session)
    limit = s.ai_budget_eur
    ratio = spent / limit if limit else 1.0
    return {
        "monthly_budget_eur": s.monthly_budget_eur,
        "server_cost_eur": s.server_cost_eur,
        "ai_budget_eur": round(limit, 2),
        "ai_spent_eur": round(spent, 4),
        "ratio": round(ratio, 4),
        "warning": ratio >= s.budget_warning_ratio,
        "exhausted": ratio >= 1.0,
    }


def budget_exhausted(session: Session) -> bool:
    return spent_this_month_eur(session) >= get_settings().ai_budget_eur
