"""Les pièces jointes renforcent le rapport : sources citées, recoupement, suivi des actions antérieures, numérotation stable, péremption."""
import io
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader
from docx import Document

from app import annexes, attachments as A, config, db, exporters, generate, main, pipeline, slides
from tests.sample import ANALYSIS, RAW

ENRICHED = generate.normalize({
    **RAW,
    "points_abordes": [{**RAW["points_abordes"][0], "pj": [2]}, RAW["points_abordes"][1]],
    "decisions": [{**RAW["decisions"][0], "pj": [2, 3]}],
    "actions": [{**RAW["actions"][0], "pj": [1]}, RAW["actions"][1]],
    "annexes": [{"numero": 1, "nom": "ordre.eml", "resume": "Convocation du COPIL."}, {"numero": 2, "nom": "budget.xlsx", "resume": "Budget 2027."},
                {"numero": 3, "nom": "cr_precedent.docx", "resume": "CR du 3 octobre."}],
    "recoupements": [
        {"sujet": "Budget vidéoprotection", "en_reunion": "120 k€ examinés", "dans_piece_jointe": "95 k€ fixés", "pj": 3, "constat": "ecart"},
        {"sujet": "Délai fournisseur", "en_reunion": "10 semaines", "dans_piece_jointe": "10 semaines", "pj": 2, "constat": "confirme"},
        {"sujet": "Second devis", "en_reunion": "Demandé par les Achats", "dans_piece_jointe": "Devis n°2 attendu le 15/11", "pj": 2, "constat": "complement"}],
    "suivi_anterieur": [
        {"action": "Cartographier les angles morts", "responsable": "Marc Dubois", "statut": "reportee", "commentaire": "Reprise en action 2", "pj": 3},
        {"action": "Valider le budget caméras", "responsable": "Awa Koné", "statut": "soldee", "commentaire": "Validé sous réserve", "pj": 3},
        {"action": "Audit des accès", "responsable": "", "statut": "non_evoquee", "commentaire": "", "pj": 3}],
}, {})


def _heads(blocks):
    return [b["text"] for b in blocks if b["t"] == "h"]


def _table(blocks, name):
    return next(b for b in blocks if b["t"] == "table" and b["name"] == name)


# ------------------------------------------------------------------ consignes et schéma
def test_prompt_asks_the_model_to_reinforce_with_attachments_without_inventing():
    s = generate.SYSTEM
    assert "RENFORCER" in s and "recoupements" in s and "suivi_anterieur" in s and "d'après PJ" in s
    props = generate.ANALYSIS_SCHEMA["properties"]
    assert {"recoupements", "suivi_anterieur", "annexes"} <= props.keys()
    assert "pj" in props["decisions"]["items"]["properties"] and "pj" in props["actions"]["items"]["properties"]
    assert "pj" in props["points_abordes"]["items"]["properties"]
    assert "un faux écart est pire" in props["recoupements"]["description"]
    assert props["recoupements"]["items"]["properties"]["constat"]["enum"] == ["confirme", "ecart", "complement"]
    assert props["suivi_anterieur"]["items"]["properties"]["statut"]["enum"] == ["soldee", "en_cours", "reportee", "non_evoquee"]


# ------------------------------------------------------------------ rapports : citations, recoupement, suivi
def test_pv_cites_sources_and_shows_cross_checks():
    blocks = exporters.build_pv(ENRICHED)
    texts = [b.get("text", "") for b in blocks if b["t"] == "p"]
    assert "Sources : PJ 2 (budget.xlsx)" in texts                                   # sujet appuyé sur une pièce
    assert "Valider le principe du renouvellement des caméras. [PJ 2, PJ 3]" in _table(blocks, "Décisions")["rows"][0]
    assert "Obtenir un second devis caméras [PJ 1]" in _table(blocks, "Actions")["rows"][0]
    assert "Suivi des actions antérieures" in _heads(blocks) and "Recoupement avec les pièces jointes" in _heads(blocks)
    rc = _table(blocks, "Recoupement")["rows"]
    assert [r[3] for r in rc] == ["Écart", "Complément", "Confirmé"]                  # écarts d'abord
    assert rc[0][2] == "PJ 3 : 95 k€ fixés" and rc[0][1] == "120 k€ examinés"
    sv = _table(blocks, "Suivi antérieur")["rows"]
    assert [r[2] for r in sv] == ["Reportée", "Soldée", "Non évoquée"] and sv[2][1] == "—" and sv[0][4] == "PJ 3"


def test_cr_and_note_also_carry_the_reinforcement():
    for build in (exporters.build_cr, exporters.build_note):
        h = _heads(build(ENRICHED))
        assert "Recoupement avec les pièces jointes" in h and "Suivi des actions antérieures" in h
    note = exporters.build_note(ENRICHED)
    bullets = [i for b in note if b["t"] == "bullets" for i in b["items"]]
    assert any(i.endswith("[PJ 2]") for i in bullets)


def test_no_attachment_content_means_reports_are_unchanged():
    for build in (exporters.build_pv, exporters.build_cr, exporters.build_note):
        h = _heads(build(ANALYSIS))
        assert "Recoupement avec les pièces jointes" not in h and "Suivi des actions antérieures" not in h
    assert annexes.tail_blocks([], ANALYSIS) == []


def test_citations_stay_readable_when_annexes_are_turned_off():
    tail = annexes.tail_blocks([], ENRICHED)
    assert tail[0]["text"] == "Pièces jointes citées"
    assert tail[1]["items"] == ["PJ 1 — ordre.eml", "PJ 2 — budget.xlsx", "PJ 3 — cr_precedent.docx"]
    assert annexes.cited(ENRICHED) == {1, 2, 3}


def test_malformed_model_output_never_breaks_a_report():
    weird = generate.normalize({**RAW, "decisions": [{"decision": "X", "pj": ["a", None, True, 99999, 2.0]}], "recoupements": [{"sujet": "s", "constat": "bizarre", "pj": "x"}],
                                "suivi_anterieur": [{"action": "a", "statut": "inconnu"}]}, {})
    assert annexes.tag(weird["decisions"][0]["pj"]) == "PJ 2"
    for t in ("pv", "cr", "note"):
        for f in ("pdf", "docx", "xlsx"):
            exporters.export(weird, t, f)


@pytest.mark.parametrize("fmt", ["pdf", "docx", "xlsx"])
def test_enriched_report_exports_in_every_format(fmt):
    for t in ("pv", "cr", "note"):
        exporters.export(ENRICHED, t, fmt)
    data, *_ = exporters.export(ENRICHED, "pv", fmt)
    if fmt == "docx":
        d = Document(io.BytesIO(data)); cells = " ".join(c.text for t in d.tables for r in t.rows for c in r.cells)
        assert "Écart" in cells and "95 k€ fixés" in cells and "Non évoquée" in cells and "[PJ 2, PJ 3]" in cells
        assert "Pièces jointes citées" in "\n".join(p.text for p in d.paragraphs)
    elif fmt == "xlsx":
        wb = load_workbook(io.BytesIO(data)); assert {"Recoupement", "Suivi antérieur"} <= set(wb.sheetnames)
        assert wb["Recoupement"]["D2"].value == "Écart"
    else:
        txt = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
        assert "Recoupement avec les pièces jointes" in txt and "Écart" in txt


# ------------------------------------------------------------------ présentations
@pytest.mark.parametrize("visual", [False, True])
def test_decks_show_cross_checks_and_follow_up(visual):
    sl = slides.build_slides(ENRICHED, visual)
    titles = [s["title"] for s in sl]
    assert "Suivi des actions antérieures" in titles and "Recoupement avec les pièces jointes" in titles
    rc = next(s for s in sl if s["title"] == "Recoupement avec les pièces jointes")
    assert rc["layout"] == "table" and rc["rows"][0][3] == "Écart"
    data, *_ = exporters.export(ENRICHED, "deck_visual" if visual else "deck", "pptx")
    xml = "".join(s._element.xml for s in Presentation(io.BytesIO(data)).slides)
    assert "D64545" in xml                                   # « Écart » en rouge (couleur sémantique)
    if visual:
        dec = next(s for s in sl if s["title"].startswith("Décisions prises"))
        assert "PJ 2, PJ 3" in dec["items"][0]["chip"]
    else:
        dt = next(s for s in sl if s["title"] == "Décisions")
        assert "[PJ 2, PJ 3]" in dt["rows"][0][1]
    ap = next(s for s in sl if s["title"].startswith("Plan d'actions"))
    assert "Obtenir un second devis caméras [PJ 1]" in ap["rows"][0][1]            # citations aussi dans le tableau d'actions des présentations


def test_topic_notes_carry_the_sources():
    topic = next(s for s in slides.build_slides(ENRICHED, True) if s["layout"] == "topic")
    assert "Sources : PJ 2 (budget.xlsx)" in topic["notes"]


# ------------------------------------------------------------------ numérotation stable
def test_numbers_stay_stable_when_an_attachment_is_removed_then_regenerated(monkeypatch):
    seen = {}
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None, attachments=None: seen.update(att=attachments) or generate.normalize(RAW, meta))
    m = db.create(title="x", source_type="text", status="queued", transcript="[00:00:01] x")["id"]
    ids = [A.save(io.BytesIO(f"contenu {n}".encode()), f"{n}.txt", m)["id"] for n in "abc"]
    pipeline.process(m, raw_text="[00:00:01] x")
    assert [a["n"] for a in seen["att"]] == [1, 2, 3] and A.analyzed_numbers(m) == dict(zip(ids, (1, 2, 3)))
    db.att_update(ids[1], included=False)                                    # on retire la pièce 2…
    assert [(a["name"], a["n"]) for a in A.for_report(m)] == [("a.txt", 1), ("c.txt", 3)]       # …c.txt reste « PJ 3 »
    pipeline.process(m, raw_text="[00:00:01] x")                             # régénération : toujours PJ 3
    assert [(a["name"], a["n"]) for a in seen["att"]] == [("a.txt", 1), ("c.txt", 3)] and A.analyzed_numbers(m) == {ids[0]: 1, ids[2]: 3}
    A.save(io.BytesIO(b"nouvelle"), "d.txt", m)                    # nouvelle pièce : numéro suivant, jamais réutilisé
    assert [a["n"] for a in A.for_report(m)] == [1, 3, 4]
    assert "[PJ 3] « c.txt »" in A.context_text(A.for_report(m)) and "[PJ 2]" not in A.context_text(A.for_report(m))


def test_annexes_use_the_citation_numbers():
    atts = [{"id": "x", "n": 3, "name": "c.txt", "kind": "texte", "label": "Texte", "snippet": "s", "extract": {"text": "bonjour", "meta": {}}}]
    blocks = annexes.build_blocks(atts, ENRICHED)
    assert blocks[2]["rows"][0][0] == "3" and any(b.get("text") == "Annexe 3 — c.txt" for b in blocks)
    assert annexes.summaries(atts, ENRICHED)["x"] == "CR du 3 octobre."       # résumé du modèle repéré par le numéro stable
    sl = slides.build_slides(ENRICHED, False, atts)
    assert any(s["title"].startswith("Annexe 3 — c.txt") for s in sl)


# ------------------------------------------------------------------ péremption (bandeau « régénérer »)
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None, attachments=None: generate.normalize(ENRICHED, meta))
    return TestClient(main.app)


def _wait(c, mid, want="done"):
    for _ in range(100):
        m = c.get(f"/api/meetings/{mid}").json()
        if m["status"] in (want, "error"):
            return m
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_stale_flag_follows_attachment_changes(client):
    a = client.post("/api/attachments", files=[("files", ("a.txt", b"un"))]).json()["attachments"][0]["id"]
    mid = client.post("/api/meetings/text", json={"text": "[00:00:01] x", "attachment_ids": [a]}).json()["id"]
    assert _wait(client, mid)["atts_stale"] is False
    b = client.post("/api/attachments", files=[("files", ("b.txt", b"deux"))], data={"meeting_id": mid}).json()["attachments"][0]["id"]
    assert client.get(f"/api/meetings/{mid}").json()["atts_stale"] is True                 # pièce ajoutée après la rédaction
    client.post(f"/api/meetings/{mid}/regenerate"); assert _wait(client, mid)["atts_stale"] is False
    client.patch(f"/api/attachments/{b}", json={"included": False})
    assert client.get(f"/api/meetings/{mid}").json()["atts_stale"] is True                 # pièce désactivée
    client.patch(f"/api/attachments/{b}", json={"included": True})
    assert client.get(f"/api/meetings/{mid}").json()["atts_stale"] is False                # retour à l'état rédigé : plus périmé
    client.delete(f"/api/attachments/{b}")
    assert client.get(f"/api/meetings/{mid}").json()["atts_stale"] is True


def test_meetings_without_attachments_are_never_stale_and_legacy_ones_are_detected(client):
    mid = client.post("/api/meetings/text", json={"text": "[00:00:01] x"}).json()["id"]
    assert _wait(client, mid)["atts_stale"] is False
    legacy = db.create(title="ancienne", source_type="text", status="done", transcript="x")["id"]
    db.update(legacy, analysis=ENRICHED)                                                      # rédigée avant cette fonction (colonne vide)
    assert client.get(f"/api/meetings/{legacy}").json()["atts_stale"] is False
    A.save(io.BytesIO(b"x"), "n.txt", legacy)
    assert client.get(f"/api/meetings/{legacy}").json()["atts_stale"] is True


def test_database_migration_adds_columns_and_keeps_data(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE meetings (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, meeting_date TEXT, location TEXT, "
                  "participants TEXT, context TEXT, language TEXT, source_type TEXT, source_url TEXT, status TEXT NOT NULL, progress TEXT, "
                  "error TEXT, duration REAL, transcript TEXT, analysis TEXT)")
        c.execute("INSERT INTO meetings (id,title,created_at,status) VALUES ('old1','Ancienne','2026-01-01T00:00:00','done')")
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init(); db.init()                                                                       # idempotent
    with sqlite3.connect(path) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(meetings)")}
    assert {"analyzed_atts", "analyzed_at"} <= cols and db.get("old1")["title"] == "Ancienne"
