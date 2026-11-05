import time

import pytest
from fastapi.testclient import TestClient

from app import generate, main
from tests.sample import RAW


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None: generate.normalize(RAW, meta))
    return TestClient(main.app)


def _wait_done(c, mid):
    for _ in range(50):
        m = c.get(f"/api/meetings/{mid}").json()
        if m["status"] in ("done", "error"):
            return m
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_text_flow_and_exports(client):
    r = client.post("/api/meetings/text", json={"text": "[00:00:01] Bonjour", "title": "Test"})
    mid = r.json()["id"]
    m = _wait_done(client, mid)
    assert m["status"] == "done" and m["title"] == "Test" and m["analysis"]["actions"]
    for t in ("pv", "cr", "note"):
        for f in ("pdf", "docx", "xlsx"):
            resp = client.get(f"/api/meetings/{mid}/export/{t}.{f}")
            assert resp.status_code == 200 and "attachment" in resp.headers["content-disposition"]
    assert client.get(f"/api/meetings/{mid}/preview/pv").json()[0]["t"] == "title"
    assert client.get(f"/api/meetings/{mid}/export/zzz.pdf").status_code == 404
    assert client.delete(f"/api/meetings/{mid}").json() == {"ok": True}
    assert client.get(f"/api/meetings/{mid}").status_code == 404


def test_validation(client):
    assert client.post("/api/meetings/url", json={"url": "ftp://x"}).status_code == 422
    assert client.post("/api/meetings/text", json={"text": "  "}).status_code == 422


def test_password_protection(client, monkeypatch):
    monkeypatch.setattr(main.config, "PASSWORD", "secret")
    assert client.get("/api/meetings").status_code == 401
    assert client.get("/api/meetings", auth=("gmeeting", "bad")).status_code == 401
    assert client.get("/api/meetings", auth=("gmeeting", "secret")).status_code == 200
