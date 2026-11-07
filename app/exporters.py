"""Rendus PV / CR / Note de synthèse en PDF, Word (.docx) et Excel (.xlsx).

Chaque type de document est d'abord construit comme une liste de « blocs » neutres,
puis rendu par le moteur du format demandé : le contenu reste identique d'un format à l'autre.
"""
from __future__ import annotations

import io
import re
import unicodedata
from typing import Any
from xml.sax.saxutils import escape

DOC_TYPES = {"pv": "Procès-verbal", "cr": "Compte rendu", "note": "Note de synthèse",
             "deck": "Présentation", "deck_visual": "Présentation illustrée"}
DECKS = {"deck": False, "deck_visual": True}   # type → présentation illustrée ?
FORMATS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
NAVY = "1F3A5F"  # couleur par défaut ; surchargée par le gabarit (branding)
PRIO_ORDER = {"haute": 0, "moyenne": 1, "basse": 2}

from . import annexes, labels

Block = dict[str, Any]
DEFAULT_BRAND: dict[str, Any] = {"org_name": "", "header_right": "", "footer": "", "confidential": "",
                                 "color": NAVY, "logo": None, "logo_size": None}


def _has_header(brand: dict) -> bool:
    return bool(brand.get("logo") or brand.get("org_name") or brand.get("header_right"))


def _logo_dims(brand: dict, height: float, max_width: float) -> tuple[float, float]:
    """Dimensions (largeur, hauteur) du logo, hauteur cible bornée en largeur, ratio conservé."""
    lw, lh = brand["logo_size"]
    w, h = height * lw / lh, height
    if w > max_width:
        w, h = max_width, max_width * lh / lw
    return w, h


# ------------------------------------------------------------------ construction des blocs
def _meta(a: dict) -> Block:
    rows = [("Objet", a["objet"]), ("Date", a["date"]), ("Lieu / outil", a["lieu"])]
    return {"t": "meta", "rows": [(k, v) for k, v in rows if v]}


def _participants_table(a: dict) -> Block | None:
    if not a["participants"]:
        return None
    return {"t": "table", "name": "Participants", "headers": ["Nom", "Fonction", "Statut"],
            "widths": [0.4, 0.4, 0.2],
            "rows": [[p.get("nom", ""), p.get("fonction", ""), p.get("statut", "présent")] for p in a["participants"]]}


def _decisions_table(a: dict) -> Block | None:
    if not a["decisions"]:
        return None
    return {"t": "table", "name": "Décisions", "headers": ["N°", "Décision", "Responsable"],
            "widths": [0.08, 0.67, 0.25],
            "rows": [[str(i), annexes.cite(d.get("decision", ""), d.get("pj")), d.get("responsable", "") or "—"]
                     for i, d in enumerate(a["decisions"], 1)]}


def _actions_table(a: dict) -> Block | None:
    if not a["actions"]:
        return None
    acts = sorted(a["actions"], key=lambda x: PRIO_ORDER.get(x.get("priorite", "moyenne"), 1))
    return {"t": "table", "name": "Actions", "headers": ["N°", "Action", "Responsable", "Échéance", "Priorité"],
            "widths": [0.07, 0.43, 0.2, 0.17, 0.13],
            "rows": [[str(i), annexes.cite(x.get("action", ""), x.get("pj")), x.get("responsable", "") or "À définir",
                      x.get("echeance", "") or "À définir", (x.get("priorite") or "moyenne").capitalize()]
                     for i, x in enumerate(acts, 1)]}


def _add(blocks: list[Block], *items: Block | None) -> None:
    blocks.extend(i for i in items if i)


def _section(blocks: list[Block], title: str, content: Block | None) -> None:
    if content:
        blocks.append({"t": "h", "text": title})
        blocks.append(content)


def _bullets(items: list[str]) -> Block | None:
    items = [i for i in items if i]
    return {"t": "bullets", "items": items} if items else None


def build_pv(a: dict) -> list[Block]:
    b: list[Block] = [{"t": "title", "text": "PROCÈS-VERBAL DE RÉUNION"}, {"t": "subtitle", "text": a["titre"]}, _meta(a)]
    _section(b, "Participants", _participants_table(a))
    _section(b, "Ordre du jour", {"t": "numbered", "items": a["ordre_du_jour"]} if a["ordre_du_jour"] else None)
    if a["points_abordes"]:
        b.append({"t": "h", "text": "Délibérations"})
        for i, p in enumerate(a["points_abordes"], 1):
            b.append({"t": "h2", "text": f"{i}. {p.get('sujet', '')}"})
            if p.get("discussion"):
                b.append({"t": "p", "text": p["discussion"]})
            if annexes.tag(p.get("pj")):
                b.append({"t": "p", "text": annexes.sources_line(p["pj"], a)})
            if p.get("positions"):
                b.append({"t": "p", "text": "Positions exprimées :", "bold": True})
                b.append({"t": "bullets", "items": p["positions"]})
            if p.get("decisions"):
                b.append({"t": "p", "text": "Décision(s) :", "bold": True})
                b.append({"t": "bullets", "items": p["decisions"]})
    _section(b, "Relevé des décisions", _decisions_table(a))
    _section(b, "Plan d'actions", _actions_table(a))
    _section(b, "Suivi des actions antérieures", annexes.suivi_table(a))
    _section(b, "Recoupement avec les pièces jointes", annexes.recoupement_table(a))
    _section(b, "Points de vigilance", _bullets(a["risques_vigilance"]))
    _section(b, "Questions restées ouvertes", _bullets(a["questions_ouvertes"]))
    if a["prochaine_reunion"]:
        _section(b, "Prochaine réunion", {"t": "p", "text": a["prochaine_reunion"]})
    b.append({"t": "p", "text": "La séance est levée. Le présent procès-verbal est établi pour servir et valoir ce que de droit."})
    b.append({"t": "signatures", "labels": ["Le/la secrétaire de séance", "Le/la président(e) de séance"]})
    return b


def build_cr(a: dict) -> list[Block]:
    b: list[Block] = [{"t": "title", "text": "COMPTE RENDU DE RÉUNION"}, {"t": "subtitle", "text": a["titre"]}, _meta(a)]
    _section(b, "Participants", _participants_table(a))
    _section(b, "Résumé", {"t": "p", "text": a["resume"]} if a["resume"] else None)
    if a["points_abordes"]:
        b.append({"t": "h", "text": "Points abordés"})
        for p in a["points_abordes"]:
            b.append({"t": "h2", "text": p.get("sujet", "")})
            if p.get("discussion"):
                b.append({"t": "p", "text": p["discussion"]})
            if annexes.tag(p.get("pj")):
                b.append({"t": "p", "text": annexes.sources_line(p["pj"], a)})
    _section(b, "Décisions", _decisions_table(a))
    _section(b, "Actions à mener", _actions_table(a))
    _section(b, "Suivi des actions antérieures", annexes.suivi_table(a))
    _section(b, "Recoupement avec les pièces jointes", annexes.recoupement_table(a))
    _section(b, "Points de vigilance", _bullets(a["risques_vigilance"]))
    if a["prochaine_reunion"]:
        _section(b, "Prochaine réunion", {"t": "p", "text": a["prochaine_reunion"]})
    return b


def build_note(a: dict) -> list[Block]:
    b: list[Block] = [{"t": "title", "text": "NOTE DE SYNTHÈSE"}, {"t": "subtitle", "text": a["titre"]}, _meta(a)]
    _section(b, "Synthèse", {"t": "p", "text": a["resume"]} if a["resume"] else None)
    _section(b, "Enjeux", _bullets(a["enjeux"]))
    if a["points_abordes"]:
        _section(b, "Points clés", _bullets([
            annexes.cite(p.get("sujet", "") + (f" — {_first_sentence(p['discussion'])}" if p.get("discussion") else ""), p.get("pj"))
            for p in a["points_abordes"]]))
    _section(b, "Décisions prises", _bullets([d.get("decision", "") + (f" ({d['responsable']})" if d.get("responsable") else "")
                                              for d in a["decisions"]]))
    _section(b, "Risques et points de vigilance", _bullets(a["risques_vigilance"]))
    _section(b, "Recoupement avec les pièces jointes", annexes.recoupement_table(a))
    _section(b, "Suivi des actions antérieures", annexes.suivi_table(a))
    _section(b, "Actions prioritaires", _actions_table(a))
    _section(b, "Recommandations / arbitrages attendus", _bullets(a["recommandations"]))
    _section(b, "Questions ouvertes", _bullets(a["questions_ouvertes"]))
    return b


def _first_sentence(text: str, limit: int = 220) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip(), re.S)
    s = (m.group(1) if m else text.strip())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _localized(f):
    """Rend le builder indifférent à la langue : les intitulés fixes sont traduits selon la langue du rapport (`_lang`)."""
    def g(a: dict) -> list[Block]:
        return labels.tr_deep(f(a), labels.of(a))
    g.__name__ = f.__name__
    return g


BUILDERS = {"pv": _localized(build_pv), "cr": _localized(build_cr), "note": _localized(build_note)}


def _footer_text(a: dict, doc_type: str) -> str:
    return f"{labels.tr(DOC_TYPES[doc_type], labels.of(a))} — {a['titre']}" + (f" — {a['date']}" if a["date"] else "")


# ------------------------------------------------------------------ PDF
def render_pdf(blocks: list[Block], footer: str, brand: dict, assets: dict[str, bytes] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    navy = colors.HexColor("#" + brand["color"])
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=14.5, alignment=TA_JUSTIFY, spaceAfter=5)
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12, alignment=0, spaceAfter=0)
    cell_h = ParagraphStyle("cellh", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    st = {
        "title": ParagraphStyle("t", parent=ss["Title"], fontSize=20, textColor=navy, spaceAfter=4, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("s", parent=ss["Heading2"], fontSize=13, alignment=TA_CENTER, textColor=colors.HexColor("#444444"), spaceAfter=12),
        # keepWithNext : un titre n'est jamais seul en bas de page, séparé de son contenu
        "h": ParagraphStyle("h", parent=ss["Heading2"], fontSize=13, textColor=navy, spaceBefore=14, spaceAfter=6, keepWithNext=1),
        "h2": ParagraphStyle("h2", parent=ss["Heading3"], fontSize=11, textColor=colors.HexColor("#2d2d2d"), spaceBefore=8, spaceAfter=3, keepWithNext=1),
    }
    width = A4[0] - 4 * cm

    def para(text: str, style=body) -> Paragraph:
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    story: list = []
    for blk in blocks:
        t = blk["t"]
        if t in ("title", "subtitle"):
            story.append(Paragraph(escape(blk["text"]), st[t]))
        elif t in ("h", "h2"):
            story.append(Paragraph(escape(blk["text"]), st[t]))
        elif t == "p":
            txt = escape(blk["text"]).replace("\n", "<br/>")
            story.append(Paragraph(f"<b>{txt}</b>" if blk.get("bold") else txt, body))
        elif t in ("bullets", "numbered"):
            for i, it in enumerate(blk["items"], 1):
                mark = "•" if t == "bullets" else f"{i}."
                story.append(Paragraph(escape(it), ParagraphStyle("li", parent=body, leftIndent=16, bulletIndent=4, spaceAfter=2), bulletText=mark))
        elif t == "meta":
            data = [[Paragraph(f"<b>{escape(k)}</b>", cell), para(v, cell)] for k, v in blk["rows"]]
            if data:
                tb = Table(data, colWidths=[3.2 * cm, width - 3.2 * cm])
                tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                                        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
                story += [tb, Spacer(1, 6)]
        elif t == "table":
            data = [[Paragraph(escape(h), cell_h) for h in blk["headers"]]] + \
                   [[para(str(c), cell) for c in row] for row in blk["rows"]]
            tb = Table(data, colWidths=[w * width for w in blk["widths"]], repeatRows=1)
            tb.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), navy), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CF")),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            story += [tb, Spacer(1, 6)]
        elif t == "pagebreak":
            story.append(PageBreak())
        elif t == "image":
            data = (assets or {}).get(blk["id"])
            if data:
                iw, ih = blk.get("size") or (800, 600)
                scale = min(width / iw, 11 * cm / ih, 1.5)          # tient dans la page, sans trop agrandir les petites images
                story.append(RLImage(io.BytesIO(data), width=iw * scale, height=ih * scale))
                story.append(para(blk.get("caption", ""), cell))
                story.append(Spacer(1, 6))
        elif t == "signatures":
            cells = [[para(l, cell) for l in blk["labels"]], ["", ""]]
            tb = Table(cells, colWidths=[width / 2] * 2, rowHeights=[16, 2.2 * cm])
            tb.setStyle(TableStyle([("BOX", (0, 1), (0, 1), 0.4, colors.grey), ("BOX", (1, 1), (1, 1), 0.4, colors.grey)]))
            story += [Spacer(1, 18), KeepTogether(tb)]

    head = _has_header(brand)

    def decorate(canvas, doc):
        from reportlab.lib.utils import ImageReader
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, (brand["footer"] or footer)[:110])
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{labels.tr('Page', brand.get('_lang', 'fr'))} {doc.page}")
        if brand["confidential"]:
            canvas.setFillColor(colors.HexColor("#C0392B")); canvas.setFont("Helvetica-Bold", 8)
            canvas.drawCentredString(A4[0] / 2, 0.75 * cm, brand["confidential"])
        canvas.setStrokeColor(navy)
        canvas.setLineWidth(1.2)
        if head:
            x, base = 2 * cm, A4[1] - 2.3 * cm
            if brand["logo"]:
                w, h = _logo_dims(brand, 1.3 * cm, 5 * cm)
                canvas.drawImage(ImageReader(io.BytesIO(brand["logo"])), x, base + (1.3 * cm - h) / 2 + 0.2 * cm,
                                 width=w, height=h, mask="auto")
                x += w + 0.35 * cm
            if brand["org_name"]:
                canvas.setFillColor(navy); canvas.setFont("Helvetica-Bold", 12)
                canvas.drawString(x, base + 0.65 * cm, brand["org_name"])
            if brand["header_right"]:
                canvas.setFillColor(colors.grey); canvas.setFont("Helvetica", 8.5)
                canvas.drawRightString(A4[0] - 2 * cm, base + 0.65 * cm, brand["header_right"])
            canvas.line(2 * cm, base, A4[0] - 2 * cm, base)
        else:
            canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=3.2 * cm if head else 2.2 * cm, bottomMargin=2 * cm,
                      title=footer, author=brand["org_name"] or "GMeeting").build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()


# ------------------------------------------------------------------ Word
def render_docx(blocks: list[Block], footer: str, brand: dict, assets: dict[str, bytes] | None = None) -> bytes:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    navy = RGBColor.from_string(brand["color"])
    for name, size in (("Heading 1", 14), ("Heading 2", 12)):
        s = doc.styles[name]
        s.font.name, s.font.size, s.font.color.rgb = "Calibri", Pt(size), navy

    # pied de page
    fp = sec.footer.paragraphs[0]
    fp.text = (brand["footer"] or footer) + "  —  " + labels.tr("Page", brand.get("_lang", "fr")) + " "
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        run = fp.add_run()
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText"); el.text = txt
        run._r.append(el)
    for r in fp.runs:
        r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    if brand["confidential"]:
        cp = sec.footer.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = cp.add_run(brand["confidential"]); cr.bold = True; cr.font.size = Pt(8); cr.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)

    if _has_header(brand):
        hdr = sec.header
        tb = hdr.add_table(1, 2, Cm(17))
        lp = tb.cell(0, 0).paragraphs[0]
        if brand["logo"]:
            w, h = _logo_dims(brand, 1.3, 5)
            lp.add_run().add_picture(io.BytesIO(brand["logo"]), width=Cm(w), height=Cm(h))
        if brand["org_name"]:
            r = lp.add_run(("  " if brand["logo"] else "") + brand["org_name"])
            r.bold = True; r.font.size = Pt(12); r.font.color.rgb = navy
        rp = tb.cell(0, 1).paragraphs[0]; rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        rr = rp.add_run(brand["header_right"]); rr.font.size = Pt(8.5); rr.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
        tb.cell(0, 0).width, tb.cell(0, 1).width = Cm(10), Cm(7)
        line = hdr.add_paragraph()
        bdr = OxmlElement("w:pBdr"); bot = OxmlElement("w:bottom")
        for k, v in (("val", "single"), ("sz", "12"), ("space", "1"), ("color", brand["color"])):
            bot.set(qn("w:" + k), v)
        bdr.append(bot); line._p.get_or_add_pPr().append(bdr)
        first = hdr.paragraphs[0]._p
        first.getparent().remove(first)

    def shade(cell, hex_):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_)
        tcPr.append(shd)

    for blk in blocks:
        t = blk["t"]
        if t == "title":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(blk["text"]); r.bold = True; r.font.size = Pt(20); r.font.color.rgb = navy
        elif t == "subtitle":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(blk["text"]); r.font.size = Pt(13); r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        elif t == "h":
            doc.add_heading(blk["text"], level=1)
        elif t == "h2":
            doc.add_heading(blk["text"], level=2)
        elif t == "p":
            p = doc.add_paragraph(); r = p.add_run(blk["text"]); r.bold = bool(blk.get("bold"))
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif t in ("bullets", "numbered"):
            for it in blk["items"]:
                doc.add_paragraph(it, style="List Bullet" if t == "bullets" else "List Number")
        elif t == "meta":
            tb = doc.add_table(rows=0, cols=2)
            for k, v in blk["rows"]:
                row = tb.add_row().cells
                row[0].text, row[1].text = "", v
                row[0].paragraphs[0].add_run(k).bold = True
                row[0].width, row[1].width = Cm(3.2), Cm(13.8)
        elif t == "table":
            tb = doc.add_table(rows=1, cols=len(blk["headers"]))
            tb.style = "Table Grid"; tb.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, h in enumerate(blk["headers"]):
                c = tb.rows[0].cells[i]; c.text = ""
                r = c.paragraphs[0].add_run(h); r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255)
                shade(c, brand["color"])
            for n, row in enumerate(blk["rows"]):
                cells = tb.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = str(v)
                    if n % 2:
                        shade(cells[i], "F2F5F9")
            for row in tb.rows:
                for i, w in enumerate(blk["widths"]):
                    row.cells[i].width = Cm(17 * w)
            el = OxmlElement("w:tblHeader"); el.set(qn("w:val"), "true")
            tb.rows[0]._tr.get_or_add_trPr().append(el)
            doc.add_paragraph()
        elif t == "pagebreak":
            doc.add_page_break()
        elif t == "image":
            data = (assets or {}).get(blk["id"])
            if data:
                iw, ih = blk.get("size") or (800, 600)
                width_cm = min(16.0, 14.0 * iw / ih) if ih else 16.0     # largeur max 16 cm, hauteur max ≈ 14 cm
                doc.add_picture(io.BytesIO(data), width=Cm(width_cm))
                cp = doc.add_paragraph(); r = cp.add_run(blk.get("caption", "")); r.italic = True; r.font.size = Pt(9)
        elif t == "signatures":
            doc.add_paragraph()
            tb = doc.add_table(rows=2, cols=2); tb.style = "Table Grid"
            for i, l in enumerate(blk["labels"]):
                tb.rows[0].cells[i].text = l
                tb.rows[1].cells[i].text = "\n\n\n"
    buf = io.BytesIO(); doc.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ Excel
def render_xlsx(blocks: list[Block], title: str, transcript: str | None = None, brand: dict | None = None,
                assets: dict[str, bytes] | None = None) -> bytes:
    brand = brand or DEFAULT_BRAND
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active; ws.title = "Document"
    NAVY = brand["color"]
    head_fill = PatternFill("solid", fgColor=NAVY)
    white_bold = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="B8C2CF")
    wrap = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110

    def sheet_name(n: str) -> str:
        return re.sub(r"[\\/*?:\[\]]", "", n)[:31]

    row = 1
    used = {"Document"}
    if _has_header(brand):
        from openpyxl.drawing.image import Image as XLImage
        if brand["logo"]:
            w, h = _logo_dims(brand, 52, 190)
            img = XLImage(io.BytesIO(brand["logo"])); img.width, img.height = w, h
            ws.add_image(img, "A1")
        if brand["org_name"]:
            ws.cell(1, 2, brand["org_name"]).font = Font(bold=True, size=14, color=NAVY)
        if brand["header_right"]:
            ws.cell(2, 2, brand["header_right"]).font = Font(size=10, color="808080")
        for r_ in (1, 2, 3):
            ws.row_dimensions[r_].height = 20
        row = 5
    ws.oddFooter.left.text = brand["footer"] or title
    ws.oddFooter.right.text = labels.tr("Page", (brand or {}).get("_lang", "fr")) + " &P / &N"
    if brand["confidential"]:
        ws.oddFooter.center.text = brand["confidential"]
    for blk in blocks:
        t = blk["t"]
        if t == "title":
            ws.cell(row, 1, blk["text"]).font = Font(bold=True, size=16, color=NAVY); row += 1
        elif t == "subtitle":
            ws.cell(row, 1, blk["text"]).font = Font(size=12, color="444444"); row += 2
        elif t == "meta":
            for k, v in blk["rows"]:
                ws.cell(row, 1, k).font = Font(bold=True)
                c = ws.cell(row, 2, v); c.alignment = wrap; row += 1
            row += 1
        elif t in ("h", "h2"):
            c = ws.cell(row, 1, blk["text"]); c.font = Font(bold=True, size=12 if t == "h" else 11, color=NAVY); row += 1
        elif t == "p":
            c = ws.cell(row, 1, blk["text"]); c.alignment = wrap; c.font = Font(bold=bool(blk.get("bold")))
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            ws.row_dimensions[row].height = max(15, 15 * (len(blk["text"]) // 130 + 1 + blk["text"].count("\n")))
            row += 1
        elif t in ("bullets", "numbered"):
            for i, it in enumerate(blk["items"], 1):
                c = ws.cell(row, 1, ("• " if t == "bullets" else f"{i}. ") + it); c.alignment = wrap
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
                ws.row_dimensions[row].height = max(15, 15 * (len(it) // 130 + 1)); row += 1
        elif t == "table":
            name = sheet_name(blk["name"]); base = name; n = 2
            while name in used:
                name = f"{base[:28]}_{n}"; n += 1
            used.add(name)
            s = wb.create_sheet(name)
            for i, h in enumerate(blk["headers"], 1):
                c = s.cell(1, i, h); c.font = white_bold; c.fill = head_fill
                c.alignment = Alignment(vertical="center")
            for r_i, r_ in enumerate(blk["rows"], 2):
                for c_i, v in enumerate(r_, 1):
                    c = s.cell(r_i, c_i, v); c.alignment = wrap
                    c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            for i, w in enumerate(blk["widths"], 1):
                s.column_dimensions[get_column_letter(i)].width = max(10, round(w * 120))
            s.freeze_panes = "A2"
            s.auto_filter.ref = f"A1:{get_column_letter(len(blk['headers']))}{len(blk['rows']) + 1}"
            ws.cell(row, 1, labels.tr(f"→ voir l'onglet « {name} » ({len(blk['rows'])} ligne(s))", (brand or {}).get("_lang", "fr"))).font = Font(italic=True, color="666666"); row += 1
        elif t == "image":
            data = (assets or {}).get(blk["id"])
            if data:
                from openpyxl.drawing.image import Image as XLImage
                iw, ih = blk.get("size") or (800, 600)
                scale = min(1.0, 700 / iw, 420 / ih)
                img = XLImage(io.BytesIO(data)); img.width, img.height = iw * scale, ih * scale
                ws.add_image(img, f"A{row}")
                row += int(img.height / 20) + 2
        elif t in ("signatures", "pagebreak"):
            pass
    if transcript:
        _lg = (brand or {}).get("_lang", "fr")
        s = wb.create_sheet(labels.tr("Transcription", _lg))
        s.append([labels.tr("Horodatage", _lg), labels.tr("Texte", _lg)])
        for c in s[1]:
            c.font = white_bold; c.fill = head_fill
        for line in transcript.splitlines():
            m = re.match(r"\[(\d{2}:\d{2}:\d{2})\]\s*(.*)", line)
            s.append([m.group(1), m.group(2)] if m else ["", line])
        s.column_dimensions["A"].width = 12; s.column_dimensions["B"].width = 120
        for r in s.iter_rows(min_row=2):
            r[1].alignment = wrap
        s.freeze_panes = "A2"
    wb.properties.title = title
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ API publique
def export(analysis: dict, doc_type: str, fmt: str, transcript: str | None = None,
           brand: dict | None = None, attachments: list[dict] | None = None) -> tuple[bytes, str, str]:
    """Retourne (contenu, type MIME, nom de fichier)."""
    if doc_type not in BUILDERS and doc_type not in DECKS:
        raise ValueError(f"Type de document inconnu : {doc_type}")
    if fmt not in FORMATS:
        raise ValueError(f"Format inconnu : {fmt}")
    if (doc_type in DECKS) != (fmt == "pptx"):
        raise ValueError("Les présentations s'exportent en .pptx ; les autres documents en PDF, Word ou Excel.")
    brand = {**(brand or DEFAULT_BRAND), "_lang": labels.of(analysis)}
    footer = _footer_text(analysis, doc_type)
    if doc_type in DECKS:
        from . import pptx_export, slides
        visual = DECKS[doc_type]
        assets = {a["id"]: a["image_bytes"] for a in (attachments or []) if a.get("image_bytes")}
        data = pptx_export.render(slides.build_slides(analysis, visual, attachments or []), brand, visual, analysis["titre"], assets)
        ascii_title = unicodedata.normalize("NFKD", analysis["titre"]).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_title).strip("_")[:50] or "reunion"
        return data, FORMATS["pptx"], f"{'PRESENTATION_ILLUSTREE' if visual else 'PRESENTATION'}_{slug}.pptx"
    atts = attachments or []
    # Excel : tableaux d'annexes complets (un onglet chacun) ; PDF/Word : extraits lisibles
    blocks = BUILDERS[doc_type](analysis) + annexes.tail_blocks(atts, analysis, rows_limit=200 if fmt == "xlsx" else 25,
                                                                 cols_limit=20 if fmt == "xlsx" else 8)
    assets = {a["id"]: a["image_bytes"] for a in atts if a.get("image_bytes")}
    if fmt == "pdf":
        data = render_pdf(blocks, footer, brand, assets)
    elif fmt == "docx":
        data = render_docx(blocks, footer, brand, assets)
    else:
        data = render_xlsx(blocks, footer, transcript, brand, assets)
    ascii_title = unicodedata.normalize("NFKD", analysis["titre"]).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_title).strip("_")[:50] or "reunion"
    return data, FORMATS[fmt], f"{doc_type.upper()}_{slug}.{fmt}"
