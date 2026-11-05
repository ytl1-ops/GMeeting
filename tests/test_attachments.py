import io
import zipfile
from pathlib import Path

import pytest

from app import attachments as A, config, db
from tests import attbuild as B


def save(data: bytes, name: str, mid=None):
    return A.save(io.BytesIO(data), name, mid)


# ------------------------------------------------------------------ extraction par format
def test_email_eml_headers_body_and_nested_attachments():
    a = save(B.eml_bytes(), "ordre.eml"); x = a["extract"]
    assert a["kind"] == "email" and x["meta"]["Objet"] == "Ordre du jour du COPIL"
    assert "Awa Koné" in x["meta"]["De"] and "Léa Martin" in x["meta"]["À"] and x["meta"]["Cc"] == "direction@example.org"
    assert x["meta"]["Date"].startswith("03/11/2026")
    assert "bilan T3, budget 2027" in x["text"] and x["mail_attachments"] == ["ordre_du_jour.pdf"]
    assert a["snippet"].startswith("Ordre du jour du COPIL")


def test_email_html_only_is_converted_without_scripts_or_styles():
    x = save(B.eml_html_only_bytes(), "h.eml")["extract"]
    assert "Bonjour Marc" in x["text"] and "Point A" in x["text"] and "alert" not in x["text"] and "color:red" not in x["text"]


def test_real_outlook_msg(tmp_path):
    p = tmp_path / "m.msg"; B.msg_file(p)
    a = save(p.read_bytes(), "Ordre du jour.msg"); x = a["extract"]
    assert a["kind"] == "email" and a["label"].startswith("E-mail Outlook")
    assert x["meta"]["Objet"] == "Ordre du jour – COPIL sûreté" and "Awa Koné" in x["meta"]["De"]
    assert x["meta"]["À"] == "Marc Dubois; Léa Martin" and x["meta"]["Cc"] == "Direction" and x["meta"]["Date"] == "03/11/2026 09:30"
    assert "bilan T3 et budget 2027" in x["text"] and x["mail_attachments"] == ["budget.xlsx"]


def test_word_text_tables_and_properties():
    x = save(B.docx_bytes(), "cr.docx")["extract"]
    assert "95 k€" in x["text"] and x["meta"]["Titre"] == "Compte rendu précédent" and x["meta"]["Auteur"] == "Awa Koné"
    t = x["tables"][0]
    assert t["headers"] == ["Poste", "Montant"] and t["rows"] == [["Caméras", "60 000"], ["Câblage", "35 000"]]


def test_excel_values_dates_numbers_and_sheets():
    a = save(B.xlsx_bytes(), "budget.xlsx"); t = a["extract"]["tables"]
    assert [s["name"] for s in t] == ["Budget", "Notes"]
    rows = t[0]["rows"]
    assert t[0]["headers"] == ["Poste", "Montant", "Date", "Validé"]
    assert rows[0] == ["Ligne 1", "1000", "03/11/2026", "Non"] and rows[1][1] == "1234.5" and rows[1][3] == "Oui"   # dates FR, pas de « 1000.0 »
    assert "Budget : 5 ligne(s)" in a["snippet"]


def test_excel_large_sheet_is_capped_and_flagged():
    t = save(B.xlsx_bytes(rows=450), "gros.xlsx")["extract"]["tables"][0]
    assert len(t["rows"]) == A.MAX_TABLE_ROWS == 200 and t["truncated"] and t["total_rows"] == 450


def test_csv_semicolon_and_windows_encoding():
    t = save(B.CSV_FR, "sites.csv")["extract"]["tables"][0]
    assert t["headers"] == ["Site", "Incidents", "Coût"] and t["rows"][2] == ["Ést", "3", "450"] and t["rows"][0][2] == "1 200,50"


def test_pdf_text_and_scanned_pdf_note():
    assert "Trois écarts mineurs" in save(B.pdf_bytes(), "audit.pdf")["extract"]["text"]
    scan = save(B.pdf_bytes(""), "scan.pdf")
    assert scan["extract"]["text"] == "" and "sans texte" in scan["extract"]["note"]


def test_powerpoint_text_and_notes():
    x = save(B.pptx_bytes(), "plan.pptx")["extract"]
    assert "Plan 2027" in x["text"] and "Renouveler 40 caméras" in x["text"] and "Insister sur le calendrier" in x["text"]


def test_text_file_encodings():
    assert "été" in save("Résumé de l'été".encode("cp1252"), "n.txt")["extract"]["text"]


def test_image_is_reencoded_resized_and_stripped():
    a = save(B.png_bytes((3000, 1500)), "plan.jpg" if False else "photo.png")
    from PIL import Image
    im = Image.open(A.image_path(a))
    assert im.format == "PNG" and max(im.size) <= 1600 and a["extract"]["image"] and a["extract"]["meta"]["Dimensions"] == "3000 × 1500 px"


def test_legacy_and_unknown_formats_are_kept_with_a_note():
    d = save(b"\xd0\xcf\x11\xe0 binaire", "ancien.doc"); u = save(b"data", "archive.zip")
    assert d["kind"] == "autre" and "docx" in d["extract"]["note"] and u["kind"] == "autre" and "non extrait" in u["extract"]["note"]


# ------------------------------------------------------------------ refus et sécurité
def test_executables_and_scripts_are_refused():
    for n in ("virus.exe", "run.bat", "x.ps1", "s.js", "a.SH", "doc.exe"):
        with pytest.raises(A.AttachmentError):
            save(b"MZ", n)


def test_path_traversal_in_filename_is_neutralised():
    a = save(b"texte", "../../etc/passwd.txt")
    assert a["name"] == "passwd.txt" and A.original_path(a).parent == config.ATTACH_DIR / a["id"]
    assert A.clean_name("..\\..\\win\\x<>.txt") == "x.txt"


def test_empty_oversized_and_corrupted_are_refused_and_leave_nothing(monkeypatch):
    before = set(p.name for p in config.ATTACH_DIR.iterdir())
    rows_before = db.att_count(None)
    with pytest.raises(A.AttachmentError, match="vide"):
        save(b"", "vide.txt")
    monkeypatch.setattr(config, "MAX_ATTACH_MB", 1)
    with pytest.raises(A.AttachmentError, match="dépasse"):
        save(b"x" * (2 * 1024 * 1024), "gros.txt")
    monkeypatch.undo()
    with pytest.raises(A.AttachmentError, match="corrompu"):
        save(b"pas un zip", "faux.docx")
    with pytest.raises(A.AttachmentError, match="illisible"):
        save(b"pas une image", "faux.png")
    assert set(p.name for p in config.ATTACH_DIR.iterdir()) == before          # aucun fichier orphelin…
    assert db.att_count(None) == rows_before                                   # …et aucune ligne en base


def test_zip_bomb_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"\0" * (125 * 1024 * 1024))              # ≈ 125 Mo une fois décompressé, quelques Ko compressé
    assert len(buf.getvalue()) < 1_000_000
    with pytest.raises(A.AttachmentError, match="volumineux"):
        save(buf.getvalue(), "bombe.docx")


def test_limit_per_meeting(monkeypatch):
    monkeypatch.setattr(config, "MAX_ATTACH_PER_MEETING", 2)
    m = db.create(title="x", source_type="text", status="done")["id"]
    save(b"a", "1.txt", m); save(b"b", "2.txt", m)
    with pytest.raises(A.AttachmentError, match="Trop"):
        save(b"c", "3.txt", m)


def test_macro_enabled_workbook_never_executes_macros():
    # .xlsm accepté en lecture seule (valeurs), keep_vba=False : aucun code n'est chargé ni exécuté
    assert save(B.xlsx_bytes(), "m.xlsm")["kind"] == "excel"


# ------------------------------------------------------------------ rattachement et contexte
def test_staging_link_and_stale_purge():
    a = save(b"un", "a.txt"); b = save(b"deux", "b.txt")
    m = db.create(title="x", source_type="text", status="done")["id"]
    assert A.link([a["id"], "inconnu0000", "zz"], m) == [a["id"]]
    assert A.link([a["id"]], "autre1234567") == []                                # déjà rattachée : non volable
    assert [x["id"] for x in db.att_list(m)] == [a["id"]]
    db.att_update(b["id"], included=True)
    import sqlite3
    with sqlite3.connect(config.DB_PATH) as c:
        c.execute("UPDATE attachments SET created_at='2000-01-01T00:00:00' WHERE id=?", (b["id"],))
    A.purge_stale()
    assert db.att_get(b["id"]) is None and not (config.ATTACH_DIR / b["id"]).exists() and db.att_get(a["id"])


def test_context_text_shares_budget_and_labels_sources():
    m = db.create(title="x", source_type="text", status="done")["id"]
    save(B.eml_bytes(), "ordre.eml", m); save(B.xlsx_bytes(), "budget.xlsx", m)
    ctx = A.context_text(db.att_list(m))
    assert ctx.startswith("[PJ 1] « ordre.eml »") and "[PJ 2] « budget.xlsx »" in ctx
    assert "Objet : Ordre du jour du COPIL" in ctx and "Ligne 1 | 1000" in ctx
    short = A.context_text(db.att_list(m), budget=100)
    assert "[…tronqué]" not in A.context_text(db.att_list(m)) and len(short) < len(ctx) + 200
