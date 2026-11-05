"""Pièces jointes d'une réunion : réception, extraction du contenu et stockage.

Formats lus : e-mails Outlook (.msg) et standards (.eml), Word (.docx), Excel (.xlsx/.xlsm) et CSV, PDF, PowerPoint (.pptx),
texte (.txt/.md/.log), images (png/jpg/gif/webp). Les autres fichiers sont conservés mais leur contenu n'est pas extrait.

Sécurité : un fichier joint est une donnée non fiable.
  * jamais exécuté (macros Excel/Word ignorées), jamais interprété par le navigateur (téléchargement forcé, nosniff) ;
  * exécutables et scripts refusés ; taille limitée ; archives Office contrôlées (zip-bombe) ;
  * images ré-encodées en PNG (métadonnées et contenu actif supprimés) ;
  * le texte extrait est transmis au modèle comme DONNÉE de référence, jamais comme instruction (voir generate.py).
"""
from __future__ import annotations

import csv
import email
import email.policy
import html
import io
import re
import shutil
import zipfile
from datetime import date, datetime, time
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import config, db

BLOCKED_EXT = {".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".dll", ".jar", ".js", ".vbs", ".ps1", ".sh", ".apk", ".lnk", ".reg", ".hta", ".cpl"}
KINDS = {
    ".msg": ("email", "E-mail Outlook (.msg)"), ".eml": ("email", "E-mail (.eml)"),
    ".docx": ("word", "Document Word"), ".xlsx": ("excel", "Classeur Excel"), ".xlsm": ("excel", "Classeur Excel"),
    ".csv": ("excel", "Fichier CSV"), ".pdf": ("pdf", "Document PDF"), ".pptx": ("powerpoint", "Présentation PowerPoint"),
    ".txt": ("texte", "Texte"), ".md": ("texte", "Texte"), ".log": ("texte", "Texte"),
    ".png": ("image", "Image"), ".jpg": ("image", "Image"), ".jpeg": ("image", "Image"), ".gif": ("image", "Image"), ".webp": ("image", "Image"),
}
LEGACY = {".doc": "Word 97-2003", ".xls": "Excel 97-2003", ".ppt": "PowerPoint 97-2003"}
MAX_STORED_TEXT = 60_000
MAX_TABLE_ROWS, MAX_TABLE_COLS, MAX_SHEETS, MAX_PDF_PAGES = 200, 20, 8, 30
IMG_MAX = (1600, 1600)
_ID = re.compile(r"[0-9a-f]{12}")


class AttachmentError(ValueError):
    """Pièce jointe refusée (message affichable à l'utilisateur)."""


def valid_id(x: str) -> bool:
    return bool(_ID.fullmatch(x or ""))


# ------------------------------------------------------------------ utilitaires
def clean_name(name: str) -> str:
    n = Path((name or "fichier").replace("\\", "/")).name
    n = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", n).strip(" .") or "fichier"
    return n[:120]


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y") if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, time):
        return v.strftime("%H:%M")
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:.6g}"
    return re.sub(r"\s+", " ", str(v)).strip()[:300]


def _table(name: str, raw_rows: list[list[Any]], truncated: bool) -> dict | None:
    rows = [[_cell(c) for c in r][:MAX_TABLE_COLS] for r in raw_rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    headers = [h or f"Col. {i + 1}" for i, h in enumerate(rows[0])]
    body = rows[1:MAX_TABLE_ROWS + 1]
    return {"name": name, "headers": headers, "rows": body, "truncated": truncated or len(rows) - 1 > MAX_TABLE_ROWS,
            "total_rows": len(rows) - 1}


class _Html2Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append("  ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(src: str) -> str:
    p = _Html2Text()
    try:
        p.feed(src)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", src)
    return tidy("".join(p.out))


def tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _safe_zip(path: Path) -> None:
    """Refuse les archives Office qui se décompresseraient démesurément (zip-bombe)."""
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 5000 or sum(i.file_size for i in infos) > 300 * 1024 * 1024 or any(i.file_size > 120 * 1024 * 1024 for i in infos):
                raise AttachmentError("Fichier Office trop volumineux une fois décompressé.")
    except zipfile.BadZipFile:
        raise AttachmentError("Fichier corrompu ou format non reconnu.")


# ------------------------------------------------------------------ extracteurs (chacun renvoie un dict)
def _mail_meta(sender: str, to: str, cc: str, when: str, subject: str) -> dict[str, str]:
    return {k: v for k, v in (("De", sender), ("À", to), ("Cc", cc), ("Date", when), ("Objet", subject)) if v}


def _fmt_date(d: datetime | None) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if d else ""


def _x_eml(path: Path) -> dict:
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)
    body = msg.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        raw = body.get_content()
        text = tidy(raw) if body.get_content_type() == "text/plain" else html_to_text(raw)
    try:
        when = _fmt_date(parsedate_to_datetime(str(msg["Date"]))) if msg["Date"] else ""
    except (TypeError, ValueError):
        when = str(msg["Date"] or "")
    atts = [a.get_filename() or "sans nom" for a in msg.iter_attachments()]
    return {"meta": _mail_meta(str(msg["From"] or ""), str(msg["To"] or ""), str(msg["Cc"] or ""), when, str(msg["Subject"] or "")),
            "text": text, "mail_attachments": atts}


def _x_msg(path: Path) -> dict:
    try:
        import extract_msg
    except ImportError:
        raise AttachmentError("La lecture des .msg nécessite le paquet « extract-msg » (pip install extract-msg) ; enregistrez le mail au format .eml en attendant.")
    with extract_msg.openMsg(str(path)) as m:
        body = m.body
        if not body:
            h = m.htmlBody
            body = html_to_text(h.decode("utf-8", "replace") if isinstance(h, bytes) else (h or "")) if h else ""
        to = m.to or (m.getStringStream("__substg1.0_0E04") or "")
        cc = m.cc or (m.getStringStream("__substg1.0_0E03") or "")
        atts = [(a.longFilename or a.shortFilename or "sans nom") for a in m.attachments]
        when = _fmt_date(m.date) if isinstance(m.date, datetime) else str(m.date or "")
        return {"meta": _mail_meta(str(m.sender or ""), str(to or ""), str(cc or ""), when, str(m.subject or "")),
                "text": tidy(body or ""), "mail_attachments": atts}


def _x_docx(path: Path) -> dict:
    _safe_zip(path)
    from docx import Document
    doc = Document(str(path))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    tables = []
    for i, t in enumerate(doc.tables[:6], 1):
        rows = [[c.text for c in r.cells] for r in t.rows[:MAX_TABLE_ROWS + 2]]
        tb = _table(f"Tableau {i}", rows, len(t.rows) > MAX_TABLE_ROWS + 1)
        if tb:
            tables.append(tb)
    meta = {}
    if doc.core_properties.title:
        meta["Titre"] = doc.core_properties.title
    if doc.core_properties.author:
        meta["Auteur"] = doc.core_properties.author
    return {"meta": meta, "text": "\n".join(paras), "tables": tables}


def _x_xlsx(path: Path) -> dict:
    _safe_zip(path)
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True, keep_vba=False)   # valeurs calculées, macros jamais exécutées
    tables, names = [], wb.sheetnames
    for name in names[:MAX_SHEETS]:
        ws = wb[name]
        rows, truncated = [], False
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if i > 5000:
                truncated = True
                break
            rows.append(list(r))
        tb = _table(name, rows, truncated)
        if tb:
            tables.append(tb)
    wb.close()
    note = f"{len(names) - MAX_SHEETS} feuille(s) supplémentaire(s) non extraite(s)." if len(names) > MAX_SHEETS else ""
    return {"meta": {"Feuilles": ", ".join(names[:MAX_SHEETS])}, "text": "", "tables": tables, "note": note}


def _x_csv(path: Path) -> dict:
    raw = path.read_bytes()[:2_000_000]
    for enc in ("utf-8-sig", "cp1252"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(txt[:4096], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO(txt), dialect)):
        if i > 5000:
            break
        rows.append(r)
    tb = _table(path.stem[:31] or "CSV", rows, len(rows) > MAX_TABLE_ROWS + 1)
    return {"meta": {}, "text": "", "tables": [tb] if tb else []}


def _x_pdf(path: Path) -> dict:
    from pypdf import PdfReader
    r = PdfReader(str(path))
    if r.is_encrypted:
        return {"meta": {}, "text": "", "note": "PDF protégé par mot de passe : contenu non extrait."}
    pages = []
    for p in r.pages[:MAX_PDF_PAGES]:
        try:
            pages.append((p.extract_text() or "").strip())
        except Exception:  # noqa: BLE001
            pages.append("")
    text = tidy("\n\n".join(t for t in pages if t))
    note = ""
    if not text:
        note = "PDF sans texte extractible (document scanné ?) : contenu non extrait."
    elif len(r.pages) > MAX_PDF_PAGES:
        note = f"Seules les {MAX_PDF_PAGES} premières pages sur {len(r.pages)} ont été lues."
    meta = {"Pages": str(len(r.pages))}
    if r.metadata and r.metadata.title:
        meta["Titre"] = str(r.metadata.title)
    return {"meta": meta, "text": text, "note": note}


def _x_pptx(path: Path) -> dict:
    _safe_zip(path)
    from pptx import Presentation
    prs = Presentation(str(path))
    out = []
    for i, sl in enumerate(prs.slides, 1):
        parts = [sh.text_frame.text.strip() for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        if sl.has_notes_slide and sl.notes_slide.notes_text_frame.text.strip():
            parts.append("Notes : " + sl.notes_slide.notes_text_frame.text.strip())
        if parts:
            out.append(f"Diapositive {i} : " + " / ".join(parts))
    return {"meta": {"Diapositives": str(len(prs.slides))}, "text": "\n".join(out)}


def _x_text(path: Path) -> dict:
    raw = path.read_bytes()[:2_000_000]
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return {"meta": {}, "text": tidy(raw.decode(enc))}
        except UnicodeDecodeError:
            continue
    return {"meta": {}, "text": tidy(raw.decode("utf-8", "replace"))}


def _x_image(path: Path, dest_png: Path) -> dict:
    from PIL import Image, ImageOps
    try:
        im = Image.open(path)
        im.load()
    except Exception:  # noqa: BLE001  (inclut DecompressionBombError)
        raise AttachmentError("Image illisible ou trop grande.")
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    im = im.convert("RGBA")
    im.thumbnail(IMG_MAX)
    im.save(dest_png, "PNG", optimize=True)
    return {"meta": {"Dimensions": f"{w} × {h} px"}, "text": "", "image": True, "image_size": list(im.size)}


EXTRACTORS = {".eml": _x_eml, ".msg": _x_msg, ".docx": _x_docx, ".xlsx": _x_xlsx, ".xlsm": _x_xlsx, ".csv": _x_csv,
              ".pdf": _x_pdf, ".pptx": _x_pptx, ".txt": _x_text, ".md": _x_text, ".log": _x_text}


def snippet_of(kind: str, x: dict) -> str:
    """Aperçu court pour les listes : ce qu'il faut savoir en un coup d'œil."""
    meta, text, tables = x.get("meta", {}), x.get("text", ""), x.get("tables", [])
    if kind == "email":
        return (f"{meta.get('Objet', '')} — " if meta.get("Objet") else "") + re.sub(r"\s+", " ", text)[:180]
    if kind == "excel" and tables:
        return " ; ".join(f"{t['name']} : {t['total_rows']} ligne(s) × {len(t['headers'])} col." for t in tables[:3])
    if kind == "image":
        return meta.get("Dimensions", "Image")
    s = re.sub(r"\s+", " ", text)[:220]
    if not s and tables:
        s = f"{len(tables)} tableau(x)"
    return s or x.get("note", "") or "Contenu non extrait"


# ------------------------------------------------------------------ stockage
def _dir(aid: str) -> Path:
    return config.ATTACH_DIR / aid


def original_path(att: dict) -> Path:
    return _dir(att["id"]) / ("original" + Path(att["name"]).suffix.lower())


def image_path(att: dict) -> Path:
    return _dir(att["id"]) / "image.png"


def save(fileobj, filename: str, meeting_id: str | None) -> dict:
    """Enregistre et analyse une pièce jointe. Lève AttachmentError (message affichable) si refusée."""
    name = clean_name(filename)
    ext = Path(name).suffix.lower()
    if ext in BLOCKED_EXT:
        raise AttachmentError(f"« {name} » : les fichiers exécutables ou scripts ne sont pas acceptés.")
    if db.att_count(meeting_id) >= config.MAX_ATTACH_PER_MEETING + (10 if meeting_id is None else 0):
        raise AttachmentError(f"Trop de pièces jointes (maximum {config.MAX_ATTACH_PER_MEETING} par réunion).")
    kind, label = KINDS.get(ext, ("autre", LEGACY.get(ext, "Fichier")))
    purge_stale()

    rec = db.att_create(meeting_id=meeting_id, name=name, kind=kind, label=label, size=0, snippet="", extract={})
    d = _dir(rec["id"])
    d.mkdir(parents=True, exist_ok=True)
    dest = d / ("original" + ext)
    size, limit = 0, config.MAX_ATTACH_MB * 1024 * 1024
    try:
        with open(dest, "wb") as out:
            while chunk := fileobj.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    raise AttachmentError(f"« {name} » dépasse {config.MAX_ATTACH_MB} Mo.")
                out.write(chunk)
        if size == 0:
            raise AttachmentError(f"« {name} » est vide.")
        try:
            if kind == "image":
                x = _x_image(dest, d / "image.png")
            elif kind in ("email", "word", "excel", "pdf", "powerpoint", "texte"):
                x = EXTRACTORS[ext](dest)
            else:
                x = {"meta": {}, "text": "", "note": f"Format {label} : conservé tel quel, contenu non extrait." + (
                    " Enregistrez-le en .docx/.xlsx/.pptx pour qu'il soit lu." if ext in LEGACY else "")}
        except AttachmentError:
            raise
        except Exception as e:  # noqa: BLE001  (fichier corrompu : on le garde mais sans contenu)
            x = {"meta": {}, "text": "", "note": f"Contenu illisible ({type(e).__name__}) : conservé tel quel."}
        x["text"] = (x.get("text") or "")[:MAX_STORED_TEXT]
        x["kind"], x["label"] = kind, label
        db.att_update(rec["id"], size=size, snippet=snippet_of(kind, x)[:300], extract=x)
    except Exception:
        delete(rec["id"])
        raise
    return db.att_get(rec["id"])  # type: ignore[return-value]


def delete(aid: str) -> None:
    db.att_delete(aid)
    shutil.rmtree(_dir(aid), ignore_errors=True)


def delete_for_meeting(mid: str) -> None:
    for a in db.att_list(mid):
        delete(a["id"])


def purge_stale() -> None:
    for aid in db.att_stale_staging():
        delete(aid)


def link(ids: list[str], mid: str) -> list[str]:
    return db.att_link([i for i in ids if valid_id(i)][:config.MAX_ATTACH_PER_MEETING], mid)


def public(a: dict) -> dict:
    x = a.get("extract", {})
    return {"id": a["id"], "meeting_id": a["meeting_id"], "name": a["name"], "kind": a["kind"], "label": a["label"], "size": a["size"],
            "snippet": a["snippet"], "included": a["included"], "created_at": a["created_at"], "meta": x.get("meta", {}),
            "tables": [{"name": t["name"], "rows": t["total_rows"], "cols": len(t["headers"])} for t in x.get("tables", [])],
            "has_image": bool(x.get("image")), "note": x.get("note", ""), "mail_attachments": x.get("mail_attachments", []),
            "has_text": bool(x.get("text"))}


# ------------------------------------------------------------------ usage : rédaction et rendus
def for_report(mid: str) -> list[dict]:
    """Pièces incluses d'une réunion, avec le contenu nécessaire (les octets d'image sont chargés à la demande par le rendu)."""
    out = []
    for a in db.att_list(mid):
        if a["included"]:
            out.append(a)
    return out


def with_image_bytes(atts: list[dict]) -> list[dict]:
    res = []
    for a in atts:
        b = None
        if a["extract"].get("image"):
            try:
                b = image_path(a).read_bytes()
            except OSError:
                b = None
        res.append({**a, "image_bytes": b})
    return res


def context_text(atts: list[dict], budget: int | None = None) -> str:
    """Texte des pièces jointes pour le modèle de rédaction, réparti équitablement dans le budget."""
    if not atts:
        return ""
    budget = budget or config.ATTACH_CONTEXT_CHARS
    per = max(3000, budget // len(atts))
    blocks = []
    for i, a in enumerate(atts, 1):
        x = a["extract"]
        head = f"[PJ {i}] « {a['name']} » — {a['label']}"
        meta = "\n".join(f"{k} : {v}" for k, v in x.get("meta", {}).items())
        body = x.get("text", "")
        tables = ""
        for t in x.get("tables", [])[:4]:
            lines = [" | ".join(t["headers"])] + [" | ".join(r) for r in t["rows"][:60]]
            tables += f"\nTableau « {t['name']} » ({t['total_rows']} ligne(s)) :\n" + "\n".join(lines)
        if x.get("mail_attachments"):
            meta += "\nPièces jointes du message : " + ", ".join(x["mail_attachments"])
        text = (meta + "\n\n" + body + tables).strip() or x.get("note", "(contenu non extrait)")
        blocks.append(head + "\n" + (text[:per] + ("\n[…tronqué]" if len(text) > per else "")))
    return "\n\n".join(blocks)
