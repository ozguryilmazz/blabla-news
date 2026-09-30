import threading

from sqlalchemy import select

from app import db, pipeline
from app.models import ScanRun, Source
from app.pipeline import close_interrupted_runs, run_scan
from app.progress import progress
from tests.conftest import FakeAI, FakeFetcher, entry


def _only(session, url):
    for src in session.scalars(select(Source)):
        src.active = src.url == url
    session.commit()


def test_progress_reports_phases_and_events(session):
    tov = "https://www.timesofisrael.com/feed/"
    _only(session, tov)
    fetcher = FakeFetcher(feeds={tov: [entry("u1", "Erdogan warns"), entry("u2", "Weather")]}, texts={"u1": "Erdogan"})
    run_scan(db.session_factory, fetcher, FakeAI())
    snap = progress.snapshot()
    assert not snap["running"] and snap["phase_index"] == 2 and snap["done"] == snap["total"] == 1
    texts = [e["text"] for e in snap["events"]]
    assert "Times of Israel: 2 yeni haber, 1 Türkiye adayı" in texts
    assert any(t.startswith("Yayınlandı:") for t in texts)
    assert texts[0] == "Tarama bitti"  # en yeni en üstte


def test_new_scan_cancels_running_one(session):
    tov = "https://www.timesofisrael.com/feed/"
    _only(session, tov)
    started, release = threading.Event(), threading.Event()

    class SlowFetcher(FakeFetcher):
        def fetch_article(self, url):
            started.set()
            release.wait(5)
            return super().fetch_article(url)

    slow = SlowFetcher(feeds={tov: [entry("a", "Erdogan 1"), entry("b", "Erdogan 2")]})
    first = {}
    t = threading.Thread(target=lambda: first.setdefault("run", run_scan(db.session_factory, slow, FakeAI())))
    t.start()
    assert started.wait(5)
    assert pipeline.cancel_running_scan()
    release.set()
    second = run_scan(db.session_factory, FakeFetcher(), FakeAI(), wait=5)
    t.join(5)
    assert first["run"].note == "İptal edildi: yeni tarama başlatıldı"
    assert second is not None and second.note is None
    assert not pipeline.cancel_running_scan()


def test_interrupted_runs_are_closed(session):
    session.add(ScanRun(trigger="manual"))
    session.commit()
    close_interrupted_runs(session)
    run = session.scalar(select(ScanRun))
    assert run.finished_at is not None and "Yarıda kaldı" in run.note
