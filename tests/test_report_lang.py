"""Langue des rapports (français / anglais) : choix à la création, consigne au modèle, intitulés des exports, rien d'autre ne change."""
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import exporters, generate, labels, main, slides, transcribe
from tests.sample import RAW


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(transcribe, "transcribe", lambda a, l, p=lambda m: None: "[00:00:01] Hello")
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None, attachments=None: generate.normalize(RAW, meta))
    return TestClient(main.app)


def _wait(c, mid):
    for _ in range(100):
        m = c.get(f"/api/meetings/{mid}").json()
        if m["status"] in ("done", "error"):
            return m
        time.sleep(0.1)
    raise AssertionError("timeout")


def _strings(o, acc=None):
    acc = [] if acc is None else acc
    if isinstance(o, str):
        acc.append(o)
    elif isinstance(o, (list, tuple)):
        for x in o:
            _strings(x, acc)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("t", "layout", "icon", "tone", "id"):
                _strings(v, acc)
    return acc


FIXED_FR = {k for k, v in labels.EN.items() if k != v}


def test_norm_and_defaults():
    assert labels.norm(None) == "fr" and labels.norm("") == "fr" and labels.norm("EN") == "en" and labels.norm("de") == "fr"
    assert labels.of({}) == "fr" and labels.of({"_lang": "en"}) == "en"


def test_french_is_untouched():
    a = generate.normalize(RAW, {})
    assert a["_lang"] == "fr"
    texts = _strings(exporters.BUILDERS["pv"](a))
    assert "PROCÈS-VERBAL DE RÉUNION" in texts and "Relevé des décisions" in texts and "Plan d'actions" in texts


def test_english_blocks_and_slides_have_no_fixed_french_label():
    a = generate.normalize(RAW, {"report_lang": "en"})
    assert a["_lang"] == "en"
    texts = []
    for t in ("pv", "cr", "note"):
        texts += _strings(exporters.BUILDERS[t](a))
    for visual in (False, True):
        texts += _strings(slides.build_slides(a, visual, []))
    left = sorted({s for s in texts if s.strip() in FIXED_FR})
    assert not left, left
    assert "MEETING MINUTES" in texts and "Record of decisions" in texts and "Action plan" in texts


def test_model_text_is_left_alone_unless_it_is_exactly_a_fixed_label():
    # seule une chaîne IDENTIQUE à un intitulé fixe est remplacée ; tout texte rédigé reste tel quel
    text = "Les décisions du comité de pilotage ont été validées."
    a = generate.normalize(dict(RAW, resume=text), {"report_lang": "en"})
    cr = exporters.BUILDERS["cr"](a)
    assert any(b.get("t") == "p" and b.get("text") == text for b in cr)
    assert labels.tr("Décisions", "en") == "Decisions" and labels.tr(text, "en") == text and labels.tr(text, "fr") == text


def test_prompt_changes_only_the_output_language():
    fr, en = generate.system_prompt("fr"), generate.system_prompt("en")
    assert "Rédige en français" in fr and "ANGLAIS" not in fr
    assert "Rédige en ANGLAIS" in en and "LANGUE DE SORTIE : ANGLAIS" in en and "TBD" in en
    assert "N'invente aucun nom" in en     # les règles de fidélité restent


def _texts_of(data: bytes, fmt: str) -> str:
    if fmt == "pdf":
        import re
        return data.decode("latin-1")
    z = zipfile.ZipFile(io.BytesIO(data))
    return " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))


@pytest.mark.parametrize("doc,fmt", [("pv", "docx"), ("cr", "xlsx"), ("note", "docx"), ("deck", "pptx"), ("deck_visual", "pptx")])
def test_english_exports_use_english_labels(doc, fmt):
    a = generate.normalize(RAW, {"report_lang": "en"})
    data, _, _ = exporters.export(a, doc, fmt, "[00:00:01] x")
    xml = _texts_of(data, fmt)
    for fr_label in ("PROCÈS-VERBAL", "COMPTE RENDU DE", "NOTE DE SYNTHÈSE", "Relevé des décisions", "Suivi des actions", "Prochaines étapes", "RÉPARTITION"):
        assert fr_label not in xml, fr_label
    assert ("Page" in xml) or fmt == "pptx"
    fr = exporters.export(generate.normalize(RAW, {}), doc, fmt, "[00:00:01] x")[0]
    assert len(fr) > 1000 and fr != data


def test_xlsx_footer_and_transcript_sheet_are_localised():
    en = exporters.export(generate.normalize(RAW, {"report_lang": "en"}), "cr", "xlsx", "[00:00:01] x")[0]
    fr = exporters.export(generate.normalize(RAW, {}), "cr", "xlsx", "[00:00:01] x")[0]
    xe, xf = _texts_of(en, "xlsx"), _texts_of(fr, "xlsx")
    assert "Transcript" in xe and "Timestamp" in xe and "Horodatage" not in xe
    assert "Transcription" in xf and "Horodatage" in xf


def test_report_lang_is_stored_through_every_creation_route(client):
    r = client.post("/api/meetings/text", json={"text": "Bonjour tout le monde", "title": "T", "report_lang": "en"})
    m = _wait(client, r.json()["id"])
    assert m["report_lang"] == "en" and m["analysis"]["_lang"] == "en"
    r = client.post("/api/meetings/text", json={"text": "Bonjour tout le monde", "title": "T"})
    m = _wait(client, r.json()["id"])
    assert m["report_lang"] == "fr" and m["analysis"]["_lang"] == "fr"
    r = client.post("/api/meetings/text", json={"text": "Bonjour", "report_lang": "xx"})
    assert _wait(client, r.json()["id"])["report_lang"] == "fr"       # valeur inconnue → français


def test_changing_the_language_then_regenerating(client):
    mid = client.post("/api/meetings/text", json={"text": "Bonjour tout le monde", "title": "T"}).json()["id"]
    assert _wait(client, mid)["analysis"]["_lang"] == "fr"
    assert client.patch(f"/api/meetings/{mid}", json={"report_lang": "en"}).json()["report_lang"] == "en"
    client.post(f"/api/meetings/{mid}/regenerate")
    assert _wait(client, mid)["analysis"]["_lang"] == "en"
    blocks = client.get(f"/api/meetings/{mid}/preview/pv").json()
    assert any(b.get("text") == "MEETING MINUTES" for b in blocks)
    docx = client.get(f"/api/meetings/{mid}/export/pv.docx")
    assert docx.status_code == 200 and b"MEETING MINUTES" in zipfile.ZipFile(io.BytesIO(docx.content)).read("word/document.xml")


def test_recording_meta_carries_the_report_language(client):
    rid = "a1b2c3d4e5f6"
    assert client.post("/api/recordings", json={"id": rid, "title": "R", "report_lang": "en"}).status_code == 200
    assert client.get(f"/api/meetings/{rid}").json()["report_lang"] == "en"
