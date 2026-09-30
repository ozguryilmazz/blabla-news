from sqlalchemy import select

from app import db
from app.collector import page_image, parse_feed
from app.keywords import highlight_terms
from app.models import Article, Source
from app.pipeline import run_scan
from tests.conftest import FakeAI, FakeFetcher, entry
from tests.test_api import client  # noqa: F401  (fikstür)

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
<item><title>A</title><link>https://site.gr/a</link><media:content url="https://img.gr/a.jpg" medium="image"/></item>
<item><title>B</title><link>https://site.gr/b</link><enclosure url="https://img.gr/b.jpg" type="image/jpeg" length="1"/></item>
<item><title>C</title><link>https://site.gr/c</link><description>&lt;img src="/c.png"&gt; metin</description></item>
<item><title>D</title><link>https://site.gr/d</link><description>resimsiz</description></item>
</channel></rss>"""


def test_feed_images():
    images = [e.image_url for e in parse_feed(RSS)]
    assert images == ["https://img.gr/a.jpg", "https://img.gr/b.jpg", "https://site.gr/c.png", None]


def test_page_og_image():
    assert page_image('<meta property="og:image" content="https://x/y.jpg">') == "https://x/y.jpg"
    assert page_image('<meta content="https://x/z.jpg" name="twitter:image">') == "https://x/z.jpg"
    assert page_image("<p>yok</p>") is None


def _only(session, url):
    for src in session.scalars(select(Source)):
        src.active = src.url == url
    session.commit()


def test_image_saved_and_backfilled(session):
    tov = "https://www.timesofisrael.com/feed/"
    _only(session, tov)
    fetcher = FakeFetcher(
        feeds={tov: [entry("u1", "Erdogan warns", image_url="https://img/1.jpg"), entry("u2", "Turkey and Erdogan")]},
        texts={"u1": "Erdogan said", "u2": "Turkey..."},
        images={"u2": "https://img/og2.jpg"},
    )
    run_scan(db.session_factory, fetcher, FakeAI())
    got = {a.url: a.image_url for a in session.scalars(select(Article))}
    assert got == {"u1": "https://img/1.jpg", "u2": "https://img/og2.jpg"}

    # Görsel özelliğinden önce kaydedilmiş haber: bir sonraki taramada tamamlanır, sonra tekrar aranmaz
    a = session.scalar(select(Article).where(Article.url == "u2"))
    a.image_url = None
    session.commit()
    fetcher.images = {}
    fetcher.article_fetches.clear()
    run_scan(db.session_factory, fetcher, FakeAI())
    session.expire_all()
    assert session.scalar(select(Article.image_url).where(Article.url == "u2")) == ""
    run_scan(db.session_factory, fetcher, FakeAI())
    assert fetcher.article_fetches == ["u2"]


def test_api_exposes_image_and_terms(client, session):
    tov = "https://www.timesofisrael.com/feed/"
    _only(session, tov)
    run_scan(db.session_factory, FakeFetcher(feeds={tov: [entry("u1", "Erdogan warns")]}, texts={"u1": "Erdogan"}), FakeAI())
    item = client.get("/api/articles").json()["items"][0]
    assert item["image_url"] is None  # "" dışarıya boş olarak verilir
    terms = client.get("/api/highlight-terms").json()
    assert "turk" in terms and "τουρκ" in terms and "טורקי" in terms
    assert terms == highlight_terms()
