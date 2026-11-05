"""Configuration centralisée (variables d'environnement)."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "gmeeting.db"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
TRANSCRIBE_PROVIDER = os.getenv("TRANSCRIBE_PROVIDER", "auto").lower()
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

PASSWORD = os.getenv("GMEETING_PASSWORD", "")
KEEP_AUDIO = os.getenv("KEEP_AUDIO", "false").lower() in {"1", "true", "yes", "oui"}

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
# Au-delà de ce volume de texte, l'analyse passe en deux temps (résumés partiels puis synthèse).
MAX_DIRECT_CHARS = int(os.getenv("MAX_DIRECT_CHARS", "350000"))

for d in (DATA_DIR, AUDIO_DIR):
    d.mkdir(parents=True, exist_ok=True)
