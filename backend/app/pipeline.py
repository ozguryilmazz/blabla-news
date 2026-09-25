"""Tarama akışı: kaynakları çek → anahtar kelime ön elemesi → yapay zekâ ilgi kontrolü →
kategori seçimi → Türkçe yeniden yazım → yayın."""

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import keywords
from .ai import AIError, Usage
from .budget import budget_exhausted
from .collector import make_excerpt
from .config import get_settings
from .models import AppSetting, Article, Category, ScanRun, Source, UsageLog

log = logging.getLogger(__name__)

_scan_lock = threading.Lock()

PAUSED_KEY = "scan_paused"


def is_paused(session: Session) -> bool:
    setting = session.get(AppSetting, PAUSED_KEY)
    return setting is not None and setting.value == "1"


def set_paused(session: Session, paused: bool) -> None:
    setting = session.get(AppSetting, PAUSED_KEY) or AppSetting(key=PAUSED_KEY, value="0")
    setting.value = "1" if paused else "0"
    session.merge(setting)
    session.commit()


def scan_running() -> bool:
    return _scan_lock.locked()


def _log_usage(session: Session, usage: Usage | None) -> None:
    if usage is None:
        return
    session.add(
        UsageLog(
            model=usage.model,
            purpose=usage.purpose,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=usage.cost_usd,
        )
    )


def collect(session: Session, fetcher, run: ScanRun) -> None:
    max_items = get_settings().max_items_per_source
    sources = session.scalars(select(Source).where(Source.active.is_(True))).all()
    for source in sources:
        source.last_checked_at = datetime.now(timezone.utc)
        try:
            entries = fetcher.fetch_feed(source.url)
        except Exception as exc:  # her kaynak bağımsız; biri bozuksa diğerleri devam eder
            source.last_error = str(exc)[:500]
            run.errors += 1
            session.commit()
            continue
        source.last_error = None

        for entry in entries[:max_items]:
            if session.scalar(select(Article.id).where(Article.url == entry.url)):
                continue
            text = fetcher.fetch_article_text(entry.url) or entry.summary
            article = Article(
                source_id=source.id,
                url=entry.url,
                published_at=entry.published_at or datetime.now(timezone.utc),
                title_orig=entry.title,
                excerpt_orig=make_excerpt(entry.summary or text or ""),
            )
            if keywords.is_candidate(entry.title, entry.summary, text):
                article.status = "pending"
                article.content_orig = text
                run.new_items += 1
            else:
                article.status = "irrelevant"  # yalnızca tekrar görmemek için saklanır
            session.add(article)
        session.commit()


def process_pending(session: Session, ai, run: ScanRun) -> None:
    categories = session.scalars(select(Category).order_by(Category.sort_order)).all()
    category_names = {c.slug: c.name for c in categories}
    by_slug = {c.slug: c for c in categories}

    pending = session.scalars(
        select(Article).where(Article.status == "pending").order_by(Article.fetched_at)
    ).all()
    for article in pending:
        if budget_exhausted(session):
            run.note = "Aylık yapay zekâ bütçesi doldu; bekleyen haberler gelecek ay işlenecek."
            break
        source = article.source
        try:
            relevance = ai.check_relevance(article.title_orig, article.content_orig or "", source.language, category_names)
            _log_usage(session, relevance.usage)
            category = by_slug.get(relevance.category) or by_slug.get("diger")
            article.category_id = category.id if category else None

            if not relevance.relevant:
                article.status = "irrelevant"
            elif category is not None and not category.scan_enabled:
                article.status = "skipped_category"
            else:
                rewrite = ai.rewrite(article.title_orig, article.content_orig or "", source.language, source.name)
                _log_usage(session, rewrite.usage)
                article.title_tr = rewrite.title_tr
                article.summary_tr = rewrite.summary_tr
                article.key_points_tr = "\n".join(rewrite.key_points)
                article.tags = ", ".join(rewrite.tags)
                article.status = "published"
                run.published += 1
        except AIError as exc:
            _log_usage(session, exc.usage)
            article.status = "failed"
            run.errors += 1
            log.warning("Yapay zekâ adımı başarısız (%s): %s", article.url, exc)
        session.commit()


def run_scan(session_factory, fetcher, ai, trigger: str = "manual") -> ScanRun | None:
    """Tek seferlik tarama. Başka bir tarama sürüyorsa None döner."""
    if not _scan_lock.acquire(blocking=False):
        return None
    session = session_factory()
    try:
        run = ScanRun(trigger=trigger)
        session.add(run)
        session.commit()
        try:
            collect(session, fetcher, run)
            process_pending(session, ai, run)
        except Exception as exc:
            log.exception("Tarama hatası")
            session.rollback()
            run.note = f"Tarama hatası: {exc}"[:500]
            run.errors += 1
        run.finished_at = datetime.now(timezone.utc)
        session.merge(run)
        session.commit()
        return run
    finally:
        session.close()
        _scan_lock.release()
