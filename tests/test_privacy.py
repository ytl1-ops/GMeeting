"""Protection des données : la page « Confidentialité » ne dit que des faits, et les pièces reçues par partage ne traînent jamais."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import attachments, config, db, main, retention, transcribe


@pytest.fixture()
def client():
    return TestClient(main.app)


def _staged(hours_old: float, mid=None):
    a = db.att_create(meeting_id=mid, name="mail.eml", kind="email", label="E-mail (.eml)", size=1, snippet="", extract={})
    old = (datetime.now() - timedelta(hours=hours_old)).isoformat(timespec="seconds")
    with db._lock, db._conn() as c:
        c.execute("UPDATE attachments SET created_at=? WHERE id=?", (old, a["id"]))
    (attachments._dir(a["id"])).mkdir(parents=True, exist_ok=True)
    (attachments._dir(a["id"]) / "file").write_bytes(b"secret")
    return a["id"]


def test_privacy_reports_the_real_configuration(client, monkeypatch):
    monkeypatch.setattr(config, "RETENTION_DAYS", 30); monkeypatch.setattr(config, "KEEP_AUDIO", True)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-ne-doit-jamais-sortir"); monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-oai-ne-doit-jamais-sortir")
    monkeypatch.setattr(transcribe, "provider", lambda: "openai")
    r = client.get("/api/privacy"); d = r.json()
    assert r.status_code == 200
    assert d["retention_days"] == 30 and d["keep_audio"] is True and d["ai_drafting"]["enabled"] is True
    assert d["transcription"] == {"provider": "openai", "audio_leaves_server": True}
    assert "sk-" not in r.text and "ne-doit-jamais-sortir" not in r.text            # aucun secret


def test_privacy_local_transcription_keeps_audio_on_the_server(client, monkeypatch):
    monkeypatch.setattr(transcribe, "provider", lambda: "local"); monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    d = client.get("/api/privacy").json()
    assert d["transcription"]["audio_leaves_server"] is False and d["ai_drafting"]["enabled"] is False


def test_privacy_detects_https_and_password(client, monkeypatch):
    monkeypatch.setattr(config, "PASSWORD", "pw")
    assert client.get("/api/privacy").status_code == 401                              # comme le reste de l'application
    auth = ("u", "pw")
    d = client.get("/api/privacy", auth=auth).json()
    assert d["password_set"] is True and d["https"] is False
    assert client.get("/api/privacy", auth=auth, headers={"x-forwarded-proto": "https"}).json()["https"] is True


def test_shared_files_never_attached_are_erased_even_without_retention(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_DAYS", 0)
    old, fresh = _staged(30), _staged(2)
    mid = db.create(title="x", status="done")["id"]
    attached = _staged(30, mid=mid)
    retention.purge()                                                                 # sans RETENTION_DAYS : nettoie quand même la zone d'attente
    assert db.att_get(old) is None and not attachments._dir(old).exists()
    assert db.att_get(fresh) is not None                                              # récent : l'utilisateur peut encore le rattacher
    assert db.att_get(attached) is not None                                           # rattaché à une réunion : jamais touché
    attachments.delete(fresh); attachments.delete(attached); db.delete(mid)


def test_startup_cleanup_erases_stale_shared_files(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_DAYS", 0)
    monkeypatch.setattr(retention.threading, "Thread", lambda **k: type("T", (), {"start": lambda self: None})())   # pas de boucle en arrière-plan
    old = _staged(48)
    retention.schedule()
    assert db.att_get(old) is None


def test_deleting_a_meeting_erases_everything(client, monkeypatch):
    mid = db.create(title="x", status="done")["id"]
    att = _staged(1, mid=mid)
    audio = config.AUDIO_DIR / mid; audio.mkdir(parents=True, exist_ok=True); (audio / "a.opus").write_bytes(b"x")
    (config.ARCHIVE_DIR / f"{mid}.ogg").parent.mkdir(parents=True, exist_ok=True); (config.ARCHIVE_DIR / f"{mid}.ogg").write_bytes(b"x")
    assert client.delete(f"/api/meetings/{mid}").status_code == 200
    assert db.get(mid) is None and db.att_get(att) is None
    assert not audio.exists() and not (config.ARCHIVE_DIR / f"{mid}.ogg").exists() and not attachments._dir(att).exists()
