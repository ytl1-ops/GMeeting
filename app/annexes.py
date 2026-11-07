"""Annexes : les pièces jointes d'une réunion insérées à la suite des rapports (PV, CR, note de synthèse).

Même mécanique que le reste des exports : on produit des « blocs » neutres, rendus ensuite en PDF, Word ou Excel.
Mode lecture (PDF/Word/aperçu) : extraits et tableaux raccourcis. Mode Excel : tableaux complets (200 lignes), un onglet par tableau.
"""
from __future__ import annotations

import re
from typing import Any

Block = dict[str, Any]
TEXT_CHARS = 3000
MAX_TEXT_PARAS = 10


def model_summaries(atts: list[dict], analysis: dict) -> dict[str, str]:
    """Résumés rédigés par le modèle (repérés par numéro ou par nom) ; une pièce absente du dictionnaire n'a pas de résumé."""
    by_num, by_name = {}, {}
    for e in analysis.get("annexes") or []:
        r = (e.get("resume") or "").strip()
        if not r:
            continue
        if isinstance(e.get("numero"), int):
            by_num[e["numero"]] = r
        if e.get("nom"):
            by_name[str(e["nom"]).strip().lower()] = r
    out = {}
    for i, a in enumerate(atts, 1):
        r = by_num.get(a.get("n", i)) or by_name.get(a["name"].strip().lower())
        if r:
            out[a["id"]] = r
    return out


def summaries(atts: list[dict], analysis: dict) -> dict[str, str]:
    """Résumé du modèle pour chaque pièce, à défaut l'aperçu extrait (pour les listes)."""
    mine = model_summaries(atts, analysis)
    return {a["id"]: mine.get(a["id"]) or a.get("snippet") or "" for a in atts}


def _paragraphs(text: str) -> list[str]:
    clipped = len(text) > TEXT_CHARS
    text = text[:TEXT_CHARS]
    if clipped:
        text = text[: text.rfind(" ")] if " " in text[-200:] else text
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) == 1 and "\n" in paras[0]:                 # texte sans lignes vides : une ligne = un paragraphe
        paras = [p.strip() for p in paras[0].split("\n") if p.strip()]
    paras = paras[:MAX_TEXT_PARAS]
    if clipped or len(paras) == MAX_TEXT_PARAS:
        paras.append("[…] Extrait : le contenu complet figure dans la pièce jointe d'origine.")
    return paras


def build_blocks(atts: list[dict], analysis: dict, rows_limit: int = 25, cols_limit: int = 8) -> list[Block]:
    if not atts:
        return []
    summ = summaries(atts, analysis)
    b: list[Block] = [{"t": "pagebreak"}, {"t": "h", "text": "Annexes — pièces jointes"}]
    b.append({"t": "table", "name": "Annexes", "headers": ["N°", "Pièce jointe", "Type", "Résumé"], "widths": [0.07, 0.3, 0.18, 0.45],
              "rows": [[str(a.get("n", i)), a["name"], a["label"], summ[a["id"]]] for i, a in enumerate(atts, 1)]})
    for i0, a in enumerate(atts, 1):
        i = a.get("n", i0)                                  # même numéro que les citations « PJ n » du rapport
        x = a["extract"]
        b.append({"t": "h2", "text": f"Annexe {i} — {a['name']}"})
        if x.get("meta"):
            b.append({"t": "meta", "rows": [(k, v) for k, v in x["meta"].items() if v]})
        if x.get("image"):
            b.append({"t": "image", "id": a["id"], "caption": a["name"], "size": x.get("image_size")})
        for para in _paragraphs(x.get("text", "")) if x.get("text") else []:
            b.append({"t": "p", "text": para})
        if x.get("mail_attachments"):
            b.append({"t": "p", "text": "Pièces jointes de ce message :", "bold": True})
            b.append({"t": "bullets", "items": x["mail_attachments"][:15]})
        for t in x.get("tables", [])[:4]:
            cols = len(t["headers"])
            width = min(cols, cols_limit)
            rows = [r[:width] for r in t["rows"][:rows_limit]]
            b.append({"t": "table", "name": f"PJ{i} {t['name']}"[:31], "headers": t["headers"][:width],
                      "widths": [1 / width] * width, "rows": rows})
            notes = []
            if t["truncated"] or t["total_rows"] > len(rows):
                notes.append(f"{len(rows)} première(s) ligne(s) sur {t['total_rows']}")
            if cols > width:
                notes.append(f"{width} colonnes sur {cols}")
            if notes:
                b.append({"t": "p", "text": "Extrait : " + " ; ".join(notes) + ". Données complètes dans la pièce jointe d'origine."})
        if x.get("note"):
            b.append({"t": "p", "text": x["note"]})
    return b


# ------------------------------------------------------------------ renfort du rapport par les pièces jointes
CONSTAT = {"confirme": "Confirmé", "ecart": "Écart", "complement": "Complément"}
STATUT = {"soldee": "Soldée", "en_cours": "En cours", "reportee": "Reportée", "non_evoquee": "Non évoquée"}


def _nums(pj) -> list[int]:
    return sorted({int(n) for n in (pj or []) if isinstance(n, (int, float)) and not isinstance(n, bool) and 0 < n < 1000})


def tag(pj) -> str:
    """« PJ 2, PJ 3 » : sources d'un élément du rapport."""
    return ", ".join(f"PJ {n}" for n in _nums(pj))


def cite(text: str, pj) -> str:
    t = tag(pj)
    return f"{text} [{t}]" if t else text


def names(analysis: dict) -> dict[int, str]:
    return {int(e["numero"]): str(e.get("nom") or "") for e in analysis.get("annexes") or []
            if isinstance(e.get("numero"), int) and e.get("nom")}


def cited(analysis: dict) -> set[int]:
    """Numéros de toutes les pièces citées dans le rapport."""
    out: set[int] = set()
    for key in ("points_abordes", "decisions", "actions", "suivi_anterieur", "recoupements"):
        for it in analysis.get(key) or []:
            out |= set(_nums(it.get("pj") if key not in ("suivi_anterieur", "recoupements") else [it.get("pj")]))
    return out


def sources_line(pj, analysis: dict) -> str:
    nm = names(analysis)
    return "Sources : " + ", ".join(f"PJ {n}" + (f" ({nm[n]})" if n in nm else "") for n in _nums(pj))


def recoupement_table(analysis: dict) -> Block | None:
    items = analysis.get("recoupements") or []
    if not items:
        return None
    order = {"ecart": 0, "complement": 1, "confirme": 2}
    items = sorted(items, key=lambda r: order.get(r.get("constat"), 3))
    return {"t": "table", "name": "Recoupement", "headers": ["Sujet", "En réunion", "Pièce jointe", "Constat"], "widths": [0.2, 0.28, 0.37, 0.15],
            "rows": [[r.get("sujet", ""), r.get("en_reunion", ""),
                      (f"PJ {r['pj']} : " if r.get("pj") else "") + r.get("dans_piece_jointe", ""),
                      CONSTAT.get(r.get("constat"), "")] for r in items]}


def suivi_table(analysis: dict) -> Block | None:
    items = analysis.get("suivi_anterieur") or []
    if not items:
        return None
    return {"t": "table", "name": "Suivi antérieur", "headers": ["Action antérieure", "Responsable", "Statut", "Commentaire", "Source"],
            "widths": [0.33, 0.15, 0.13, 0.29, 0.1],
            "rows": [[r.get("action", ""), r.get("responsable", "") or "—", STATUT.get(r.get("statut"), ""), r.get("commentaire", ""),
                      f"PJ {r['pj']}" if r.get("pj") else ""] for r in items]}


def tail_blocks(atts: list[dict], analysis: dict, rows_limit: int = 25, cols_limit: int = 8) -> list[Block]:
    """Annexes dans la langue du rapport."""
    from . import labels
    return labels.tr_deep(_tail_blocks(atts, analysis, rows_limit, cols_limit), labels.of(analysis))


def _tail_blocks(atts: list[dict], analysis: dict, rows_limit: int = 25, cols_limit: int = 8) -> list[Block]:
    """Fin de rapport : annexes complètes ; sans annexes, la liste des pièces citées (pour que « PJ 2 » reste compréhensible)."""
    if atts:
        return build_blocks(atts, analysis, rows_limit, cols_limit)
    nm, nums = names(analysis), sorted(cited(analysis))
    if not nums:
        return []
    return [{"t": "h", "text": "Pièces jointes citées"},
            {"t": "bullets", "items": [f"PJ {n}" + (f" — {nm[n]}" if n in nm else "") for n in nums]}]
