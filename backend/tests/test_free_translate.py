import json

import httpx
import pytest
from sqlalchemy import select

from app import db
from app.ai import AIError, AIFatalError, ClaudeAI, active_translator_name, build_translator
from app.config import get_settings
from app.free_translate import (
    FreeTranslator,
    GoogleProvider,
    MyMemoryProvider,
    _pieces,
    default_providers,
    guess_category,
    lead_paragraphs,
)
from app.models import Article, Source, UsageLog
from app.pipeline import run_scan
from tests.conftest import FakeFetcher, entry

CATS = {"kibris": "Kıbrıs", "savunma-guvenlik": "Savunma", "siyaset-diplomasi": "Siyaset", "diger": "Diğer"}


def fake_services(seen, google_status=200, mymemory=None):
    """Google ve MyMemory'yi taklit eder; her isteği (servis, parametreler) olarak kaydeder."""

    def handler(request: httpx.Request):
        params = dict(request.url.params)
        if request.url.host == "translate.googleapis.com":
            seen.append(("google", params))
            q = params["q"]
            return httpx.Response(google_status, text=json.dumps([[["TR:" + q, q, None, None]], None, "el"]))
        if request.url.host == "api.mymemory.translated.net":
            seen.append(("mymemory", params))
            body = mymemory or {"responseData": {"translatedText": "MM:" + params["q"]}, "responseStatus": 200}
            return httpx.Response(200, json=body)
        if request.url.path == "/translate":
            body = json.loads(request.content)
            seen.append(("libre", body))
            return httpx.Response(200, json={"translatedText": "LT:" + body["q"]})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def translator(seen, **kw):
    providers = kw.pop("providers", None) or [GoogleProvider(), MyMemoryProvider("")]
    return FreeTranslator(client=fake_services(seen, **kw), providers=providers, delay=0)


def test_translate_uses_google_get_with_source_language():
    seen = []
    assert translator(seen).translate("Γεια σου", "el") == "TR:Γεια σου"
    name, params = seen[0]
    assert name == "google" and params["tl"] == "tr" and params["sl"] == "el" and params["client"] == "gtx"


def test_long_text_is_split_into_small_requests_without_losing_text():
    seen = []
    paragraph = " ".join(f"Πρόταση {i} για την Τουρκία." for i in range(80))
    out = translator(seen).translate(paragraph + "\nΔεύτερη παράγραφος.", "el")
    google_qs = [p["q"] for n, p in seen if n == "google"]
    assert len(google_qs) > 1 and all(len(q) <= GoogleProvider.max_chars for q in google_qs)
    assert " ".join(google_qs[:-1]) == paragraph  # hiçbir cümle kaybolmaz
    assert out.split("\n")[1] == "TR:Δεύτερη παράγραφος."


def test_pieces_cut_by_bytes_and_long_words():
    fits = MyMemoryProvider("").fits
    pieces = _pieces("α" * 700 + " βήτα. Γάμμα", fits)
    assert all(fits(p) for p in pieces) and "".join(pieces).replace(" ", "") == "α" * 700 + "βήτα.Γάμμα"


def test_google_rate_limit_falls_back_to_mymemory_and_is_skipped_afterwards():
    seen = []
    tr = translator(seen, google_status=429)
    assert tr.translate("Γεια", "el") == "MM:Γεια"
    assert tr.translate("Κύπρος", "el") == "MM:Κύπρος"
    assert [n for n, _ in seen] == ["google", "mymemory", "mymemory"]
    assert seen[1][1]["langpair"] == "el|tr"


def test_mymemory_email_is_sent():
    seen = []
    tr = translator(seen, google_status=429, providers=[GoogleProvider(), MyMemoryProvider("a@b.c")])
    tr.translate("x", "he")
    assert seen[1][1]["de"] == "a@b.c" and seen[1][1]["langpair"] == "he|tr"


def test_all_services_limited_is_fatal():
    quota = {"responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY"}, "responseStatus": 429}
    with pytest.raises(AIFatalError):
        translator([], google_status=429, mymemory=quota).translate("x", "el")


def test_other_errors_are_not_fatal():
    broken = {"responseData": {"translatedText": ""}, "responseStatus": "403", "responseDetails": "bad langpair"}
    tr = translator([], google_status=500, mymemory={**broken, "responseStatus": 500})
    with pytest.raises(AIError) as exc:
        tr.translate("x", "el")
    assert not isinstance(exc.value, AIFatalError)


def test_libretranslate_is_first_when_configured(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "libretranslate_url", "http://libretranslate:5000/")
    providers = default_providers()
    assert [p.name for p in providers] == ["libretranslate", "google", "mymemory"]
    seen = []
    assert translator(seen, providers=providers).translate("שלום", "he") == "LT:שלום"
    assert seen == [("libre", {"q": "שלום", "source": "he", "target": "tr", "format": "text"})]
    monkeypatch.setattr(s, "libretranslate_url", "")
    assert [p.name for p in default_providers()] == ["google", "mymemory"]


def test_relevance_rules():
    tr = translator([])
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
    tr = translator([])
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
    run = run_scan(db.session_factory, fetcher, translator([]))
    assert run.published == 1
    a = session.scalar(select(Article).where(Article.url == "u1"))
    assert a.status == "published" and a.translator == "free" and a.title_tr.startswith("TR:")
    assert session.scalar(select(UsageLog.id)) is None


def test_mentions_only_at_the_end_are_not_relevant():
    tr = translator([])
    body = "\n".join(["Βάφτιση στη θάλασσα, μια όμορφη τελετή." * 5] * 15)
    tail = "\nΔιαβάστε επίσης: Τουρκία απειλεί, Ερντογάν μιλά, Άγκυρα απαντά"
    assert not tr.check_relevance("Βάφτιση", body + tail, "el", CATS).relevant
    assert tr.check_relevance("Βάφτιση", "Η Τουρκία αντέδρασε.\n" + body + tail, "el", CATS).relevant


def test_old_irrelevant_free_articles_are_unpublished(session):
    tov = "https://www.timesofisrael.com/feed/"
    src = session.scalar(select(Source).where(Source.url == tov))
    for s in session.scalars(select(Source)):
        s.active = False
    good = Article(source_id=src.id, url="g", title_orig="Erdogan speaks", content_orig="x", status="published", translator="free")
    bad = Article(source_id=src.id, url="b", title_orig="Football", content_orig="Match report. " * 200 + "Turkey Turkey", status="published", translator="free")
    claude = Article(source_id=src.id, url="c", title_orig="Football", content_orig="Match", status="published", translator="claude")
    session.add_all([good, bad, claude])
    session.commit()
    run_scan(db.session_factory, FakeFetcher(), translator([]))
    session.expire_all()
    assert {a.url: a.status for a in session.scalars(select(Article))} == {"g": "published", "b": "irrelevant", "c": "published"}
