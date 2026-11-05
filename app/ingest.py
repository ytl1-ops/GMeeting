"""Acquisition de l'audio : fichier envoyé, enregistrement navigateur ou lien vidéo (toute source)."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import config

MEDIA_EXT = {".mp3", ".m4a", ".mp4", ".wav", ".webm", ".ogg", ".opus", ".flac", ".aac", ".mkv", ".mov", ".avi", ".wma"}


@dataclass
class Fetched:
    audio: Path | None          # fichier audio normalisé (None si on a déjà un texte)
    text: str | None = None     # transcription récupérée directement (sous-titres natifs)
    title: str | None = None
    duration: float | None = None


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg est requis (apt install ffmpeg / brew install ffmpeg).")


AUDIO_EXT = ".ogg"   # conteneur Ogg/Opus : compact, lu par ffmpeg, Whisper (local et API) et les navigateurs


def audio_args() -> list[str]:
    """Paramètres d'encodage uniques (fichiers de travail, assemblage des enregistrements, archive).

    Opus mono 16 kHz en mode « voix » : la fréquence utile à la parole et à Whisper, au meilleur rapport qualité/poids.
    Le passe-haut (70 Hz) retire les bruits graves ; loudnorm remonte les enregistrements faibles sans saturer.
    VBR « contraint » : mesuré, le VBR libre d'Opus dépasse sa cible de plus de 50 % sur certains sons (51 kbps pour 32
    demandés) ; contraint, le débit reste plafonné à ≈ cible + 3 %, donc la taille est prévisible (≈ 14 Mo/h au maximum).
    """
    af = ["-af", "highpass=f=70,loudnorm=I=-18:TP=-2:LRA=11"] if config.AUDIO_ENHANCE else []
    return ["-vn", "-ac", "1", "-ar", "16000", *af, "-c:a", "libopus", "-b:a", f"{config.AUDIO_KBPS}k", "-application", "voip", "-vbr", "constrained"]


def normalize_audio(src: Path, dst: Path) -> Path:
    """Convertit n'importe quelle source (audio/vidéo) en Opus mono 16 kHz : petit, et optimal pour la reconnaissance vocale."""
    require_ffmpeg()
    cmd = ["ffmpeg", "-y", "-i", str(src), *audio_args(), str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError(f"Conversion audio impossible : {r.stderr[-400:]}")
    return dst


def probe_duration(path: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(r.stdout.strip())
    except Exception:
        return None


def split_audio(path: Path, seconds: int = 600) -> list[tuple[Path, float]]:
    """Découpe en segments (offset en secondes) pour contourner les limites de taille des API."""
    dur = probe_duration(path) or 0
    if dur and dur <= seconds + 30 and path.stat().st_size < 24 * 1024 * 1024:
        return [(path, 0.0)]
    out_dir = path.parent / f"{path.stem}_parts"
    out_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-f", "segment", "-segment_time", str(seconds),
         "-c", "copy", str(out_dir / f"part_%04d{AUDIO_EXT}")],
        capture_output=True, check=True,
    )
    parts = sorted(out_dir.glob(f"part_*{AUDIO_EXT}"))
    return [(p, i * float(seconds)) for i, p in enumerate(parts)]


# ---------------------------------------------------------------- liens
def _vtt_to_text(vtt: str) -> str:
    """Convertit WebVTT/SRT en texte continu, en supprimant les doublons de sous-titres 'roulants'."""
    lines: list[str] = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if (not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line
                or re.fullmatch(r"\d+", line)):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


def fetch_url(url: str, workdir: Path, lang: str | None = None, prefer_subtitles: bool = True,
              progress=lambda msg: None) -> Fetched:
    """Récupère le contenu d'un lien : sous-titres natifs si possibles, sinon l'audio.

    yt-dlp couvre YouTube, Vimeo, Dailymotion, LinkedIn, Facebook, X, Loom, Teams/SharePoint
    (liens accessibles), Zoom (liens de partage sans mot de passe), PeerTube, etc.
    Les liens directs vers un fichier média sont gérés en repli.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Le lien doit commencer par http:// ou https://")
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        return _fetch_ytdlp(url, workdir, lang, prefer_subtitles, progress)
    except Exception as e_yt:  # noqa: BLE001
        progress("Extraction spécialisée impossible, tentative de téléchargement direct…")
        try:
            return _fetch_direct(url, workdir)
        except Exception as e_direct:  # noqa: BLE001
            raise RuntimeError(
                f"Impossible de récupérer ce lien. yt-dlp : {str(e_yt)[:300]} | direct : {e_direct}. "
                "Si le lien est privé (Teams, Zoom, Drive…), téléchargez le fichier puis importez-le."
            ) from e_direct


def _fetch_ytdlp(url, workdir, lang, prefer_subtitles, progress) -> Fetched:
    import yt_dlp

    langs = [l for l in [lang, "fr", "en"] if l]
    base_opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "outtmpl": str(workdir / "src.%(ext)s")}

    progress("Lecture des informations du lien…")
    with yt_dlp.YoutubeDL({**base_opts, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    title, duration = info.get("title"), info.get("duration")

    if prefer_subtitles:
        has = {**(info.get("automatic_captions") or {}), **(info.get("subtitles") or {})}
        pick = next((l for l in langs if any(k == l or k.startswith(l + "-") for k in has)), None)
        if pick:
            progress(f"Sous-titres '{pick}' trouvés, récupération du texte…")
            opts = {**base_opts, "skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                    "subtitleslangs": [pick, f"{pick}.*"], "subtitlesformat": "vtt/srt/best"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            subs = sorted(workdir.glob("src*.vtt")) + sorted(workdir.glob("src*.srt"))
            if subs:
                text = _vtt_to_text(subs[0].read_text(encoding="utf-8", errors="ignore"))
                if len(text) > 200:
                    return Fetched(audio=None, text=text, title=title, duration=duration)

    progress("Téléchargement de la piste audio…")
    opts = {**base_opts, "format": "bestaudio[abr<=128]/bestaudio/best"}   # inutile de télécharger plus gros que nécessaire
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in workdir.glob("src.*") if p.suffix not in {".vtt", ".srt", ".part"}]
    if not files:
        raise RuntimeError("aucun fichier téléchargé")
    audio = normalize_audio(files[0], workdir / f"audio{AUDIO_EXT}")
    return Fetched(audio=audio, title=title, duration=duration or probe_duration(audio))


def _fetch_direct(url: str, workdir: Path) -> Fetched:
    ext = Path(urlparse(url).path).suffix.lower()
    dst = workdir / f"direct{ext if ext in MEDIA_EXT else '.bin'}"
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "text/html" in ctype:
            raise RuntimeError("la page n'est pas un fichier média")
        with open(dst, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    audio = normalize_audio(dst, workdir / f"audio{AUDIO_EXT}")
    return Fetched(audio=audio, title=Path(urlparse(url).path).stem or None, duration=probe_duration(audio))
