import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import pipeline
from .budget import budget_status
from .config import get_settings
from .db import Base, get_engine, get_session, session_factory
from .models import Article, Category, ScanRun, Source
from .schemas import (
    AdminStatus,
    ArticleDetail,
    ArticlePage,
    ArticleSummary,
    CategoryOut,
    CategoryUpdate,
    ScanRunOut,
    SourceAdmin,
    SourceCreate,
    SourcePublic,
    SourceUpdate,
)
from .seed import seed

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(get_engine())
    session = session_factory()
    try:
        seed(session)
    finally:
        session.close()
    scheduler = None
    if get_settings().scheduler_enabled:
        from .scheduler import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Haber Analiz API", lifespan=lifespan)


def require_admin(x_admin_password: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_admin_password, get_settings().admin_password):
        raise HTTPException(status_code=401, detail="Yönetici şifresi hatalı")


def _excerpt(text: str | None, limit: int = 240) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _summary(a: Article) -> ArticleSummary:
    return ArticleSummary(
        id=a.id,
        url=a.url,
        published_at=a.published_at,
        title_orig=a.title_orig,
        title_tr=a.title_tr,
        excerpt_tr=_excerpt(a.summary_tr),
        source=SourcePublic.model_validate(a.source),
        category=CategoryOut.model_validate(a.category) if a.category else None,
    )


# ---------- Herkese açık uçlar ----------


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/articles", response_model=ArticlePage)
def list_articles(
    q: str | None = None,
    country: str | None = Query(default=None, pattern="^(GR|IL)$"),
    category: str | None = None,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    stmt = select(Article).join(Source).where(Article.status == "published")
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Article.title_tr.ilike(like),
                Article.summary_tr.ilike(like),
                Article.tags.ilike(like),
                Article.title_orig.ilike(like),
            )
        )
    if country:
        stmt = stmt.where(Source.country == country)
    if category:
        stmt = stmt.join(Category, Article.category_id == Category.id).where(Category.slug == category)
    if source_id:
        stmt = stmt.where(Article.source_id == source_id)
    if date_from:
        stmt = stmt.where(Article.published_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        stmt = stmt.where(Article.published_at <= datetime.combine(date_to, time.max, timezone.utc))

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(Article.published_at.desc(), Article.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ArticlePage(items=[_summary(a) for a in rows], total=total, page=page, page_size=page_size)


@app.get("/api/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int, session: Session = Depends(get_session)):
    a = session.get(Article, article_id)
    if a is None or a.status != "published":
        raise HTTPException(status_code=404, detail="Haber bulunamadı")
    # Telif: tam orijinal metin (content_orig) hiçbir zaman dışarı verilmez
    return ArticleDetail(
        id=a.id,
        url=a.url,
        published_at=a.published_at,
        title_orig=a.title_orig,
        excerpt_orig=a.excerpt_orig,
        title_tr=a.title_tr,
        summary_tr=a.summary_tr,
        key_points_tr=[p for p in (a.key_points_tr or "").split("\n") if p.strip()],
        tags=[t.strip() for t in (a.tags or "").split(",") if t.strip()],
        source=SourcePublic.model_validate(a.source),
        category=CategoryOut.model_validate(a.category) if a.category else None,
    )


@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_session)):
    return session.scalars(select(Category).order_by(Category.sort_order)).all()


@app.get("/api/sources", response_model=list[SourcePublic])
def list_sources(session: Session = Depends(get_session)):
    return session.scalars(select(Source).where(Source.active.is_(True)).order_by(Source.country, Source.name)).all()


# ---------- Yönetim uçları ----------


@app.get("/api/admin/status", response_model=AdminStatus, dependencies=[Depends(require_admin)])
def admin_status(session: Session = Depends(get_session)):
    counts = dict(session.execute(select(Article.status, func.count()).group_by(Article.status)).all())
    runs = session.scalars(select(ScanRun).order_by(ScanRun.id.desc()).limit(10)).all()
    return AdminStatus(
        paused=pipeline.is_paused(session),
        scan_running=pipeline.scan_running(),
        interval_minutes=get_settings().scan_interval_minutes,
        budget=budget_status(session),
        counts=counts,
        recent_runs=[ScanRunOut.model_validate(r) for r in runs],
    )


@app.post("/api/admin/scan", status_code=202, dependencies=[Depends(require_admin)])
def admin_scan():
    if pipeline.scan_running():
        raise HTTPException(status_code=409, detail="Bir tarama zaten sürüyor")
    from .scheduler import start_manual_scan

    start_manual_scan()
    return {"started": True}


@app.post("/api/admin/pause", dependencies=[Depends(require_admin)])
def admin_pause(session: Session = Depends(get_session)):
    pipeline.set_paused(session, True)
    return {"paused": True}


@app.post("/api/admin/resume", dependencies=[Depends(require_admin)])
def admin_resume(session: Session = Depends(get_session)):
    pipeline.set_paused(session, False)
    return {"paused": False}


@app.get("/api/admin/sources", response_model=list[SourceAdmin], dependencies=[Depends(require_admin)])
def admin_sources(session: Session = Depends(get_session)):
    return session.scalars(select(Source).order_by(Source.country, Source.name)).all()


@app.post("/api/admin/sources", response_model=SourceAdmin, status_code=201, dependencies=[Depends(require_admin)])
def admin_create_source(body: SourceCreate, session: Session = Depends(get_session)):
    if session.scalar(select(Source.id).where(Source.url == body.url)):
        raise HTTPException(status_code=409, detail="Bu adres zaten kayıtlı")
    source = Source(**body.model_dump())
    session.add(source)
    session.commit()
    return source


@app.patch("/api/admin/sources/{source_id}", response_model=SourceAdmin, dependencies=[Depends(require_admin)])
def admin_update_source(source_id: int, body: SourceUpdate, session: Session = Depends(get_session)):
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(source, key, value)
    session.commit()
    return source


@app.patch("/api/admin/categories/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)])
def admin_update_category(category_id: int, body: CategoryUpdate, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(category, key, value)
    session.commit()
    return category
