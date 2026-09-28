import json

import httpx
import pytest
from sqlalchemy import select

from app import db
from app.ai import AIFatalError, ClaudeAI, active_translator_name, build_translator
from app.config import get_settings
from app.free_translate import FreeTranslator, guess_category, lead_paragraphs
from app.models import Article, Source, UsageLog
from app.pipeline import run_scan
from tests.conftest import FakeFetcher, entry

CATS = {"kibris": "Kıbrıs", "savunma-guvenlik": "Savunma", "siyaset-diplomasi": "Siyaset", "diger": "Diğer"}


def google_client(seen, status=200):
    def handler(request: httpx.Request):
        q = dict(httpx.QueryParams(request.content.decode()))["q"]
        seen.append((dict(request.url.params), q))
        return httpx.Response(status, text=json.dumps([[["TR:" + q, q, None, None]], None, "el"]))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_translate_uses_google_free_endpoint():
    seen = []
    tr = FreeTranslator(client=google_client(seen))
    assert tr.translate("Γεια σου") == "TR:Γεια σου"
    params, _ = seen[0]
    assert params["tl"] == "tr" and params["client"] == "gtx"


def test_rate_limit_is_fatal():
    with pytest.raises(AIFatalError):
        FreeTranslator(client=google_client([], status=429)).translate("x")


def test_relevance_rules():
    tr = FreeTranslator(client=google_client([]))
    assert tr.check_relevance("Ερντογάν: νέες απειλές", "", "el", CATS).relevant
    assert tr.check_relevance("Weather", "Turkey and Erdogan talks...", "en", CATS).relevant
    assert not tr.check_relevance("Weather", "One mention of Istanbul flights.", "en", CATS).relevant


def test_category_guess():
    assert guess_category("Τουρκία και Κύπρος") == "kibris"
    assert guess_category("Turkish drones and the army") == "savunma-guvenlik"
    assert guess_category("ארדואן נפגש עם השגריר") == "siyaset-diplomasi"
    assert guess_category("Erdogan said") == "diger"


def test_only_lead_is_translated():
    text = "\n".join(f"Paragraf {i} " + "x" * 400 for i in range(10))
    lead = lead_paragraphs(text)
    assert lead.startswith("Paragraf 0") and "Paragraf 9" not in lead
    assert len(lead) <= 1600


def test_rewrite_tags_and_no_key_points():
    tr = FreeTranslator(client=google_client([]))
    r = tr.rewrite("Erdogan warns Athens", "Ankara said...", "en", "X")
    assert r.title_tr == "TR:Erdogan warns Athens"
    assert r.tags == ["Ankara", "Erdoğan"]
    assert r.key_points == [] and r.usage is None


def test_auto_selects_free_without_key_and_claude_with_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "translator", "auto")
    monkeypatch.setattr(s, "anthropic_api_key", "")
    assert active_translator_name() == "free"
    assert isinstance(build_translator(), FreeTranslator)
    monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test")
    assert active_translator_name() == "claude"
    assert isinstance(build_translator(), ClaudeAI)
    monkeypatch.setattr(s, "translator", "free")
    assert active_translator_name() == "free"


def test_pipeline_with_free_translator_publishes_without_cost(session):
    tov = "https://www.timesofisrael.com/feed/"
    for src in session.scalars(select(Source)):
        src.active = src.url == tov
    session.commit()
    fetcher = FakeFetcher(feeds={tov: [entry("u1", "Erdogan warns Israel")]}, texts={"u1": "Turkish president Erdogan said..."})
    run = run_scan(db.session_factory, fetcher, FreeTranslator(client=google_client([])))
    assert run.published == 1
    a = session.scalar(select(Article).where(Article.url == "u1"))
    assert a.status == "published" and a.translator == "free" and a.title_tr.startswith("TR:")
    assert session.scalar(select(UsageLog.id)) is None
