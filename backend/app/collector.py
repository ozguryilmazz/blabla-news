"""Kaynaklardan (şimdilik RSS) haber çekme ve metin ayıklama."""

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx
import trafilatura

from .config import get_settings

# Birçok haber sitesi bot gibi görünen istekleri 403 ile reddediyor; sıradan bir tarayıcı gibi istek atılır
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.9, text/html;q=0.8, */*;q=0.7",
    "Accept-Language": "el,he;q=0.9,en;q=0.8,tr;q=0.7",
}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class FeedEntry:
    url: str
    title: str
    summary: str
    published_at: datetime | None


def clean_html(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", unescape(_TAG_RE.sub(" ", text))).strip()


def make_excerpt(text: str, limit: int = 280) -> str:
    text = _WS_RE.sub(" ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def parse_feed(raw: bytes | str) -> list[FeedEntry]:
    parsed = feedparser.parse(raw)
    entries = []
    for e in parsed.entries:
        url = e.get("link")
        title = clean_html(e.get("title"))
        if not url or not title:
            continue
        published = None
        stamp = e.get("published_parsed") or e.get("updated_parsed")
        if stamp:
            published = datetime.fromtimestamp(calendar.timegm(stamp), tz=timezone.utc)
        entries.append(FeedEntry(url=url.strip(), title=title, summary=clean_html(e.get("summary")), published_at=published))
    return entries


class HttpFetcher:
    def __init__(self):
        s = get_settings()
        self.client = httpx.Client(
            timeout=s.request_timeout_seconds,
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        )

    def fetch_feed(self, url: str) -> list[FeedEntry]:
        response = self.client.get(url)
        response.raise_for_status()
        entries = parse_feed(response.content)
        if not entries:
            raise ValueError("Beslemede haber bulunamadı")
        return entries

    def fetch_article_text(self, url: str) -> str | None:
        try:
            response = self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        return trafilatura.extract(response.text, include_comments=False, include_tables=False)
