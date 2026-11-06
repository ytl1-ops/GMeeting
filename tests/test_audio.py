import json
import re
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app import config, generate, ingest, main, recordings, transcribe
from tests.sample import RAW


def _ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=codec_name,channels,sample_rate:format=duration,size", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    return {**j["streams"][0], **j["format"]}


def _mean_volume(path) -> float:
    r = subprocess.run(["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr).group(1))


def _sine(tmp_path, name, seconds=20, vol_db=0, stereo=True):
    out = tmp_path / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}:sample_rate=48000",
                    "-af", f"volume={vol_db}dB", "-ac", "2" if stereo else "1", str(out)], check=True)
    return out


def test_work_file_is_compact_opus_mono_16k(tmp_path):
    src = _sine(tmp_path, "in.wav", seconds=30)
    dst = ingest.normalize_audio(src, tmp_path / f"out{ingest.AUDIO_EXT}")
    p = _ffprobe(dst)
    assert (p["codec_name"], int(p["channels"])) == ("opus", 1)   # (ffprobe annonce toujours 48 kHz pour Opus : fréquence de décodage)
    kbps = int(p["size"]) * 8 / float(p["duration"]) / 1000
    assert kbps <= config.AUDIO_KBPS * 1.1                      # plafonné (VBR contraint) : ≤ ≈ 14 Mo/h, contre ≈ 21 Mo/h en MP3 48 kbps, même sur un son tonal
    assert int(src.stat().st_size) > 20 * int(p["size"])        # très inférieur au WAV d'origine


def test_bandwidth_is_limited_to_speech_16k(tmp_path, monkeypatch):
    """Preuve que l'encodage est bien à 16 kHz : une voix (300 Hz) est conservée, un son à 10 kHz (inutile à la parole) est éliminé."""
    monkeypatch.setattr(config, "AUDIO_ENHANCE", False)
    def tone(freq):
        src = tmp_path / f"t{freq}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=5:sample_rate=48000", str(src)], check=True)
        return _mean_volume(ingest.normalize_audio(src, tmp_path / f"t{freq}.ogg"))
    assert tone(300) > -30 and tone(10000) < -60


def test_quiet_recordings_are_brought_up_but_can_be_disabled(tmp_path, monkeypatch):
    quiet = _sine(tmp_path, "quiet.wav", vol_db=-38)
    monkeypatch.setattr(config, "AUDIO_ENHANCE", True)
    loud = ingest.normalize_audio(quiet, tmp_path / "e.ogg")
    monkeypatch.setattr(config, "AUDIO_ENHANCE", False)
    raw = ingest.normalize_audio(quiet, tmp_path / "r.ogg")
    assert _mean_volume(loud) > _mean_volume(raw) + 10          # le volume est rattrapé…
    assert _mean_volume(loud) < -8                              # …sans saturation


def test_bitrate_is_configurable_and_bounded(tmp_path, monkeypatch):
    src = _sine(tmp_path, "in.wav", seconds=30)
    sizes = {}
    for k in (16, 64):
        monkeypatch.setattr(config, "AUDIO_KBPS", k)
        sizes[k] = ingest.normalize_audio(src, tmp_path / f"o{k}.ogg").stat().st_size
    assert sizes[64] > sizes[16]


def test_long_audio_is_split_in_decodable_segments(tmp_path):
    src = _sine(tmp_path, "long.wav", seconds=200, stereo=False)
    dst = ingest.normalize_audio(src, tmp_path / "long.ogg")
    parts = ingest.split_audio(dst, seconds=60)
    assert len(parts) >= 3 and all(p.suffix == ".ogg" for p, _ in parts)
    assert [off for _, off in parts] == [0.0, 60.0, 120.0, 180.0][: len(parts)]
    assert all(float(_ffprobe(p)["duration"]) > 5 for p, _ in parts)


def test_assembled_recording_uses_the_same_compact_format(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_ENHANCE", False)
    mid = "aaaaaaaaaaaa"
    for part, f in enumerate((300, 600)):
        webm = tmp_path / f"p{part}.webm"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={f}:duration=3", "-c:a", "libopus", str(webm)], check=True)
        recordings.write_chunk(mid, part, 0, webm.read_bytes())
    out = recordings.assemble(mid, tmp_path / f"audio{ingest.AUDIO_EXT}")
    p = _ffprobe(out)
    assert p["codec_name"] == "opus" and int(p["channels"]) == 1 and 5.5 < float(p["duration"]) < 6.6


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(transcribe, "transcribe", lambda a, l, p=lambda m: None: "[00:00:01] Bonjour")
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None, attachments=None: generate.normalize(RAW, meta))
    return TestClient(main.app)


def _record(client, tmp_path, name="c.webm"):
    mid = client.post("/api/recordings", json={"title": "Archive"}).json()["id"]
    webm = tmp_path / name
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:a", "libopus", str(webm)], check=True)
    client.put(f"/api/recordings/{mid}/parts/0/chunks/0", content=webm.read_bytes())
    client.post(f"/api/recordings/{mid}/finish", json={})
    for _ in range(100):
        m = client.get(f"/api/meetings/{mid}").json()
        if m["status"] in ("done", "error"):
            return mid, m
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_keep_audio_archives_one_compact_file_and_serves_it(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "KEEP_AUDIO", True)
    mid, m = _record(client, tmp_path)
    assert m["status"] == "done" and m["has_audio"] is True
    assert not (config.AUDIO_DIR / mid).exists()                          # le brut est supprimé : un seul fichier conservé
    assert _ffprobe(config.ARCHIVE_DIR / f"{mid}.ogg")["codec_name"] == "opus"
    r = client.get(f"/api/meetings/{mid}/audio")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/ogg")
    part = client.get(f"/api/meetings/{mid}/audio", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100           # lecture par plages : avance/retour dans le lecteur
    client.delete(f"/api/meetings/{mid}")
    assert not (config.ARCHIVE_DIR / f"{mid}.ogg").exists()


def test_default_deletes_all_audio(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "KEEP_AUDIO", False)
    mid, m = _record(client, tmp_path, "d.webm")
    assert m["has_audio"] is False and not (config.ARCHIVE_DIR / f"{mid}.ogg").exists() and not (config.AUDIO_DIR / mid).exists()
    assert client.get(f"/api/meetings/{mid}/audio").status_code == 404
