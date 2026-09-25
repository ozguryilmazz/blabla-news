import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from .ai import ClaudeAI
from .collector import HttpFetcher
from .config import get_settings
from .db import session_factory
from .pipeline import is_paused, run_scan

log = logging.getLogger(__name__)


def _scan(trigger: str) -> None:
    run = run_scan(session_factory, HttpFetcher(), ClaudeAI(), trigger=trigger)
    if run is None:
        log.info("Tarama zaten sürüyor, atlandı (%s)", trigger)


def scheduled_scan() -> None:
    session = session_factory()
    try:
        if is_paused(session):
            log.info("Otomatik tarama durdurulmuş, atlandı")
            return
    finally:
        session.close()
    _scan("schedule")


def start_manual_scan() -> None:
    threading.Thread(target=_scan, args=("manual",), daemon=True).start()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_scan,
        "interval",
        minutes=get_settings().scan_interval_minutes,
        id="scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
