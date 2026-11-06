"""Transcription audio → texte (faster-whisper local ou API OpenAI)."""
from __future__ import annotations

from pathlib import Path

from . import config
from .ingest import split_audio


def _fmt(t: float) -> str:
    t = int(t)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def _have_local() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def provider() -> str:
    p = config.TRANSCRIBE_PROVIDER
    if p == "auto":
        return "local" if _have_local() else "openai"
    return p


def transcribe(audio: Path, language: str | None, progress=lambda m: None) -> str:
    """Retourne une transcription horodatée : '[hh:mm:ss] texte' par segment."""
    prov = provider()
    if prov == "local":
        return _local(audio, language, progress)
    if prov == "openai":
        return _openai(audio, language, progress)
    raise RuntimeError(f"Fournisseur de transcription inconnu : {prov}")


_model = None


def _local(audio: Path, language: str | None, progress) -> str:
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        progress(f"Chargement du modèle Whisper « {config.WHISPER_MODEL} »…")
        _model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    segments, info = _model.transcribe(str(audio), language=language or None, vad_filter=True)
    total = info.duration or 1
    lines = []
    for s in segments:
        lines.append(f"[{_fmt(s.start)}] {s.text.strip()}")
        progress(f"Transcription locale… {min(99, int(s.end / total * 100))} %")
    return "\n".join(lines)


def _openai(audio: Path, language: str | None, progress) -> str:
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "Aucun moteur de transcription : définissez OPENAI_API_KEY ou installez faster-whisper "
            "(pip install faster-whisper) pour une transcription locale."
        )
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    parts = split_audio(audio)
    lines: list[str] = []
    for i, (part, offset) in enumerate(parts, 1):
        progress(f"Transcription… segment {i}/{len(parts)}")
        with open(part, "rb") as f:
            kwargs = {"model": config.OPENAI_TRANSCRIBE_MODEL, "file": f, "response_format": "verbose_json"}
            if language:
                kwargs["language"] = language
            res = client.audio.transcriptions.create(**kwargs)
        segs = getattr(res, "segments", None)
        if segs:
            for s in segs:
                start = s["start"] if isinstance(s, dict) else s.start
                text = s["text"] if isinstance(s, dict) else s.text
                lines.append(f"[{_fmt(offset + start)}] {text.strip()}")
        else:
            lines.append(f"[{_fmt(offset)}] {res.text.strip()}")
    return "\n".join(lines)
