from sqlalchemy import func, select

from app import db
from app.models import Article, Category, Source, UsageLog
from app.pipeline import run_scan
from tests.conftest import FakeAI, FakeFetcher, entry

TOV = "https://www.timesofisrael.com/feed/"


def only_source(session, url=TOV):
    for s in session.scalars(select(Source)):
        s.active = s.url == url
    session.commit()


def statuses(session):
    return {a.url: a.status for a in session.scalars(select(Article))}


def test_candidate_is_published_and_unrelated_is_skipped(session):
    only_source(session)
    fetcher = FakeFetcher(
        feeds={TOV: [entry("u1", "Erdogan warns Israel"), entry("u2", "Tel Aviv weather")]},
        texts={"u1": "Turkish president Erdogan said..."},
    )
    ai = FakeAI()
    run = run_scan(db.session_factory, fetcher, ai)

    assert run.new_items == 1 and run.published == 1
    assert statuses(session) == {"u1": "published", "u2": "irrelevant"}
    assert ai.relevance_calls == 1  # anahtar kelime elemesi ilgisiz haberi yapay zekâya göndermez
    article = session.scalar(select(Article).where(Article.url == "u1"))
    assert article.title_tr == "TR: Erdogan warns Israel"
    assert session.scalar(select(func.count(UsageLog.id))) == 2


def test_second_scan_does_not_reprocess(session):
    only_source(session)
    fetcher = FakeFetcher(feeds={TOV: [entry("u1", "Erdogan warns Israel")]})
    ai = FakeAI()
    run_scan(db.session_factory, fetcher, ai)
    run = run_scan(db.session_factory, fetcher, ai)
    assert run.new_items == 0
    assert ai.relevance_calls == 1


def test_disabled_category_is_not_rewritten(session):
    only_source(session)
    cat = session.scalar(select(Category).where(Category.slug == "savunma-guvenlik"))
    cat.scan_enabled = False
    session.commit()
    ai = FakeAI(category="savunma-guvenlik")
    run_scan(db.session_factory, FakeFetcher(feeds={TOV: [entry("u1", "Turkish drones")]}), ai)
    assert statuses(session) == {"u1": "skipped_category"}
    assert ai.rewrite_calls == 0


def test_ai_says_irrelevant(session):
    only_source(session)
    ai = FakeAI(relevant=False)
    run_scan(db.session_factory, FakeFetcher(feeds={TOV: [entry("u1", "Turkey recipe for Thanksgiving")]}), ai)
    assert statuses(session) == {"u1": "irrelevant"}
    assert ai.rewrite_calls == 0


def test_budget_exhausted_keeps_collecting_but_stops_ai(session):
    only_source(session)
    session.add(UsageLog(model="x", purpose="rewrite", input_tokens=0, output_tokens=0, cost_usd=1000.0))
    session.commit()
    ai = FakeAI()
    run = run_scan(db.session_factory, FakeFetcher(feeds={TOV: [entry("u1", "Erdogan speech")]}), ai)
    assert statuses(session) == {"u1": "pending"}
    assert ai.relevance_calls == 0
    assert "bütçe" in run.note


def test_ai_failure_marks_failed_and_logs_usage(session):
    only_source(session)
    run = run_scan(db.session_factory, FakeFetcher(feeds={TOV: [entry("u1", "Erdogan speech")]}), FakeAI(fail=True))
    assert statuses(session) == {"u1": "failed"}
    assert run.errors == 1
    assert session.scalar(select(func.count(UsageLog.id))) == 1


def test_broken_source_is_recorded_and_others_continue(session):
    other = "https://www.jpost.com/rss/rssfeedsfrontpage.aspx"
    for s in session.scalars(select(Source)):
        s.active = s.url in (TOV, other)
    session.commit()
    fetcher = FakeFetcher(feeds={other: [entry("u1", "Ankara talks")]}, failing={TOV})
    run = run_scan(db.session_factory, fetcher, FakeAI())
    assert run.errors == 1 and run.published == 1
    broken = session.scalar(select(Source).where(Source.url == TOV))
    session.refresh(broken)
    assert "bağlantı" in broken.last_error
