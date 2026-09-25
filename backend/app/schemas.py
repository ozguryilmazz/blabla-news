from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    scan_enabled: bool


class SourcePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    country: str
    language: str


class SourceAdmin(SourcePublic):
    url: str
    kind: str
    active: bool
    last_checked_at: datetime | None
    last_error: str | None


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(pattern="^(GR|IL)$")
    language: str = Field(pattern="^(el|he|en)$")
    url: str = Field(min_length=8, max_length=500)


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None


class CategoryUpdate(BaseModel):
    scan_enabled: bool | None = None
    name: str | None = None


class ArticleSummary(BaseModel):
    id: int
    url: str
    published_at: datetime | None
    title_orig: str
    title_tr: str | None
    excerpt_tr: str
    source: SourcePublic
    category: CategoryOut | None


class ArticleDetail(BaseModel):
    id: int
    url: str
    published_at: datetime | None
    title_orig: str
    excerpt_orig: str | None
    title_tr: str | None
    summary_tr: str | None
    key_points_tr: list[str]
    tags: list[str]
    source: SourcePublic
    category: CategoryOut | None


class ArticlePage(BaseModel):
    items: list[ArticleSummary]
    total: int
    page: int
    page_size: int


class ScanRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    new_items: int
    published: int
    errors: int
    note: str | None


class AdminStatus(BaseModel):
    paused: bool
    scan_running: bool
    interval_minutes: int
    budget: dict
    counts: dict[str, int]
    recent_runs: list[ScanRunOut]
