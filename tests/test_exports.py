import io
import zipfile

import pytest
from openpyxl import load_workbook
from docx import Document

from app import exporters, generate
from tests.sample import ANALYSIS, TRANSCRIPT

TYPES, FMTS = ["pv", "cr", "note"], ["pdf", "docx", "xlsx"]


@pytest.mark.parametrize("doc_type", TYPES)
@pytest.mark.parametrize("fmt", FMTS)
def test_export_all_combinations(doc_type, fmt):
    data, mime, name = exporters.export(ANALYSIS, doc_type, fmt, TRANSCRIPT)
    assert len(data) > 1000
    assert name.endswith("." + fmt) and name.startswith(doc_type.upper())
    if fmt == "pdf":
        assert data[:5] == b"%PDF-"
    else:
        assert zipfile.is_zipfile(io.BytesIO(data))


def test_docx_content_pv():
    data, *_ = exporters.export(ANALYSIS, "pv", "docx")
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "PROCÈS-VERBAL" in text and "Bilan des incidents T3" in text
    assert len(doc.tables) >= 3  # participants, décisions, actions (+ méta + signatures)


def test_xlsx_sheets_and_priority_sort():
    data, *_ = exporters.export(ANALYSIS, "cr", "xlsx", TRANSCRIPT)
    wb = load_workbook(io.BytesIO(data))
    assert {"Document", "Participants", "Décisions", "Actions", "Transcription"} <= set(wb.sheetnames)
    acts = wb["Actions"]
    assert acts["B2"].value.startswith("Obtenir")  # priorité haute en premier
    assert wb["Transcription"]["A2"].value == "00:00:03"


def test_note_is_short_form():
    blocks = exporters.build_note(ANALYSIS)
    heads = [b["text"] for b in blocks if b["t"] == "h"]
    assert heads[0] == "Synthèse" and "Recommandations / arbitrages attendus" in heads
    assert "Délibérations" not in heads


def test_empty_analysis_does_not_crash():
    empty = generate.normalize({}, {"title": "Vide"})
    for t in TYPES:
        for f in FMTS:
            exporters.export(empty, t, f)


def test_special_characters_pdf():
    a = generate.normalize({**ANALYSIS, "resume": "R&D <test> « guillemets » € – œuvre"}, {})
    data, *_ = exporters.export(a, "note", "pdf")
    assert data[:5] == b"%PDF-"


def test_filename_keeps_letters_of_accents():
    _, _, name = exporters.export(ANALYSIS, "pv", "pdf")
    assert name == "PV_Comite_de_pilotage_surete_Site_Nord.pdf"
