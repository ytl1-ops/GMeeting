"""Robustesse : reprise après redémarrage du serveur et relance d'un traitement en erreur, quel que soit son origine."""
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app import config, db, generate, ingest, main, transcribe
from tests.sample import RAW


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(transcribe, "transcribe", lambda a, l, p=lambda m: None: "[00:00:01] Bonjour")
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None, attachments=None: generate.normalize(RAW, meta))
    return TestClient(main.app)


def _wait(c, mid):
    for _ in range(100):
        m = c.get(f"/api/meetings/{mid}").json()
        if m["status"] in ("done", "error"):
            return m
        time.sleep(0.1)
    raise AssertionError("timeout")


def _webm(path, seconds=2):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "libopus", str(path)], check=True)
    return path.read_bytes()


def test_interrupted_jobs_become_explicit_retryable_errors_at_startup():
    ids = {s: db.create(title=s, source_type="text", status=s, progress="x")["id"] for s in ("queued", "processing", "analyzing", "done", "recording", "error")}
    assert db.recover_interrupted() == 3
    for s in ("queued", "processing", "analyzing"):
        m = db.get(ids[s]); assert m["status"] == "error" and "redémarrage" in m["error"] and "Relancer" in m["error"]
    assert db.get(ids["done"])["status"] == "done" and db.get(ids["recording"])["status"] == "recording"   # le reste est intact
    assert db.recover_interrupted() == 0                                                                       # idempotent


def test_retry_from_transcript(client):
    mid = db.create(title="t", source_type="text", status="error", transcript="[00:00:01] x", error=db.INTERRUPTED)["id"]
    assert client.post(f"/api/meetings/{mid}/retry").status_code == 200
    m = _wait(client, mid)
    assert m["status"] == "done" and m["error"] is None and m["analysis"]["actions"]


def test_retry_from_a_recording_kept_after_failure(client, tmp_path):
    mid = client.post("/api/recordings", json={}).json()["id"]
    client.put(f"/api/recordings/{mid}/parts/0/chunks/0", content=_webm(tmp_path / "r.webm"))
    db.update(mid, status="error", error=db.INTERRUPTED)
    assert client.post(f"/api/meetings/{mid}/retry").status_code == 200 and _wait(client, mid)["status"] == "done"


def test_retry_from_an_uploaded_file_kept_after_failure(client, tmp_path):
    mid = db.create(title="u", source_type="upload", status="error", error=db.INTERRUPTED)["id"]
    d = config.AUDIO_DIR / mid; d.mkdir(parents=True)
    (d / "upload.webm").write_bytes(_webm(tmp_path / "u.webm"))
    assert client.post(f"/api/meetings/{mid}/retry").status_code == 200 and _wait(client, mid)["status"] == "done"


def test_retry_from_a_link(client, monkeypatch):
    monkeypatch.setattr(ingest, "fetch_url", lambda url, workdir, lang=None, subs=True, progress=lambda m: None:
                        ingest.Fetched(audio=None, text="[00:00:01] sous-titres", title="Vidéo"))
    mid = db.create(title="", source_type="url", source_url="https://example.org/v", status="error", error="x")["id"]
    assert client.post(f"/api/meetings/{mid}/retry").status_code == 200
    assert _wait(client, mid)["status"] == "done"


def test_retry_refusals(client):
    nothing = db.create(title="n", source_type="upload", status="error", error="x")["id"]
    assert client.post(f"/api/meetings/{nothing}/retry").status_code == 409            # plus rien à relancer
    done = db.create(title="d", source_type="text", status="done", transcript="x")["id"]
    assert client.post(f"/api/meetings/{done}/retry").status_code == 409               # seul un traitement en erreur se relance
    assert client.post("/api/meetings/inconnu/retry").status_code == 404
