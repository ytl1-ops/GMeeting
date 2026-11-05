"""Construction du contenu des diapositives (indépendante du moteur de rendu).

Deux présentations à partir de la même analyse :
  * « standard »  (visual=False) : sobre, texte et tableaux, aucune illustration ;
  * « illustrée » (visual=True)  : chiffres clés, cartes avec pictogrammes, avatars, graphiques, frise des prochaines étapes.

Le modèle est une liste de dictionnaires {layout, title, ...}. L'aperçu web et le fichier PowerPoint sont
produits à partir de cette même liste : ce qui est affiché est ce qui est exporté.
"""
from __future__ import annotations

import math
import re
from typing import Any

from . import annexes as annex_mod

Slide = dict[str, Any]
PRIO_ORDER = {"haute": 0, "moyenne": 1, "basse": 2}
MAX_TOPIC_SLIDES = 14
CARDS_PER_SLIDE = 6
PEOPLE_PER_SLIDE = 8

ICONS = {"objectif", "equipe", "planning", "decision", "action", "risque", "idee", "budget", "securite",
         "technique", "communication", "juridique", "qualite", "question", "jalon", "horloge"}

_KEYWORDS = [
    ("budget", r"budget|€|euro|coût|cout|devis|financ|investiss|facture|tarif"),
    ("securite", r"s[ûu]ret[ée]|s[ée]curit[ée]|intrusion|vid[ée]o|cam[ée]ra|acc[èe]s|incident|gardiennage|surveillance|protection"),
    ("risque", r"risque|menace|vuln[ée]rab|alerte|crise|danger|sinistre"),
    ("planning", r"planning|calendrier|d[ée]lai|[ée]ch[ée]ance|date|roadmap|livraison|planif"),
    ("equipe", r"[ée]quipe|ressources? humaines|recrut|effectif|personnel|organisation|r[ôo]les?"),
    ("juridique", r"juridique|contrat|r[èe]glement|conformit[ée]|l[ée]gal|loi|audit|norme|assurance"),
    ("technique", r"technique|syst[èe]me|logiciel|r[ée]seau|infrastructure|\bSI\b|informatique|outil|applicati"),
    ("communication", r"communication|message|information|sensibilis|reporting|pr[ée]sentation"),
    ("qualite", r"qualit[ée]|indicateur|kpi|performance|r[ée]sultat|bilan|statistique|tableau de bord"),
    ("question", r"question|interrogation|incertitude"),
    ("decision", r"d[ée]cision|validation|arbitrage|approbation"),
]


# ------------------------------------------------------------------ utilitaires texte
def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ«\"'(\d])", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def clip(text: str, limit: int) -> str:
    """Coupe proprement (fin de phrase, sinon de mot) avec une ellipse."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    m = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if m > limit * 0.55:
        return cut[: m + 1]
    return cut[: cut.rfind(" ") if cut.rfind(" ") > limit * 0.6 else limit].rstrip(" ,;:") + "…"


def guess_icon(text: str, default: str = "objectif") -> str:
    low = (text or "").lower()
    for icon, pat in _KEYWORDS:
        if re.search(pat, low, re.I):
            return icon
    return default


def icon_or_guess(icon: str | None, text: str, default: str = "objectif") -> str:
    return icon if icon in ICONS else guess_icon(text, default)


def flow(text: str, limit: int) -> str:
    """Texte multi-paragraphes (courriel, document) tronqué proprement, paragraphes séparés par une ligne vide."""
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]
    out, used = [], 0
    for p in paras:
        if used + len(p) > limit:
            room = limit - used
            if room > 60:
                out.append(clip(p, room))
            elif out:
                out[-1] += " […]"
            break
        out.append(p); used += len(p) + 2
    return "\n\n".join(out)


def _chunks(items: list, n: int) -> list[list]:
    return [items[i:i + n] for i in range(0, len(items), n)] or [[]]


def _bullet_pages(items: list[str], max_chars: int = 950, max_items: int = 8) -> list[list[str]]:
    pages: list[list[str]] = [[]]
    used = 0
    for it in items:
        if pages[-1] and (used + len(it) > max_chars or len(pages[-1]) >= max_items):
            pages.append([]); used = 0
        pages[-1].append(it); used += len(it)
    return pages


def _paginate_rows(rows: list[list[str]], widths_in: list[float], pt: float = 14, budget_in: float = 4.6) -> list[list[list[str]]]:
    pages: list[list[list[str]]] = [[]]
    used = 0.0
    for row in rows:
        lines = max(max(1, math.ceil(len(str(c)) / max(1, int(w * 72 / (pt * 0.5))))) for c, w in zip(row, widths_in))
        h = max(0.5, lines * pt * 1.2 / 72 + 0.16)
        if pages[-1] and used + h > budget_in:
            pages.append([]); used = 0.0
        pages[-1].append(row); used += h
    return pages


def _suffix(title: str, i: int, n: int) -> str:
    return title if n == 1 else f"{title} ({i + 1}/{n})"


# ------------------------------------------------------------------ construction
def build_slides(a: dict, visual: bool, attachments: list[dict] | None = None) -> list[Slide]:
    out: list[Slide] = []
    out.append(_cover(a, visual))
    (_visual if visual else _standard)(a, out)
    if attachments:
        _annex_slides(a, attachments, visual, out)
    return out


KIND_ICON = {"email": "communication", "word": "juridique", "excel": "qualite", "pdf": "juridique", "powerpoint": "objectif",
             "texte": "juridique", "image": "idee", "autre": "juridique"}
MAX_ANNEX_DETAIL_SLIDES = 12


def _reinforcement(a: dict, out: list[Slide], visual: bool) -> None:
    """Ce que les pièces jointes apportent au rapport : suivi des actions antérieures, recoupement avec la réunion."""
    for title, icon, blk in (("Suivi des actions antérieures", "jalon", annex_mod.suivi_table(a)),
                             ("Recoupement avec les pièces jointes", "qualite", annex_mod.recoupement_table(a))):
        if blk:
            _tables(out, title, icon, blk["headers"], blk["rows"], blk["widths"], visual=visual)


def _annex_slides(a: dict, atts: list[dict], visual: bool, out: list[Slide]) -> None:
    """Pièces jointes : une liste, puis le détail utile (courriel, extrait, tableau, image) dans la limite de 12 diapositives."""
    from . import annexes
    summ = annexes.summaries(atts, a)
    mine = annexes.model_summaries(atts, a)          # résumé du modèle seulement (jamais l'aperçu, qui doublerait le texte)
    if visual:
        items = [{"title": clip(x["name"], 70), "detail": clip(summ[x["id"]], 130), "icon": KIND_ICON.get(x["kind"], "juridique"), "chip": x["label"]}
                 for x in atts]
        for i, page in enumerate(_chunks(items, CARDS_PER_SLIDE)):
            out.append({"layout": "cards", "title": _suffix("Pièces jointes", i, len(_chunks(items, CARDS_PER_SLIDE))), "icon": "juridique", "tone": "primary", "items": page})
    else:
        lines = [f"{x.get('n', i)}. {x['name']} ({x['label']}) — {clip(summ[x['id']], 110)}" for i, x in enumerate(atts, 1)]
        pages = _bullet_pages(lines)
        for i, page in enumerate(pages):
            out.append({"layout": "bullets", "title": _suffix("Pièces jointes", i, len(pages)), "paragraph": "", "items": page})
    n = 0
    for i0, x in enumerate(atts, 1):
        i = x.get("n", i0)                       # même numéro que les citations « PJ n » du rapport
        if n >= MAX_ANNEX_DETAIL_SLIDES:
            break
        e, meta = x["extract"], x["extract"].get("meta", {})
        ic = KIND_ICON.get(x["kind"], "juridique")
        if x["kind"] == "image" and e.get("image"):
            out.append({"layout": "image", "title": clip(f"Annexe {i} — {x['name']}", 80), "icon": ic, "id": x["id"], "caption": x["name"], "size": e.get("image_size")})
        elif x["kind"] == "excel" and e.get("tables"):
            t = e["tables"][0]
            cols = min(6, len(t["headers"]))
            title = f"Annexe {i} — {x['name']}" + (f" · {t['name']}" if len(e["tables"]) > 1 else "")
            out.append({"layout": "table", "title": clip(title, 80), "icon": ic, "headers": [clip(h, 30) for h in t["headers"][:cols]],
                        "rows": [[clip(c, 60) for c in r[:cols]] for r in t["rows"][:8]], "widths": [1 / cols] * cols, "charts": None})
        elif x["kind"] == "email":
            head = " · ".join(f"{k} : {meta[k]}" for k in ("De", "À", "Date") if meta.get(k))
            out.append({"layout": "bullets", "title": clip(f"Annexe {i} — {meta.get('Objet') or x['name']}", 80), "icon": ic,
                        "paragraph": head + "\n\n" + flow(e.get("text", ""), 850), "items": []})
        elif e.get("text"):
            lead = mine.get(x["id"])
            out.append({"layout": "bullets", "title": clip(f"Annexe {i} — {x['name']}", 80), "icon": ic,
                        "paragraph": (lead + "\n\n" if lead else "") + flow(e["text"], 800 if lead else 950), "items": []})
        else:
            continue
        n += 1


def _cover(a: dict, visual: bool) -> Slide:
    meta = [(k, v) for k, v in (("Date", a["date"]), ("Lieu", a["lieu"])) if v]
    if not visual and a["objet"]:
        meta.append(("Objet", a["objet"]))
    return {"layout": "cover", "title": a["titre"], "subtitle": "Synthèse de réunion" if visual else "Compte rendu de réunion",
            "meta": meta, "objet": a["objet"] if visual else ""}


def _actions_rows(a: dict) -> list[list[str]]:
    acts = sorted(a["actions"], key=lambda x: PRIO_ORDER.get(x.get("priorite", "moyenne"), 1))
    return [[str(i), annex_mod.cite(x.get("action", ""), x.get("pj")), x.get("responsable", "") or "À définir", x.get("echeance", "") or "À définir",
             (x.get("priorite") or "moyenne").capitalize()] for i, x in enumerate(acts, 1)]


ACTION_HEADERS = ["N°", "Action", "Responsable", "Échéance", "Priorité"]


def _action_charts(a: dict) -> dict | None:
    if not a["actions"]:
        return None
    prio = {"haute": 0, "moyenne": 0, "basse": 0}
    owners: dict[str, int] = {}
    for x in a["actions"]:
        prio[x.get("priorite") if x.get("priorite") in prio else "moyenne"] += 1
        o = (x.get("responsable") or "").strip()
        if o and o.lower() != "à définir":
            owners[o] = owners.get(o, 0) + 1
    top = sorted(owners.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {"priorities": prio, "owners": top if len(top) >= 2 else []}


def _tables(out: list[Slide], title: str, icon: str, headers, rows, widths, charts=None, visual=False, tone=None) -> None:
    if not rows:
        return
    narrow = [w * 7.9 for w in widths]      # 1re page : graphiques à droite
    full = [w * 12.1 for w in widths]
    if visual and charts:
        first = _paginate_rows(rows, narrow)[0]
        rest = rows[len(first):]
        pages = [first] + (_paginate_rows(rest, full) if rest else [])
    else:
        pages = _paginate_rows(rows, full)
    for i, page in enumerate(pages):
        out.append({"layout": "table", "title": _suffix(title, i, len(pages)), "icon": icon, "headers": headers, "rows": page,
                    "widths": widths, "charts": charts if (i == 0 and visual) else None})


def _standard(a: dict, out: list[Slide]) -> None:
    if a["objet"] or a["ordre_du_jour"]:
        out.append({"layout": "bullets", "title": "Objet et ordre du jour", "paragraph": a["objet"],
                    "items": [f"{i}. {t}" for i, t in enumerate(a["ordre_du_jour"], 1)]})
    if a["participants"]:
        _tables(out, "Participants", "equipe", ["Nom", "Fonction", "Statut"],
                [[p.get("nom", ""), p.get("fonction", ""), p.get("statut", "présent")] for p in a["participants"]],
                [0.4, 0.4, 0.2])
    if a["resume"]:
        out.append({"layout": "bullets", "title": "Synthèse", "paragraph": a["resume"], "items": []})
    for i, page in enumerate(_bullet_pages(a["enjeux"])):
        if page:
            out.append({"layout": "bullets", "title": _suffix("Enjeux", i, len(_bullet_pages(a["enjeux"]))), "paragraph": "", "items": page})
    points = a["points_abordes"]
    for n, p in enumerate(points[:MAX_TOPIC_SLIDES], 1):
        out.append({"layout": "topic", "title": p.get("sujet", f"Point {n}"), "number": n, "icon": None,
                    "summary": clip(p.get("discussion", ""), 520), "bullets": [clip(x, 220) for x in (p.get("positions") or [])[:4]],
                    "bullets_label": "Positions exprimées", "decisions": [clip(x, 200) for x in (p.get("decisions") or [])[:3]],
                    "notes": (p.get("discussion", "") + ("\n\n" + annex_mod.sources_line(p["pj"], a) if annex_mod.tag(p.get("pj")) else "")).strip()})
    if len(points) > MAX_TOPIC_SLIDES:
        rest = [f"{p.get('sujet', '')} — {clip(sentences(p.get('discussion', ''))[0] if sentences(p.get('discussion', '')) else '', 140)}"
                for p in points[MAX_TOPIC_SLIDES:]]
        for i, page in enumerate(_bullet_pages(rest)):
            out.append({"layout": "bullets", "title": "Autres points abordés", "paragraph": "", "items": page})
    _tables(out, "Décisions", "decision", ["N°", "Décision", "Responsable"],
            [[str(i), annex_mod.cite(d.get("decision", ""), d.get("pj")), d.get("responsable", "") or "—"] for i, d in enumerate(a["decisions"], 1)],
            [0.08, 0.67, 0.25])
    _tables(out, "Plan d'actions", "action", ACTION_HEADERS, _actions_rows(a), [0.07, 0.43, 0.2, 0.17, 0.13])
    _reinforcement(a, out, visual=False)
    for title, items in (("Points de vigilance", a["risques_vigilance"]), ("Recommandations et arbitrages attendus", a["recommandations"])):
        pages = _bullet_pages(items)
        for i, page in enumerate(pages):
            if page:
                out.append({"layout": "bullets", "title": _suffix(title, i, len(pages)), "paragraph": "", "items": page})
    last = ([f"Prochaine réunion : {a['prochaine_reunion']}"] if a["prochaine_reunion"] else []) + list(a["questions_ouvertes"])
    if last:
        out.append({"layout": "bullets", "title": "Questions ouvertes et suite", "paragraph": "", "items": last[:8]})


def _visual(a: dict, out: list[Slide]) -> None:
    # 1. La réunion en chiffres
    present = sum(1 for p in a["participants"] if p.get("statut", "présent") == "présent")
    tiles = [t for t in (
        {"value": str(present or len(a["participants"])), "label": "participants", "icon": "equipe"} if a["participants"] else None,
        {"value": str(len(a["decisions"])), "label": "décision" + ("s" if len(a["decisions"]) > 1 else ""), "icon": "decision"} if a["decisions"] else None,
        {"value": str(len(a["actions"])), "label": "action" + ("s" if len(a["actions"]) > 1 else ""), "icon": "action"} if a["actions"] else None,
        {"value": str(len(a["risques_vigilance"])), "label": "point" + ("s" if len(a["risques_vigilance"]) > 1 else "") + " de vigilance", "icon": "risque"} if a["risques_vigilance"] else None,
    ) if t]
    extra = [{"value": c.get("valeur", ""), "label": clip(c.get("libelle", ""), 48)} for c in a["chiffres_cles"][:4] if c.get("valeur")]
    if tiles or extra:
        out.append({"layout": "kpis", "title": "La réunion en chiffres", "icon": "qualite", "tiles": tiles, "extra": extra,
                    "highlight": clip(a["resume"], 330)})
    # 2. L'essentiel
    keys = [{"title": clip(m.get("titre", ""), 70), "detail": clip(m.get("detail", ""), 150),
             "icon": icon_or_guess(m.get("icone"), m.get("titre", "") + " " + m.get("detail", "")), "chip": ""}
            for m in a["messages_cles"][:6] if m.get("titre")]
    if not keys:   # analyses antérieures : on déduit les messages des sujets traités
        for p in a["points_abordes"][:4]:
            s = sentences(p.get("discussion", ""))
            keys.append({"title": clip(p.get("sujet", ""), 70), "detail": clip(p.get("essentiel") or (s[0] if s else ""), 150),
                         "icon": icon_or_guess(p.get("icone"), p.get("sujet", "") + " " + p.get("discussion", "")), "chip": ""})
    if not keys and a["resume"]:
        keys = [{"title": "Synthèse", "detail": clip(a["resume"], 150), "icon": "objectif", "chip": ""}]
    if keys:
        out.append({"layout": "cards", "title": "L'essentiel", "icon": "idee", "tone": "primary", "items": keys})
    # 3. Participants
    people = [{"nom": p.get("nom", ""), "fonction": p.get("fonction", ""), "statut": p.get("statut", "présent")} for p in a["participants"]]
    for i, page in enumerate(_chunks(people, PEOPLE_PER_SLIDE) if people else []):
        out.append({"layout": "people", "title": _suffix("Participants", i, len(_chunks(people, PEOPLE_PER_SLIDE))), "icon": "equipe", "people": page})
    # 4. Sujets
    points = a["points_abordes"]
    for n, p in enumerate(points[:MAX_TOPIC_SLIDES], 1):
        sents = sentences(p.get("discussion", ""))
        if p.get("essentiel"):        # champs dédiés aux diapositives, rédigés par le modèle
            summary, rest = p["essentiel"], sents
        else:                         # analyses antérieures : 1re phrase en résumé, les suivantes en puces (sans doublon)
            summary, rest = clip(sents[0], 230) if sents else "", sents[1:]
        bullets = [clip(b, 100) for b in (p.get("points_cles") or [])[:4]] or [clip(x, 100) for x in rest[:3]] \
            or [clip(x, 100) for x in (p.get("positions") or [])[:3]]
        out.append({"layout": "topic", "title": p.get("sujet", f"Point {n}"), "number": n,
                    "icon": icon_or_guess(p.get("icone"), p.get("sujet", "") + " " + p.get("discussion", "")),
                    "summary": summary, "bullets": bullets, "bullets_label": "", "decisions": [clip(d, 110) for d in (p.get("decisions") or [])[:2]],
                    "notes": (p.get("discussion", "") + ("\n\nPositions : " + " ; ".join(p["positions"]) if p.get("positions") else "")
                              + ("\n\n" + annex_mod.sources_line(p["pj"], a) if annex_mod.tag(p.get("pj")) else "")).strip()})
    if len(points) > MAX_TOPIC_SLIDES:
        out.append({"layout": "cards", "title": "Autres points abordés", "icon": "objectif", "tone": "primary",
                    "items": [{"title": clip(p.get("sujet", ""), 70), "detail": clip(p.get("essentiel") or " ".join(sentences(p.get("discussion", ""))[:1]), 120),
                               "icon": icon_or_guess(p.get("icone"), p.get("sujet", "")), "chip": ""} for p in points[MAX_TOPIC_SLIDES:MAX_TOPIC_SLIDES + 6]]})
    # 5. Décisions
    dec = [{"title": clip(d.get("decision", ""), 110), "detail": clip(d.get("contexte", ""), 110), "icon": "decision",
            "chip": " · ".join(x for x in (("Resp. : " + d["responsable"]) if d.get("responsable") else "", annex_mod.tag(d.get("pj"))) if x)}
           for d in a["decisions"]]
    for i, page in enumerate(_chunks(dec, CARDS_PER_SLIDE) if dec else []):
        out.append({"layout": "cards", "title": _suffix("Décisions prises", i, len(_chunks(dec, CARDS_PER_SLIDE))), "icon": "decision", "tone": "green", "items": page})
    # 6. Plan d'actions (tableau + graphiques)
    _tables(out, "Plan d'actions", "action", ACTION_HEADERS, _actions_rows(a), [0.07, 0.43, 0.2, 0.17, 0.13],
            charts=_action_charts(a), visual=True)
    _reinforcement(a, out, visual=True)
    # 7. Prochaines étapes (frise)
    def deadline_rank(x):
        e = (x.get("echeance") or "").strip().lower()
        return (PRIO_ORDER.get(x.get("priorite", "moyenne"), 1), 1 if (not e or e == "à définir") else 0)
    nxt = sorted(a["actions"], key=deadline_rank)[:5]
    if nxt:
        out.append({"layout": "timeline", "title": "Prochaines étapes", "icon": "jalon",
                    "steps": [{"label": clip(x.get("action", ""), 90), "when": x.get("echeance") or "À définir",
                               "who": x.get("responsable") or "À définir",
                               "tone": {"haute": "red", "moyenne": "amber", "basse": "green"}.get(x.get("priorite", "moyenne"), "amber")} for x in nxt]})
    # 8. Risques
    risks = [{"title": clip(r, 120), "detail": "", "icon": "risque", "chip": ""} for r in a["risques_vigilance"]]
    for i, page in enumerate(_chunks(risks, CARDS_PER_SLIDE) if risks else []):
        out.append({"layout": "cards", "title": _suffix("Points de vigilance", i, len(_chunks(risks, CARDS_PER_SLIDE))), "icon": "risque", "tone": "red", "items": page})
    # 9. Enjeux et recommandations
    er = [{"title": clip(t, 140), "detail": "", "icon": "idee", "chip": "Enjeu"} for t in a["enjeux"]] + \
         [{"title": clip(t, 140), "detail": "", "icon": "jalon", "chip": "Recommandation"} for t in a["recommandations"]]
    for i, page in enumerate(_chunks(er, CARDS_PER_SLIDE) if er else []):
        out.append({"layout": "cards", "title": _suffix("Enjeux et recommandations", i, len(_chunks(er, CARDS_PER_SLIDE))), "icon": "idee", "tone": "primary", "items": page})
    # 10. Suite
    last = ([{"title": "Prochaine réunion", "detail": clip(a["prochaine_reunion"], 140), "icon": "planning", "chip": ""}] if a["prochaine_reunion"] else []) + \
           [{"title": clip(q, 130), "detail": "", "icon": "question", "chip": "À clarifier"} for q in a["questions_ouvertes"]]
    if last:
        out.append({"layout": "cards", "title": "Suite et questions ouvertes", "icon": "question", "tone": "purple", "items": last[:CARDS_PER_SLIDE]})
