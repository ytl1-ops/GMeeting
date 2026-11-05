"""Serveur de test de bout en bout : vrai pipeline (upload, ffmpeg, assemblage) mais transcription et rédaction simulées
(aucune clé API requise).  Usage : python tests/e2e/run_stub.py   (port 8765)"""
import os, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="gmeeting_e2e_"))

from app import generate, transcribe  # noqa: E402
from tests.sample import RAW, TRANSCRIPT  # noqa: E402

def fake_analyze(t, meta, progress=lambda m: None, attachments=None):
    progress("Rédaction (simulée)…"); time.sleep(1); return generate.normalize(RAW, meta)

generate.analyze = fake_analyze
transcribe.transcribe = lambda a, l, p=lambda m: None: (p("Transcription (simulée)…"), time.sleep(1), TRANSCRIPT)[2]

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8765")), log_level="warning")
