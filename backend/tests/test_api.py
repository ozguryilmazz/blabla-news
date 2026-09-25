import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db
from app.main import app
from app.models import Source
from app.pipeline import run_scan
from tests.conftest import FakeAI, FakeFetcher, entry

ADMIN = {"X-Admin-Password": "test-sifre"}


@pytest.fixture
def client(engine):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def published(session):
    tov = "https://www.timesofisrael.com/feed/"
    for s in session.scalars(select(Source)):
        s.active = s.url == tov
    session.commit()
    fetcher = FakeFetcher(
        feeds={tov: [entry("u1", "Erdogan warns Israel", "Short RSS summary")]},
        texts={"u1": "FULL ORIGINAL TEXT about Erdogan"},
    )
    run_scan(db.session_factory, fetcher, FakeAI())


def test_list_and_detail_hide_full_original_text(client, published):
    page = client.get("/api/articles").json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["source"]["country"] == "IL"

    detail = client.get(f"/api/articles/{item['id']}").json()
    assert detail["title_tr"] == "TR: Erdogan warns Israel"
    assert detail["url"] == "u1"
    assert "FULL ORIGINAL TEXT" not in str(detail)
    assert detail["key_points_tr"] == ["Birinci nokta", "İkinci nokta"]


def test_filters(client, published):
    assert client.get("/api/articles", params={"country": "GR"}).json()["total"] == 0
    assert client.get("/api/articles", params={"category": "siyaset-diplomasi"}).json()["total"] == 1
    assert client.get("/api/articles", params={"q": "Türkiye"}).json()["total"] == 1
    assert client.get("/api/articles", params={"q": "yokboyle"}).json()["total"] == 0
    assert client.get("/api/articles", params={"date_from": "2026-09-21"}).json()["total"] == 0


def test_admin_requires_password(client):
    assert client.get("/api/admin/status").status_code == 401
    assert client.get("/api/admin/status", headers={"X-Admin-Password": "yanlis"}).status_code == 401
    assert client.get("/api/admin/status", headers=ADMIN).status_code == 200


def test_pause_and_resume(client):
    client.post("/api/admin/pause", headers=ADMIN)
    assert client.get("/api/admin/status", headers=ADMIN).json()["paused"] is True
    client.post("/api/admin/resume", headers=ADMIN)
    assert client.get("/api/admin/status", headers=ADMIN).json()["paused"] is False


def test_category_toggle_and_source_crud(client):
    cats = client.get("/api/categories").json()
    r = client.patch(f"/api/admin/categories/{cats[0]['id']}", json={"scan_enabled": False}, headers=ADMIN)
    assert r.json()["scan_enabled"] is False

    body = {"name": "Yeni Kaynak", "country": "GR", "language": "el", "url": "https://example.gr/rss"}
    created = client.post("/api/admin/sources", json=body, headers=ADMIN)
    assert created.status_code == 201
    assert client.post("/api/admin/sources", json=body, headers=ADMIN).status_code == 409
    sid = created.json()["id"]
    assert client.patch(f"/api/admin/sources/{sid}", json={"active": False}, headers=ADMIN).json()["active"] is False
