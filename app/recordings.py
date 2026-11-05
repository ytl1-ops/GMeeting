"""Enregistrement continu : réception de l'audio par segments puis assemblage.

Le navigateur envoie l'audio au fil de l'eau (un segment toutes les ~4 s). Chaque « partie » correspond à un
MediaRecorder ; une nouvelle partie démarre si l'enregistreur a dû être relancé (appel téléphonique, coupure du
micro…). Les envois sont idempotents (même segment renvoyé = écrasé) pour permettre les reprises après coupure
réseau. Si l'application se ferme, tout ce qui a été reçu reste exploitable.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from . import config
from .ingest import AUDIO_EXT, audio_args, require_ffmpeg

MAX_CHUNK_BYTES = 64 * 1024 * 1024


def root(mid: str) -> Path:
    return config.AUDIO_DIR / mid / "rec"


def write_chunk(mid: str, part: int, seq: int, data: bytes) -> None:
    pdir = root(mid) / f"part_{part:03d}"
    pdir.mkdir(parents=True, exist_ok=True)
    tmp = pdir / f".chunk_{seq:06d}.tmp"
    tmp.write_bytes(data)
    tmp.replace(pdir / f"chunk_{seq:06d}")  # atomique : jamais de segment à moitié écrit


def info(mid: str) -> dict:
    chunks = list(root(mid).glob("part_*/chunk_*"))
    last = max((c.stat().st_mtime for c in chunks), default=None)
    return {
        "chunks": len(chunks),
        "parts": len({c.parent.name for c in chunks}),
        "bytes": sum(c.stat().st_size for c in chunks),
        "last_chunk_age": None if last is None else max(0, int(time.time() - last)),
    }


def assemble(mid: str, out: Path) -> Path:
    """Concatène les segments de chaque partie, normalise chaque partie, puis les met bout à bout."""
    require_ffmpeg()
    parts: list[Path] = []
    for pdir in sorted(root(mid).glob("part_*")):
        chunks = sorted(pdir.glob("chunk_*"))
        if not chunks:
            continue
        joined = pdir / "joined.bin"
        with open(joined, "wb") as f:
            for c in chunks:
                f.write(c.read_bytes())
        enc = pdir / f"part{AUDIO_EXT}"
        # Une partie tronquée (coupure brutale) reste lisible : on accepte un code retour non nul
        # tant que de l'audio exploitable a été produit.
        subprocess.run(["ffmpeg", "-y", "-i", str(joined), *audio_args(), str(enc)], capture_output=True)
        if enc.exists() and enc.stat().st_size > 500:
            parts.append(enc)
    if not parts:
        raise RuntimeError("Aucun audio exploitable n'a été reçu pour cet enregistrement.")
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        shutil.copyfile(parts[0], out)
        return out
    listing = out.parent / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"Assemblage de l'enregistrement impossible : {r.stderr[-300:]}")
    return out


def _fmt(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def _clean(text) -> str:
    """Texte libre venant du navigateur : on ne garde que lettres, chiffres et ponctuation simple."""
    return re.sub(r"[^\w \-'’().,é]", "", str(text or ""))[:60].strip()


def session_notes(markers: list, interruptions: list) -> str:
    """Texte ajouté au contexte de rédaction : repères de l'utilisateur et trous d'enregistrement."""
    lines = []
    clean = sorted(float(m) for m in markers if isinstance(m, (int, float)) and 0 <= m < 86400)[:200]
    if clean:
        lines.append("Moments marqués comme importants par l'utilisateur pendant la réunion (temps écoulé) : "
                     + ", ".join(_fmt(m) for m in clean) + ".")
    ints = []
    for i in interruptions[:100]:
        if isinstance(i, dict) and isinstance(i.get("at"), (int, float)):
            dur = i.get("duration")
            item = _fmt(i["at"])
            if isinstance(dur, (int, float)):
                item += f" (≈ {int(dur)} s)"
            reason = _clean(i.get("reason"))
            if reason:
                item += f" – {reason}"
            ints.append(item)
    if ints:
        lines.append("Interruptions techniques de l'enregistrement (des échanges ont pu être manqués à ces instants) : "
                     + " ; ".join(ints) + ".")
    return "\n".join(lines)
