from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(2))  # GR, IL
    language: Mapped[str] = mapped_column(String(5))  # el, he, en
    kind: Mapped[str] = mapped_column(String(20), default="rss")
    url: Mapped[str] = mapped_column(String(500), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    # Taramadan önce seçilebilir: kapalı kategorideki haberler çevrilmez/yayınlanmaz
    scan_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Article(Base):
    """Her görülen haber kaydedilir (tekrarı önlemek için); sitede yalnızca status=published görünür."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # pending: yapay zekâ bekliyor (ör. bütçe doldu) | irrelevant | skipped_category | published | failed
    status: Mapped[str] = mapped_column(String(20), index=True)

    title_orig: Mapped[str] = mapped_column(Text)
    # Tam orijinal metin yalnızca iç analiz içindir, herkese açık API'de dönmez
    content_orig: Mapped[str | None] = mapped_column(Text)
    excerpt_orig: Mapped[str | None] = mapped_column(Text)

    title_tr: Mapped[str | None] = mapped_column(Text)
    summary_tr: Mapped[str | None] = mapped_column(Text)
    key_points_tr: Mapped[str | None] = mapped_column(Text)  # satır satır
    tags: Mapped[str | None] = mapped_column(Text)  # virgülle ayrılmış

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)

    source: Mapped[Source] = relationship()
    category: Mapped[Category | None] = relationship()


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    model: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(20))  # relevance | rewrite
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(String(20))  # schedule | manual
    new_items: Mapped[int] = mapped_column(Integer, default=0)
    published: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
