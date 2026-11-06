import io
import threading

import pytest
from fastapi.testclient import TestClient

from app import attachments as A, config, db, main, retention


@pytest.fixture()
def c():
    return TestClient(main.app)


def _n():
    return len(db.list_all())


# ------------------------------------------------------------------ en-têtes
def test_security_headers_everywhere(c):
    for path in ("/", "/api/config", "/app.js"):
        h = c.get(path).headers
        assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff" and h["referrer-policy"] == "no-referrer"
        assert "microphone=(self)" in h["permissions-policy"] and "camera=()" in h["permissions-policy"]
        csp = h["content-security-policy"]
        assert "script-src 'self'" in csp and "object-src 'none'" in csp and "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
        assert "script-src 'self' 'unsafe-inline'" not in csp and "unsafe-eval" not in csp      # aucun script inline ni eval


def test_api_responses_are_never_cached_but_static_files_are(c):
    assert c.get("/api/config").headers["cache-control"] == "no-store"
    assert c.get("/api/meetings").headers["cache-control"] == "no-store"
    assert "no-store" not in c.get("/style.css").headers.get("cache-control", "")


def test_hsts_only_over_https(c):
    assert "strict-transport-security" not in c.get("/api/config").headers
    assert "max-age=31536000" in c.get("/api/config", headers={"X-Forwarded-Proto": "https"}).headers["strict-transport-security"]


# ------------------------------------------------------------------ CSRF
def test_cross_site_state_changing_requests_are_refused_without_side_effect(c):
    before = _n()
    for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
                    {"Origin": "http://testserver.evil.example"}):
        r = c.post("/api/meetings/text", json={"text": "x", "title": "pirate"}, headers=headers)
        assert r.status_code == 403, headers
    assert _n() == before and not any(m["title"] == "pirate" for m in db.list_all())
    # formulaire multipart « simple » (le cas classique du CSRF) et suppression
    assert c.post("/api/attachments", files=[("files", ("a.txt", b"x"))], headers={"Origin": "https://evil.example"}).status_code == 403
    m = db.create(title="à garder", source_type="text", status="done")["id"]
    assert c.delete(f"/api/meetings/{m}", headers={"Origin": "https://evil.example"}).status_code == 403
    assert db.get(m) is not None


def test_same_origin_and_non_browser_clients_still_work(c):
    ok = [{"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}, {}, {"Origin": "https://app.example", "X-Forwarded-Host": "app.example"}]
    for headers in ok:
        assert c.post("/api/meetings/text", json={"text": "[00:00:01] x", "title": "légitime"}, headers=headers).status_code == 200, headers
    assert c.get("/api/meetings", headers={"Origin": "https://evil.example"}).status_code == 200      # lecture seule : non bloquée ici


# ------------------------------------------------------------------ authentification et sonde de santé
def test_healthz_is_reachable_without_password_but_the_rest_is_not(c, monkeypatch):
    monkeypatch.setattr(config, "PASSWORD", "secret")
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["ffmpeg"] is True
    assert set(r.json()) == {"status", "ffmpeg"}                         # aucune donnée de réunion
    assert c.get("/api/meetings").status_code == 401 and c.get("/").status_code == 401
    assert c.get("/api/meetings", auth=("x", "secret")).status_code == 200


# ------------------------------------------------------------------ rétention
def _meeting(days_old: int, status: str):
    from datetime import datetime, timedelta
    old = (datetime.now() - timedelta(days=days_old)).isoformat(timespec="seconds")
    mid = db.create(title=f"{status}-{days_old}", source_type="text", status=status, created_at=old)["id"]
    (config.AUDIO_DIR / mid).mkdir(parents=True, exist_ok=True); (config.AUDIO_DIR / mid / "a.bin").write_bytes(b"x")
    (config.ARCHIVE_DIR / f"{mid}.ogg").write_bytes(b"x")
    att = A.save(io.BytesIO(b"pj"), "pj.txt", mid)["id"]
    return mid, att


def test_purge_removes_only_old_finished_meetings_with_all_their_data():
    for m in db.list_all():
        db.delete(m["id"])
    old_done, att = _meeting(40, "done"); old_err, _ = _meeting(40, "error")
    old_rec, _ = _meeting(40, "recording"); old_proc, _ = _meeting(40, "processing"); recent, _ = _meeting(5, "done")
    assert retention.purge(30) == 2
    assert db.get(old_done) is None and db.get(old_err) is None
    assert not (config.AUDIO_DIR / old_done).exists() and not (config.ARCHIVE_DIR / f"{old_done}.ogg").exists()
    assert db.att_get(att) is None and not (config.ATTACH_DIR / att).exists()
    for keep in (old_rec, old_proc, recent):                              # jamais une réunion en cours, ni une récente
        assert db.get(keep) is not None and (config.ARCHIVE_DIR / f"{keep}.ogg").exists()


def test_purge_is_disabled_by_default(monkeypatch):
    m, _ = _meeting(900, "done")
    monkeypatch.setattr(config, "RETENTION_DAYS", 0)
    assert retention.purge() == 0 and db.get(m) is not None
    started = []
    monkeypatch.setattr(threading, "Thread", lambda *a, **k: started.append(1))
    retention.schedule()
    assert started == []                                                  # aucun thread si désactivé


def test_temporary_files_go_to_the_data_volume_and_stale_ones_are_cleaned(tmp_path, monkeypatch):
    import os, tempfile, time
    assert tempfile.tempdir == str(config.TMP_DIR) and os.environ["TMPDIR"] == str(config.TMP_DIR)   # gros envois : disque, pas RAM
    with tempfile.NamedTemporaryFile() as f:
        assert f.name.startswith(str(config.TMP_DIR))
    old, fresh = config.TMP_DIR / "old.part", config.TMP_DIR / "fresh.part"
    old.write_bytes(b"x"); fresh.write_bytes(b"x")
    os.utime(old, (time.time() - 3 * 86400,) * 2)
    assert retention.clean_tmp() >= 1 and not old.exists() and fresh.exists()
    fresh.unlink()
