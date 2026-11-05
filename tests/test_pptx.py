import io

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image

from app import exporters, generate, main, slides
from tests.sample import ANALYSIS, stress_analysis

BRAND = None


def _brand():
    buf = io.BytesIO(); Image.new("RGBA", (360, 120), (139, 30, 63, 255)).save(buf, "PNG")
    return {"org_name": "ACME", "header_right": "Diffusion restreinte", "footer": "ACME – interne", "confidential": "CONFIDENTIEL",
            "color": "8B1E3F", "logo": buf.getvalue(), "logo_size": (360, 120)}


def _deck(analysis, kind, brand=None):
    data, mime, name = exporters.export(analysis, kind, "pptx", None, brand)
    assert mime.endswith("presentationml.presentation") and name.endswith(".pptx")
    return Presentation(io.BytesIO(data)), name


def _walk(shapes):
    for s in shapes:
        yield s
        if s.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(s.shapes)


def _count(prs, kind):
    n = 0
    for sl in prs.slides:
        for s in _walk(sl.shapes):
            n += (kind == "group" and s.shape_type == MSO_SHAPE_TYPE.GROUP) or (kind == "picture" and s.shape_type == MSO_SHAPE_TYPE.PICTURE) \
                 or (kind == "chart" and getattr(s, "has_chart", False) and s.has_chart)
    return n


def _all_text(prs):
    out = []
    for sl in prs.slides:
        for s in _walk(sl.shapes):
            if s.has_text_frame:
                out.append(s.text_frame.text)
    return "\n".join(out)


def test_standard_deck_is_plain_text_and_tables():
    prs, name = _deck(ANALYSIS, "deck")
    assert name.startswith("PRESENTATION_Comite") and "ILLUSTREE" not in name
    assert _count(prs, "group") == 0 and _count(prs, "picture") == 0 and _count(prs, "chart") == 0   # aucune illustration
    text = _all_text(prs)
    assert "Bilan des incidents T3" in text and "Plan d'actions" in text and "Participants" in text


def test_visual_deck_has_pictograms_images_and_charts():
    prs, name = _deck(ANALYSIS, "deck_visual")
    assert "ILLUSTREE" in name
    assert _count(prs, "group") >= 10          # pictogrammes vectoriels groupés
    assert _count(prs, "picture") >= 3         # visuels générés (ouverture + bandeaux de sujets)
    assert _count(prs, "chart") == 2           # priorités (anneau) + actions par responsable
    text = _all_text(prs)
    assert "La réunion en chiffres" in text and "L'essentiel" in text and "Prochaines étapes" in text
    names = {s.name for sl in prs.slides for s in _walk(sl.shapes) if s.shape_type == MSO_SHAPE_TYPE.GROUP}
    assert {"Pictogramme securite", "Pictogramme budget", "Pictogramme decision"} <= names


def test_speaker_notes_carry_the_full_discussion():
    for kind in ("deck", "deck_visual"):
        prs, _ = _deck(ANALYSIS, kind)
        notes = [sl.notes_slide.notes_text_frame.text for sl in prs.slides if sl.has_notes_slide]
        assert any("baisse de 18 %" in n for n in notes)


def test_brand_applied_to_both_decks():
    for kind in ("deck", "deck_visual"):
        prs, _ = _deck(ANALYSIS, kind, _brand())
        text = _all_text(prs)
        assert "CONFIDENTIEL" in text and "ACME – interne" in text and "Diffusion restreinte" in text
        assert _count(prs, "picture") >= len(prs.slides._sldIdLst) - 1 or _count(prs, "picture") >= 5   # logo présent
        xml = "".join(sl._element.xml for sl in prs.slides)
        assert "8B1E3F" in xml                   # couleur du gabarit


def test_light_brand_color_keeps_text_readable():
    brand = {**_brand(), "color": "FFE066"}      # jaune très clair : le texte posé dessus ne doit pas être blanc
    prs, _ = _deck(ANALYSIS, "deck", brand)
    cover = prs.slides[0]
    colors = {str(r.font.color.rgb) for s in cover.shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs
              if r.text.startswith("Comité")}
    assert colors == {"1C2430"}


@pytest.mark.parametrize("kind", ["deck", "deck_visual"])
def test_stress_nothing_leaves_the_slide(kind):
    prs, _ = _deck(stress_analysis(), kind, _brand())
    W, H = prs.slide_width, prs.slide_height
    tol = 20000
    for i, sl in enumerate(prs.slides, 1):
        for s in sl.shapes:
            assert s.left >= -tol and s.top >= -tol, (kind, i, s.name)
            assert s.left + s.width <= W + tol and s.top + s.height <= H + tol, (kind, i, s.name, s.top + s.height, H)


def test_pagination_and_charts_only_on_first_actions_page():
    sl = slides.build_slides(stress_analysis(), True)
    pages = [s for s in sl if s["layout"] == "table" and s["title"].startswith("Plan d'actions")]
    assert len(pages) >= 2 and sum(len(p["rows"]) for p in pages) == 17
    assert pages[0]["charts"] and all(p["charts"] is None for p in pages[1:])
    assert pages[0]["title"].endswith(f"(1/{len(pages)})")
    people = [s for s in sl if s["layout"] == "people"]
    assert len(people) == 2 and sum(len(p["people"]) for p in people) == 14


def test_slide_content_uses_dedicated_fields_and_falls_back_for_old_analyses():
    sl = slides.build_slides(stress_analysis(), True)
    cards = next(s for s in sl if s["layout"] == "cards" and s["title"] == "L'essentiel")
    assert cards["items"][0]["icon"] == "securite" and cards["items"][0]["title"].startswith("Les intrusions")
    kp = next(s for s in sl if s["layout"] == "kpis")
    assert [e["value"] for e in kp["extra"]] == ["-18 %", "120 k€"]
    # analyse antérieure (sans champs diapositives) : déduction depuis les sujets, icônes devinées, pas de doublon
    old = slides.build_slides(ANALYSIS, True)
    topic = next(s for s in old if s["layout"] == "topic")
    assert topic["icon"] == "securite" and topic["summary"] not in topic["bullets"]


def test_icon_helpers_and_text_clipping():
    assert slides.guess_icon("Budget vidéoprotection 2027") == "budget"
    assert slides.guess_icon("Risque d'intrusion") in {"securite", "risque"}
    assert slides.guess_icon("rien de précis") == "objectif"
    assert slides.icon_or_guess("n'importe quoi", "calendrier des livraisons") == "planning"   # icône inconnue → devinée
    txt = "Première phrase complète. " + "mot " * 80
    assert slides.clip(txt, 40) == "Première phrase complète."        # coupe en fin de phrase quand elle garde l'essentiel
    t = slides.clip(txt, 100)                                          # sinon coupe au mot, avec une ellipse
    assert len(t) <= 101 and t.endswith("…") and not t.endswith(" …")
    assert slides.clip("court", 100) == "court"


def test_empty_analysis_does_not_crash():
    empty = generate.normalize({}, {"title": "Vide"})
    for kind in ("deck", "deck_visual"):
        prs, _ = _deck(empty, kind, _brand())
        assert len(prs.slides) >= 1


def test_invalid_combinations_rejected():
    with pytest.raises(ValueError):
        exporters.export(ANALYSIS, "deck", "pdf")
    with pytest.raises(ValueError):
        exporters.export(ANALYSIS, "pv", "pptx")


def test_api_preview_and_export_for_decks(monkeypatch):
    monkeypatch.setattr(generate, "analyze", lambda t, meta, progress=lambda m: None: generate.normalize(ANALYSIS, meta))
    c = TestClient(main.app)
    mid = c.post("/api/meetings/text", json={"text": "[00:00:01] x", "title": "Deck"}).json()["id"]
    import time
    for _ in range(50):
        if c.get(f"/api/meetings/{mid}").json()["status"] == "done":
            break
        time.sleep(0.1)
    for kind, visual in (("deck", False), ("deck_visual", True)):
        pv = c.get(f"/api/meetings/{mid}/preview/{kind}").json()
        assert pv["visual"] is visual and pv["slides"][0]["layout"] == "cover"
        r = c.get(f"/api/meetings/{mid}/export/{kind}.pptx")
        assert r.status_code == 200 and "presentationml" in r.headers["content-type"] and r.content[:2] == b"PK"
        assert c.get(f"/api/meetings/{mid}/export/{kind}.pdf").status_code == 404
    assert c.get(f"/api/meetings/{mid}/export/pv.pptx").status_code == 404
    assert c.get(f"/api/meetings/{mid}/preview/pv").json()[0]["t"] == "title"      # les anciens rendus ne changent pas
