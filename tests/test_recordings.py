import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app import config, generate, main, recordings, transcribe
from tests.sample import RAW


def _webm(tmp_path, seconds, freq, name):
    out = tmp_path / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
                    "-c:a", "libopus", "-f", "webm", str(out)], check=True)
    return out.read_bytes()


def _pieces(data, n=4):
    size = max(1, len(data) // n + 1)
    return [data[i:i + size] for i in range(0, len(data), size)]


@pytest.fixture()
def client(monkeypatch):
    seen = {}
    monkeypatch.setattr(transcribe, "transcribe", lambda a, l, p=lambda m: None: "[00:00:01] Bonjour")
    def fake(t, meta, progress=lambda m: None):
        seen["meta"] = meta
        return generate.normalize(RAW, meta)
    monkeypatch.setattr(generate, "analyze", fake)
    c = TestClient(main.app); c.seen = seen
    return c


def _wait(c, mid, want=("done", "error")):
    for _ in range(100):
        m = c.get(f"/api/meetings/{mid}").json()
        if m["status"] in want:
            return m
        time.sleep(0.1)
    raise AssertionError("timeout")


def _upload(c, mid, part, data):
    for seq, piece in enumerate(_pieces(data)):
        assert c.put(f"/api/recordings/{mid}/parts/{part}/chunks/{seq}", content=piece).status_code == 200


def test_two_parts_after_interruption_are_concatenated(client, tmp_path):
    mid = client.post("/api/recordings", json={"title": "Réunion appel"}).json()["id"]
    assert client.get(f"/api/meetings/{mid}").json()["status"] == "recording"
    _upload(client, mid, 0, _webm(tmp_path, 3, 440, "a.webm"))
    _upload(client, mid, 1, _webm(tmp_path, 2, 660, "b.webm"))
    info = client.get(f"/api/meetings/{mid}").json()["rec_info"]
    assert info["parts"] == 2 and info["chunks"] == 8
    r = client.post(f"/api/recordings/{mid}/finish", json={
        "meta": {"title": "Réunion appel"}, "markers": [75, 5],
        "interruptions": [{"at": 3, "duration": 12.4, "reason": "appel <script>"}]})
    assert r.status_code == 200
    m = _wait(client, mid)
    assert m["status"] == "done", m["error"]
    assert 4.5 < m["duration"] < 5.8                       # 3 s + 2 s
    ctx = client.seen["meta"]["context"]
    assert "00:00:05, 00:01:15" in ctx and "00:00:03 (≈ 12 s)" in ctx and "<script>" not in ctx
    assert not (config.AUDIO_DIR / mid).exists()           # audio supprimé après succès
    assert client.put(f"/api/recordings/{mid}/parts/0/chunks/99", content=b"x").status_code == 409


def test_chunk_resend_is_idempotent_and_truncated_part_is_usable(client, tmp_path):
    mid = client.post("/api/recordings", json={}).json()["id"]
    data = _webm(tmp_path, 4, 500, "c.webm")
    pieces = _pieces(data, 5)
    for seq, p in enumerate(pieces[:-1]):                  # dernier segment jamais reçu (coupure brutale)
        client.put(f"/api/recordings/{mid}/parts/0/chunks/{seq}", content=p)
    client.put(f"/api/recordings/{mid}/parts/0/chunks/1", content=pieces[1])  # renvoi après retry réseau
    assert client.get(f"/api/meetings/{mid}").json()["rec_info"]["chunks"] == 4
    client.post(f"/api/recordings/{mid}/finish", json={})
    m = _wait(client, mid)
    assert m["status"] == "done" and m["duration"] > 1.5


def test_finish_without_audio_is_rejected_and_validation(client):
    mid = client.post("/api/recordings", json={}).json()["id"]
    assert client.post(f"/api/recordings/{mid}/finish", json={}).status_code == 409
    assert client.put(f"/api/recordings/{mid}/parts/5000/chunks/0", content=b"x").status_code == 422
    assert client.put(f"/api/recordings/{mid}/parts/0/chunks/0", content=b"").status_code == 422
    assert client.put("/api/recordings/inconnu/parts/0/chunks/0", content=b"x").status_code == 404


def test_failure_keeps_audio_and_finish_can_be_retried(client, tmp_path, monkeypatch):
    mid = client.post("/api/recordings", json={}).json()["id"]
    _upload(client, mid, 0, _webm(tmp_path, 2, 440, "d.webm"))
    good = transcribe.transcribe
    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("API HS")))
    client.post(f"/api/recordings/{mid}/finish", json={})
    assert _wait(client, mid)["status"] == "error"
    assert (config.AUDIO_DIR / mid / "rec").exists()       # l'audio n'est pas perdu
    monkeypatch.setattr(transcribe, "transcribe", good)
    assert client.post(f"/api/recordings/{mid}/finish", json={}).status_code == 200
    assert _wait(client, mid)["status"] == "done"


def test_delete_removes_audio(client, tmp_path):
    mid = client.post("/api/recordings", json={}).json()["id"]
    _upload(client, mid, 0, _webm(tmp_path, 1, 440, "e.webm"))
    assert (config.AUDIO_DIR / mid).exists()
    client.delete(f"/api/meetings/{mid}")
    assert not (config.AUDIO_DIR / mid).exists()


def test_session_notes_formatting():
    assert recordings.session_notes([], []) == ""
    n = recordings.session_notes([3700], [{"at": 10, "duration": 30, "reason": "micro coupé"}])
    assert "01:01:40" in n and "00:00:10 (≈ 30 s) – micro coupé" in n


def test_offline_start_registers_later_with_client_id_and_real_start_time(client, tmp_path):
    """Mode avion : l'appareil génère l'identifiant et l'heure de début ; le serveur les reçoit bien plus tard."""
    mid = "abcdef012345"
    body = {"id": mid, "started_at": "2026-11-05T08:00:00Z", "title": "Réunion en mode avion"}
    assert client.post("/api/recordings", json=body).json() == {"id": mid}
    assert client.post("/api/recordings", json=body).json() == {"id": mid}      # renvoi après coupure : idempotent
    m = client.get(f"/api/meetings/{mid}").json()
    assert m["status"] == "recording" and m["created_at"].startswith("2026-11-0")  # date du début, pas de l'envoi
    _upload(client, mid, 0, _webm(tmp_path, 2, 440, "f.webm"))
    client.post(f"/api/recordings/{mid}/finish", json={})
    assert _wait(client, mid)["status"] == "done"


def test_client_id_validation_and_no_overwrite(client):
    for bad in ("../../etc", "ABCDEF012345", "short", "g" * 12, "a" * 13):
        assert client.post("/api/recordings", json={"id": bad}).status_code == 422
    r = client.post("/api/meetings/text", json={"text": "x"}).json()["id"]
    assert client.post("/api/recordings", json={"id": r}).status_code == 409   # pas d'écrasement d'une autre réunion


def test_future_start_time_is_clamped_and_garbage_ignored(client):
    a = client.post("/api/recordings", json={"started_at": "2099-01-01T00:00:00Z"}).json()["id"]
    assert client.get(f"/api/meetings/{a}").json()["created_at"] < "2030"
    b = client.post("/api/recordings", json={"started_at": "pas une date"}).json()["id"]
    assert client.get(f"/api/meetings/{b}").json()["status"] == "recording"
