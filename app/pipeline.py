"""Orchestration d'une réunion : acquisition → transcription → analyse (exécuté en tâche de fond)."""
from __future__ import annotations

import shutil
import traceback
from pathlib import Path

from . import config, db, generate, ingest, recordings, transcribe


def _progress(mid: str):
    return lambda msg: db.update(mid, progress=msg)


def process(mid: str, audio_path: Path | None = None, url: str | None = None,
            raw_text: str | None = None, prefer_subtitles: bool = True, recording: bool = False) -> None:
    """Point d'entrée unique ; reprend aussi après édition de la transcription (raw_text)."""
    meeting = db.get(mid)
    assert meeting
    progress = _progress(mid)
    workdir = config.AUDIO_DIR / mid
    success = False
    try:
        transcript = raw_text
        lang = meeting.get("language") or None
        if transcript is None:
            db.update(mid, status="processing", error=None)
            if recording:
                progress("Assemblage de l'enregistrement…")
                audio_path = recordings.assemble(mid, workdir / f"audio{ingest.AUDIO_EXT}")
                db.update(mid, duration=ingest.probe_duration(audio_path))
            elif url:
                fetched = ingest.fetch_url(url, workdir, lang, prefer_subtitles, progress)
                if fetched.title and not meeting.get("title"):
                    db.update(mid, title=fetched.title)
                if fetched.duration:
                    db.update(mid, duration=fetched.duration)
                transcript, audio_path = fetched.text, fetched.audio
            elif audio_path:
                progress("Préparation de l'audio…")
                norm = ingest.normalize_audio(audio_path, workdir / f"audio{ingest.AUDIO_EXT}")
                db.update(mid, duration=ingest.probe_duration(norm))
                audio_path = norm
            if transcript is None:
                if audio_path is None:
                    raise RuntimeError("Aucune source audio ou texte à traiter.")
                progress("Transcription en cours…")
                transcript = transcribe.transcribe(audio_path, lang, progress)
            if not transcript.strip():
                raise RuntimeError("Aucune parole détectée dans l'enregistrement.")
            db.update(mid, transcript=transcript)

        db.update(mid, status="analyzing")
        meeting = db.get(mid)
        analysis = generate.analyze(transcript, meeting, progress)
        db.update(mid, analysis=analysis, status="done", progress="Terminé", error=None,
                  title=meeting.get("title") or analysis["titre"])
        success = True
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        db.update(mid, status="error", error=str(e)[:800])
    finally:
        # En cas d'échec l'audio est conservé : on ne perd jamais une réunion, le traitement peut être relancé.
        if success:
            # KEEP_AUDIO : on archive l'unique fichier Opus compact (≈ 12 Mo/h) et on supprime tout le brut
            if config.KEEP_AUDIO and audio_path and Path(audio_path).exists():
                try:
                    shutil.copyfile(audio_path, config.ARCHIVE_DIR / f"{mid}{ingest.AUDIO_EXT}")
                except OSError:
                    traceback.print_exc()
            shutil.rmtree(workdir, ignore_errors=True)
