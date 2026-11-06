"""Fabrique de vraies pièces jointes de test (Word, Excel, PDF, PowerPoint, e-mails .eml/.msg, images, CSV)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from email.message import EmailMessage

from tests.msgbuild import build_msg


def docx_bytes() -> bytes:
    from docx import Document
    d = Document(); d.core_properties.title = "Compte rendu précédent"; d.core_properties.author = "Awa Koné"
    d.add_heading("Réunion du 3 octobre", 1); d.add_paragraph("Le budget vidéoprotection a été fixé à 95 k€ sous réserve de devis.")
    d.add_paragraph("Action reportée : cartographie des angles morts.")
    t = d.add_table(rows=3, cols=2)
    for i, (a, b) in enumerate([("Poste", "Montant"), ("Caméras", "60 000"), ("Câblage", "35 000")]):
        t.cell(i, 0).text, t.cell(i, 1).text = a, b
    buf = io.BytesIO(); d.save(buf); return buf.getvalue()


def xlsx_bytes(rows: int = 5) -> bytes:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Budget"
    ws.append(["Poste", "Montant", "Date", "Validé"])
    for i in range(rows):
        ws.append([f"Ligne {i + 1}", 1234.5 if i % 2 else 1000.0, datetime(2026, 11, 3 + i % 20), bool(i % 2)])
    ws2 = wb.create_sheet("Notes"); ws2.append(["Remarque"]); ws2.append(["Devis n°2 attendu"])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def pdf_bytes(text: str = "Rapport d'audit du site Nord. Trois écarts mineurs relevés.") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
    if text:
        c.drawString(72, 750, text)
    c.showPage(); c.save(); return buf.getvalue()


def pptx_bytes() -> bytes:
    from pptx import Presentation
    p = Presentation(); s = p.slides.add_slide(p.slide_layouts[1]); s.shapes.title.text = "Plan 2027"
    s.placeholders[1].text = "Renouveler 40 caméras"; s.notes_slide.notes_text_frame.text = "Insister sur le calendrier"
    buf = io.BytesIO(); p.save(buf); return buf.getvalue()


def eml_bytes() -> bytes:
    m = EmailMessage()
    m["From"] = "Awa Koné <awa@example.org>"; m["To"] = "Marc Dubois <marc@example.org>, Léa Martin <lea@example.org>"
    m["Cc"] = "direction@example.org"; m["Subject"] = "Ordre du jour du COPIL"; m["Date"] = "Mon, 03 Nov 2026 09:30:00 +0100"
    m.set_content("Bonjour,\n\nVoici l'ordre du jour : bilan T3, budget 2027.\n\nCordialement")
    m.add_attachment(b"%PDF-fake", maintype="application", subtype="pdf", filename="ordre_du_jour.pdf")
    return m.as_bytes()


def eml_html_only_bytes() -> bytes:
    m = EmailMessage(); m["From"] = "x@example.org"; m["To"] = "y@example.org"; m["Subject"] = "HTML"
    m.set_content("<html><head><style>p{color:red}</style></head><body><p>Bonjour <b>Marc</b></p><script>alert(1)</script><ul><li>Point A</li><li>Point B</li></ul></body></html>", subtype="html")
    return m.as_bytes()


def msg_file(path) -> None:
    build_msg(path, "Ordre du jour – COPIL sûreté", "Awa Koné", "Marc Dubois; Léa Martin",
              "Bonjour,\nVoici l'ordre du jour : bilan T3 et budget 2027.\nCordialement", datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc),
              cc="Direction", attachments=[("budget.xlsx", b"PK\x03\x04fake")])


def png_bytes(size=(2400, 1200)) -> bytes:
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", size, (30, 90, 160)).save(buf, "PNG"); return buf.getvalue()


CSV_FR = "Site;Incidents;Coût\nNord;12;1 200,50\nSud;7;980\nÉst;3;450\n".encode("cp1252")
