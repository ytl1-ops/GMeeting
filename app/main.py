"""API FastAPI + service de l'interface web."""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import shutil

from fastapi import Request

from . import annexes, attachments, branding, config, db, exporters, generate, ingest, labels, pipeline, recordings, retention, security, slides, transcribe

STATIC = Path(__file__).parent / "static"


# Authentification (GMEETING_PASSWORD), en-têtes de sécurité et protection CSRF : un seul middleware qui couvre toutes les routes
# (l'interface statique comprise), sauf la sonde /healthz. Voir security.py.
app = FastAPI(title="GMeeting")
app.middleware("http")(security.middleware)
db.init()
db.recover_interrupted()
retention.schedule()


@app.get("/healthz")
def healthz():
    """Sonde pour Docker / supervision : base de données et ffmpeg. Aucune donnée de réunion."""
    try:
        db.list_all()
    except Exception:  # noqa: BLE001
        raise HTTPException(503, "Base de données indisponible")
    return {"status": "ok", "ffmpeg": bool(shutil.which("ffmpeg"))}


def _meeting(mid: str) -> dict:
    m = db.get(mid)
    if not m:
        raise HTTPException(404, "Réunion introuvable")
    return m


# ------------------------------------------------------------------ création
def _create(title, meeting_date, location, participants, context, language, source_type, source_url=None, **extra) -> dict:
    extra["report_lang"] = labels.norm(extra.get("report_lang"))
    return db.create(title=(title or "").strip(), meeting_date=meeting_date or None, location=location or None,
                     participants=participants or None, context=context or None,
                     language=(language or "").strip() or None, source_type=source_type, source_url=source_url, **extra)


@app.post("/api/meetings/audio")
async def from_audio(bg: BackgroundTasks, file: UploadFile = File(...), title: str = Form(""), meeting_date: str = Form(""),
                     location: str = Form(""), participants: str = Form(""), context: str = Form(""),
                     language: str = Form(""), source_type: str = Form("upload"), attachment_ids: str = Form(""),
                     report_lang: str = Form("")):
    """Enregistrement navigateur ou fichier audio/vidéo importé."""
    m = _create(title, meeting_date, location, participants, context, language, source_type, report_lang=report_lang)
    attachments.link([i for i in attachment_ids.split(",") if i], m["id"])
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
    report_lang: str = ""
    prefer_subtitles: bool = True
    attachment_ids: list[str] = []


@app.post("/api/meetings/url")
def from_url(body: UrlIn, bg: BackgroundTasks):
    """Lien vidéo/audio de n'importe quelle source (YouTube, Vimeo, LinkedIn, lien direct…)."""
    if not body.url.lower().startswith(("http://", "https://")):
        raise HTTPException(422, "Le lien doit commencer par http:// ou https://")
    m = _create(body.title, body.meeting_date, body.location, body.participants, body.context, body.language,
                "url", body.url.strip(), report_lang=body.report_lang)
    attachments.link(body.attachment_ids, m["id"])
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
    report_lang: str = ""
    attachment_ids: list[str] = []


@app.post("/api/meetings/text")
def from_text(body: TextIn, bg: BackgroundTasks):
    """Transcription déjà disponible (Teams, Zoom, Otter…) : saute directement à la rédaction."""
    if not body.text.strip():
        raise HTTPException(422, "Texte vide")
    m = _create(body.title, body.meeting_date, body.location, body.participants, body.context, body.language, "text", report_lang=body.report_lang)
    attachments.link(body.attachment_ids, m["id"])
    db.update(m["id"], status="queued", transcript=body.text, progress="En file d'attente")
    bg.add_task(pipeline.process, m["id"], raw_text=body.text)
    return {"id": m["id"]}


# ------------------------------------------------------------------ enregistrement continu
class RecStart(BaseModel):
    id: str | None = None           # identifiant généré par l'appareil (démarrage hors-ligne, mode avion)
    started_at: str | None = None   # ISO 8601 : vrai début de la réunion, même si l'envoi a lieu bien plus tard
    title: str = ""
    meeting_date: str = ""
    location: str = ""
    participants: str = ""
    context: str = ""
    language: str = ""
    report_lang: str = ""


@app.post("/api/recordings")
def rec_start(body: RecStart):
    """Ouvre une session d'enregistrement : l'audio arrive ensuite segment par segment."""
    extra: dict = {}
    if body.id is not None:
        if not re.fullmatch(r"[0-9a-f]{12}", body.id):
            raise HTTPException(422, "Identifiant invalide")
        existing = db.get(body.id)
        if existing:  # renvoi après coupure réseau : idempotent, jamais d'écrasement d'une autre réunion
            if existing["source_type"] == "record" and existing["status"] == "recording":
                return {"id": body.id}
            raise HTTPException(409, "Identifiant déjà utilisé")
        extra["id"] = body.id
    if body.started_at:
        try:
            dt = datetime.fromisoformat(body.started_at.replace("Z", "+00:00"))
            local = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
            extra["created_at"] = min(local, datetime.now()).isoformat(timespec="seconds")
        except ValueError:
            pass
    m = _create(body.title, body.meeting_date, body.location, body.participants, body.context, body.language, "record",
                report_lang=body.report_lang, **extra)
    db.update(m["id"], status="recording", progress="Enregistrement en cours")
    return {"id": m["id"]}


@app.put("/api/recordings/{mid}/parts/{part}/chunks/{seq}")
async def rec_chunk(mid: str, part: int, seq: int, request: Request):
    m = _meeting(mid)
    if m["status"] != "recording":
        raise HTTPException(409, "Cet enregistrement n'accepte plus de segments")
    if not (0 <= part < 1000 and 0 <= seq < 1_000_000):
        raise HTTPException(422, "Indices invalides")
    data = await request.body()
    if not data or len(data) > recordings.MAX_CHUNK_BYTES:
        raise HTTPException(422, "Segment vide ou trop volumineux")
    recordings.write_chunk(mid, part, seq, data)
    return {"ok": True}


class RecFinish(BaseModel):
    meta: dict[str, str] = {}
    markers: list[float] = []
    interruptions: list[dict] = []
    attachment_ids: list[str] = []


@app.post("/api/recordings/{mid}/finish")
def rec_finish(mid: str, body: RecFinish, bg: BackgroundTasks):
    """Termine l'enregistrement et lance transcription + rédaction. Rejouable après un échec."""
    m = _meeting(mid)
    if m["status"] not in ("recording", "error"):
        raise HTTPException(409, "Enregistrement déjà en cours de traitement ou terminé")
    if recordings.info(mid)["chunks"] == 0:
        raise HTTPException(409, "Aucun audio reçu pour cet enregistrement")
    fields = {k: v.strip() for k, v in body.meta.items()
              if k in {"title", "meeting_date", "location", "participants", "context", "language", "report_lang"} and v.strip()}
    if "report_lang" in fields:
        fields["report_lang"] = labels.norm(fields["report_lang"])
    attachments.link(body.attachment_ids, mid)
    notes = recordings.session_notes(body.markers, body.interruptions)
    if notes and "Moments marqués" not in (m.get("context") or "") and "Interruptions techniques" not in (m.get("context") or ""):
        fields["context"] = ((fields.get("context") or m.get("context") or "") + "\n\n" + notes).strip()
    db.update(mid, status="queued", progress="En file d'attente", error=None, **fields)
    bg.add_task(pipeline.process, mid, recording=True)
    return {"id": mid}


# ------------------------------------------------------------------ lecture / édition
@app.get("/api/config")
def get_config():
    return {"transcribe_provider": transcribe.provider(), "has_anthropic": bool(config.ANTHROPIC_API_KEY),
            "has_openai": bool(config.OPENAI_API_KEY), "model": config.ANTHROPIC_MODEL,
            "keep_audio": config.KEEP_AUDIO, "retention_days": config.RETENTION_DAYS, "audio_kbps": config.AUDIO_KBPS, "audio_enhance": config.AUDIO_ENHANCE}


@app.get("/api/privacy")
def get_privacy(request: Request):
    """État RÉEL de la protection des données de CE serveur (affiché par la page « Confidentialité »). Aucun secret, que des faits."""
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").split(",")[0].strip().lower()
    prov = transcribe.provider()
    return {
        "password_set": bool(config.PASSWORD),
        "https": proto == "https",
        "ai_drafting": {"enabled": bool(config.ANTHROPIC_API_KEY), "provider": "anthropic"},
        "transcription": {"provider": prov, "audio_leaves_server": prov != "local"},
        "retention_days": config.RETENTION_DAYS,
        "keep_audio": config.KEEP_AUDIO,
        "staging_hours": 24,
    }


@app.get("/api/meetings")
def list_meetings():
    return db.list_all()


@app.get("/api/meetings/{mid}")
def get_meeting(mid: str):
    m = _meeting(mid)
    if m["status"] == "recording":
        m["rec_info"] = recordings.info(mid)
    m["has_audio"] = _archive(mid).exists()
    m["atts_stale"] = attachments.is_stale(mid, bool(m.get("analysis")) and m["status"] == "done")   # pièces modifiées depuis la rédaction
    return m


def _archive(mid: str) -> Path:
    return config.ARCHIVE_DIR / f"{mid}{ingest.AUDIO_EXT}"


@app.get("/api/meetings/{mid}/audio")
def meeting_audio(mid: str):
    """Réécoute de l'enregistrement (si KEEP_AUDIO) : fichier Opus compact, lecture par plages (avance/retour)."""
    _meeting(mid)
    if not _archive(mid).exists():
        raise HTTPException(404, "Aucun audio conservé pour cette réunion (activez KEEP_AUDIO)")
    return FileResponse(_archive(mid), media_type="audio/ogg")


class PatchIn(BaseModel):
    title: str | None = None
    meeting_date: str | None = None
    location: str | None = None
    participants: str | None = None
    context: str | None = None
    transcript: str | None = None
    analysis: dict | None = None
    report_lang: str | None = None


@app.patch("/api/meetings/{mid}")
def patch_meeting(mid: str, body: PatchIn):
    m = _meeting(mid)
    fields = body.model_dump(exclude_none=True)
    if "report_lang" in fields:
        fields["report_lang"] = labels.norm(fields["report_lang"])
        m = {**m, "report_lang": fields["report_lang"]}
    if "analysis" in fields:
        fields["analysis"] = generate.normalize(fields["analysis"], m)
    db.update(mid, **fields)
    return db.get(mid)


@app.post("/api/meetings/{mid}/retry")
def retry(mid: str, bg: BackgroundTasks):
    """Relance un traitement en erreur à partir de ce qui a été conservé : transcription, enregistrement, lien ou fichier importé."""
    m = _meeting(mid)
    if m["status"] != "error":
        raise HTTPException(409, "Seul un traitement en erreur peut être relancé")
    kw: dict
    if m.get("transcript"):
        kw = {"raw_text": m["transcript"]}
    elif m["source_type"] == "record" and recordings.info(mid)["chunks"]:
        kw = {"recording": True}
    elif m.get("source_url"):
        kw = {"url": m["source_url"]}
    else:
        files = sorted((config.AUDIO_DIR / mid).glob("upload*")) if (config.AUDIO_DIR / mid).is_dir() else []
        if not files:
            raise HTTPException(409, "Rien à relancer : l'audio d'origine n'est plus disponible")
        kw = {"audio_path": files[0]}
    db.update(mid, status="queued", progress="En file d'attente", error=None)
    bg.add_task(pipeline.process, mid, **kw)
    return {"id": mid}


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
    shutil.rmtree(config.AUDIO_DIR / mid, ignore_errors=True)
    _archive(mid).unlink(missing_ok=True)
    attachments.delete_for_meeting(mid)
    return {"ok": True}


# ------------------------------------------------------------------ aperçu & exports
@app.get("/api/meetings/{mid}/preview/{doc_type}")
def preview(mid: str, doc_type: str, annexes_on: int = Query(1, alias="annexes")):
    """Blocs du document tels qu'ils seront exportés (l'interface les affiche à l'identique)."""
    m = _meeting(mid)
    if not m.get("analysis"):
        raise HTTPException(409, "Analyse non disponible pour cette réunion")
    atts = attachments.for_report(mid) if annexes_on else []
    if doc_type in exporters.DECKS:      # présentations : liste de diapositives (même modèle que le fichier .pptx)
        visual = exporters.DECKS[doc_type]
        return {"slides": slides.build_slides(m["analysis"], visual, atts), "visual": visual}
    if doc_type not in exporters.BUILDERS:
        raise HTTPException(404, "Type de document inconnu")
    return exporters.BUILDERS[doc_type](m["analysis"]) + annexes.tail_blocks(atts, m["analysis"])


@app.get("/api/meetings/{mid}/export/{doc_type}.{fmt}")
def export(mid: str, doc_type: str, fmt: str, annexes_on: int = Query(1, alias="annexes")):
    m = _meeting(mid)
    if not m.get("analysis"):
        raise HTTPException(409, "Analyse non disponible pour cette réunion")
    try:
        atts = attachments.with_image_bytes(attachments.for_report(mid)) if annexes_on else []
        data, mime, name = exporters.export(m["analysis"], doc_type, fmt, m.get("transcript"), branding.for_export(), atts)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(io.BytesIO(data), media_type=mime,
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


# ------------------------------------------------------------------ pièces jointes
def _att(aid: str) -> dict:
    a = db.att_get(aid) if attachments.valid_id(aid) else None
    if not a:
        raise HTTPException(404, "Pièce jointe introuvable")
    return a


@app.post("/api/attachments")
def upload_attachments(files: list[UploadFile] = File(...), meeting_id: str = Form("")):
    """Dépose des pièces jointes (e-mails Outlook, Word, Excel, PDF, PowerPoint, texte, images).
    Sans meeting_id : zone d'attente, rattachée à la réunion à sa création (attachment_ids)."""
    mid = meeting_id.strip() or None
    if mid:
        _meeting(mid)
    done, errors = [], []
    for f in files[: config.MAX_ATTACH_PER_MEETING]:
        try:
            done.append(attachments.public(attachments.save(f.file, f.filename or "fichier", mid)))
        except attachments.AttachmentError as e:
            errors.append(str(e))
    if not done and errors:
        raise HTTPException(422, " ".join(errors))
    return {"attachments": done, "errors": errors}


@app.get("/api/meetings/{mid}/attachments")
def list_attachments(mid: str):
    _meeting(mid)
    return [attachments.public(a) for a in db.att_list(mid)]


class AttPatch(BaseModel):
    included: bool | None = None
    name: str | None = None


@app.patch("/api/attachments/{aid}")
def patch_attachment(aid: str, body: AttPatch):
    _att(aid)
    fields = {}
    if body.included is not None:
        fields["included"] = body.included
    if body.name:
        fields["name"] = attachments.clean_name(body.name)
    if fields:
        db.att_update(aid, **fields)
    return attachments.public(_att(aid))


@app.delete("/api/attachments/{aid}")
def delete_attachment(aid: str):
    _att(aid)
    attachments.delete(aid)
    return {"ok": True}


@app.get("/api/attachments/{aid}/content")
def attachment_content(aid: str):
    """Contenu extrait (texte, tableaux, en-têtes de mail) pour contrôle avant intégration au rapport."""
    a = _att(aid)
    x = a["extract"]
    return {**attachments.public(a), "text": x.get("text", ""), "tables_data": x.get("tables", [])}


@app.get("/api/attachments/{aid}/file")
def attachment_file(aid: str):
    """Fichier d'origine, en téléchargement forcé (jamais interprété par le navigateur)."""
    a = _att(aid)
    p = attachments.original_path(a)
    if not p.exists():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(p, filename=a["name"], content_disposition_type="attachment",
                        media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff"})


@app.get("/api/attachments/{aid}/image")
def attachment_image(aid: str):
    a = _att(aid)
    p = attachments.image_path(a)
    if not a["extract"].get("image") or not p.exists():
        raise HTTPException(404, "Pas d'image")
    return FileResponse(p, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


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
