"""API FastAPI + service de l'interface web."""
from __future__ import annotations

import io
import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import branding, config, db, exporters, generate, pipeline, transcribe

STATIC = Path(__file__).parent / "static"
basic = HTTPBasic(auto_error=False)


def auth(creds: HTTPBasicCredentials | None = Depends(basic)) -> None:
    if not config.PASSWORD:
        return
    ok = creds and secrets.compare_digest(creds.password.encode(), config.PASSWORD.encode())
    if not ok:
        raise HTTPException(401, "Authentification requise", headers={"WWW-Authenticate": 'Basic realm="GMeeting"'})


app = FastAPI(title="GMeeting", dependencies=[Depends(auth)])
db.init()


def _meeting(mid: str) -> dict:
    m = db.get(mid)
    if not m:
        raise HTTPException(404, "Réunion introuvable")
    return m


# ------------------------------------------------------------------ création
def _create(title, meeting_date, location, participants, context, language, source_type, source_url=None) -> dict:
    return db.create(title=(title or "").strip(), meeting_date=meeting_date or None, location=location or None,
                     participants=participants or None, context=context or None,
                     language=(language or "").strip() or None, source_type=source_type, source_url=source_url)


@app.post("/api/meetings/audio")
async def from_audio(bg: BackgroundTasks, file: UploadFile = File(...), title: str = Form(""), meeting_date: str = Form(""),
                     location: str = Form(""), participants: str = Form(""), context: str = Form(""),
                     language: str = Form(""), source_type: str = Form("upload")):
    """Enregistrement navigateur ou fichier audio/vidéo importé."""
    m = _create(title, meeting_date, location, participants, context, language, source_type)
    dest_dir = config.AUDIO_DIR / m["id"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / ("upload" + (Path(file.filename or "").suffix or ".webm"))
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > config.MAX_UPLOAD_MB * 1024 * 1024:
                f.close(); dest.unlink(missing_ok=True); db.delete(m["id"])
                raise HTTPException(413, f"Fichier trop volumineux (max {config.MAX_UPLOAD_MB} Mo)")
            f.write(chunk)
    db.update(m["id"], status="queued", progress="En file d'attente")
    bg.add_task(pipeline.process, m["id"], audio_path=dest)
    return {"id": m["id"]}


class UrlIn(BaseModel):
    url: str
    title: str = ""
    meeting_date: str = ""
    location: str = ""
    participants: str = ""
    context: str = ""
    language: str = ""
    prefer_subtitles: bool = True


@app.post("/api/meetings/url")
def from_url(body: UrlIn, bg: BackgroundTasks):
    """Lien vidéo/audio de n'importe quelle source (YouTube, Vimeo, LinkedIn, lien direct…)."""
    if not body.url.lower().startswith(("http://", "https://")):
        raise HTTPException(422, "Le lien doit commencer par http:// ou https://")
    m = _create(body.title, body.meeting_date, body.location, body.participants, body.context, body.language,
                "url", body.url.strip())
    db.update(m["id"], status="queued", progress="En file d'attente")
    bg.add_task(pipeline.process, m["id"], url=body.url.strip(), prefer_subtitles=body.prefer_subtitles)
    return {"id": m["id"]}


class TextIn(BaseModel):
    text: str
    title: str = ""
    meeting_date: str = ""
    location: str = ""
    participants: str = ""
    context: str = ""
    language: str = ""


@app.post("/api/meetings/text")
def from_text(body: TextIn, bg: BackgroundTasks):
    """Transcription déjà disponible (Teams, Zoom, Otter…) : saute directement à la rédaction."""
    if not body.text.strip():
        raise HTTPException(422, "Texte vide")
    m = _create(body.title, body.meeting_date, body.location, body.participants, body.context, body.language, "text")
    db.update(m["id"], status="queued", transcript=body.text, progress="En file d'attente")
    bg.add_task(pipeline.process, m["id"], raw_text=body.text)
    return {"id": m["id"]}


# ------------------------------------------------------------------ lecture / édition
@app.get("/api/config")
def get_config():
    return {"transcribe_provider": transcribe.provider(), "has_anthropic": bool(config.ANTHROPIC_API_KEY),
            "has_openai": bool(config.OPENAI_API_KEY), "model": config.ANTHROPIC_MODEL,
            "keep_audio": config.KEEP_AUDIO}


@app.get("/api/meetings")
def list_meetings():
    return db.list_all()


@app.get("/api/meetings/{mid}")
def get_meeting(mid: str):
    return _meeting(mid)


class PatchIn(BaseModel):
    title: str | None = None
    meeting_date: str | None = None
    location: str | None = None
    participants: str | None = None
    context: str | None = None
    transcript: str | None = None
    analysis: dict | None = None


@app.patch("/api/meetings/{mid}")
def patch_meeting(mid: str, body: PatchIn):
    m = _meeting(mid)
    fields = body.model_dump(exclude_none=True)
    if "analysis" in fields:
        fields["analysis"] = generate.normalize(fields["analysis"], m)
    db.update(mid, **fields)
    return db.get(mid)


@app.post("/api/meetings/{mid}/regenerate")
def regenerate(mid: str, bg: BackgroundTasks):
    """Relance la rédaction à partir de la transcription (éventuellement corrigée)."""
    m = _meeting(mid)
    if not m.get("transcript"):
        raise HTTPException(409, "Pas de transcription disponible")
    db.update(mid, status="queued", progress="En file d'attente", error=None)
    bg.add_task(pipeline.process, mid, raw_text=m["transcript"])
    return {"id": mid}


@app.delete("/api/meetings/{mid}")
def delete_meeting(mid: str):
    _meeting(mid)
    db.delete(mid)
    return {"ok": True}


# ------------------------------------------------------------------ aperçu & exports
@app.get("/api/meetings/{mid}/preview/{doc_type}")
def preview(mid: str, doc_type: str):
    """Blocs du document tels qu'ils seront exportés (l'interface les affiche à l'identique)."""
    m = _meeting(mid)
    if not m.get("analysis"):
        raise HTTPException(409, "Analyse non disponible pour cette réunion")
    if doc_type not in exporters.BUILDERS:
        raise HTTPException(404, "Type de document inconnu")
    return exporters.BUILDERS[doc_type](m["analysis"])


@app.get("/api/meetings/{mid}/export/{doc_type}.{fmt}")
def export(mid: str, doc_type: str, fmt: str):
    m = _meeting(mid)
    if not m.get("analysis"):
        raise HTTPException(409, "Analyse non disponible pour cette réunion")
    try:
        data, mime, name = exporters.export(m["analysis"], doc_type, fmt, m.get("transcript"), branding.for_export())
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(io.BytesIO(data), media_type=mime,
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


# ------------------------------------------------------------------ gabarit (logo, en-tête)
@app.get("/api/branding")
def get_branding():
    return {**branding.get(), "has_logo": branding.logo_bytes() is not None}


@app.put("/api/branding")
def put_branding(body: dict):
    try:
        return {**branding.save(body), "has_logo": branding.logo_bytes() is not None}
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/branding/logo")
async def put_logo(file: UploadFile = File(...)):
    try:
        branding.save_logo(await file.read(branding.MAX_LOGO_BYTES + 1))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"has_logo": True}


@app.delete("/api/branding/logo")
def del_logo():
    branding.delete_logo()
    return {"has_logo": False}


@app.get("/api/branding/logo")
def get_logo():
    data = branding.logo_bytes()
    if data is None:
        raise HTTPException(404, "Aucun logo")
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
