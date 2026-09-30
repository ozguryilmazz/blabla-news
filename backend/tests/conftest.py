import os

os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["ADMIN_PASSWORD"] = "test-sifre"
os.environ["DATABASE_URL"] = "sqlite://"

from datetime import datetime, timezone

import pytest
from sqlalchemy.pool import StaticPool

from app import db
from app.ai import AIError, RelevanceResult, RewriteResult, Usage
from app.collector import ArticleContent, FeedEntry
from app.db import Base
from app.seed import seed


@pytest.fixture
def engine():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db._engine = eng
    db._SessionLocal = sessionmaker(bind=eng, expire_on_commit=False)
    Base.metadata.create_all(eng)
    session = db.session_factory()
    seed(session)
    session.close()
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session(engine):
    s = db.session_factory()
    yield s
    s.close()


class FakeFetcher:
    """Kaynak URL'si → haber listesi; makale URL'si → metin."""

    def __init__(self, feeds=None, texts=None, failing=(), images=None):
        self.feeds = feeds or {}
        self.texts = texts or {}
        self.images = images or {}
        self.failing = set(failing)
        self.article_fetches = []

    def fetch_feed(self, url):
        if url in self.failing:
            raise RuntimeError("bağlantı hatası")
        return self.feeds.get(url, [])

    def fetch_article(self, url):
        self.article_fetches.append(url)
        return ArticleContent(self.texts.get(url), self.images.get(url))


class FakeAI:
    def __init__(self, relevant=True, category="siyaset-diplomasi", fail=False):
        self.relevant = relevant
        self.category = category
        self.fail = fail
        self.relevance_calls = 0
        self.rewrite_calls = 0

    def check_relevance(self, title, text, language, categories):
        self.relevance_calls += 1
        usage = Usage("claude-haiku-4-5", "relevance", 1000, 100)
        if self.fail:
            raise AIError("hata", usage)
        return RelevanceResult(self.relevant, self.category, "test", usage)

    def rewrite(self, title, text, language, source_name):
        self.rewrite_calls += 1
        return RewriteResult(
            title_tr=f"TR: {title}",
            summary_tr="Habere göre Türkiye ile ilgili geniş bir özet.",
            key_points=["Birinci nokta", "İkinci nokta"],
            tags=["Türkiye", "Yunanistan"],
            usage=Usage("claude-sonnet-5", "rewrite", 3000, 800),
        )


def entry(url, title, summary="", image_url=None):
    return FeedEntry(url=url, title=title, summary=summary, published_at=datetime(2026, 9, 20, tzinfo=timezone.utc), image_url=image_url)
