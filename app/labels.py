"""Langue des documents (français / anglais).

Les rapports sont construits en blocs neutres (exporters.py), les présentations en listes de diapositives (slides.py) : leurs intitulés fixes sont écrits
en français. Pour un rapport en anglais, `tr_deep` traduit ces intitulés juste avant le rendu ; le texte rédigé par le modèle n'est JAMAIS touché (il est
déjà dans la langue demandée, et seule une chaîne identique à un intitulé fixe français serait remplacée).
La langue d'un rapport se choisit à la création de la réunion (`report_lang`, « fr » par défaut) et est mémorisée dans l'analyse (`_lang`).
"""
from __future__ import annotations

import re
from typing import Any

LANGS = ("fr", "en")
DEFAULT_LANG = "fr"


def norm(lang: str | None) -> str:
    l = (lang or "").strip().lower()[:2]
    return l if l in LANGS else DEFAULT_LANG


def of(analysis: dict | None) -> str:
    return norm((analysis or {}).get("_lang"))


EN: dict[str, str] = {
    # types de documents
    "Procès-verbal": "Formal minutes", "Compte rendu": "Meeting report", "Note de synthèse": "Executive summary",
    "Présentation": "Presentation", "Présentation illustrée": "Illustrated presentation",
    "PROCÈS-VERBAL DE RÉUNION": "MEETING MINUTES", "COMPTE RENDU DE RÉUNION": "MEETING REPORT", "NOTE DE SYNTHÈSE": "EXECUTIVE SUMMARY",
    "Synthèse de réunion": "Meeting summary", "Compte rendu de réunion": "Meeting report",
    # en-tête / métadonnées
    "Objet": "Subject", "Date": "Date", "Lieu / outil": "Place / tool", "Réunion": "Meeting",
    # tableaux
    "Participants": "Participants", "Nom": "Name", "Fonction": "Role", "Statut": "Status", "N°": "No.", "Décision": "Decision", "Responsable": "Owner",
    "Décisions": "Decisions", "Actions": "Actions", "Action": "Action", "Échéance": "Due date", "Priorité": "Priority", "À définir": "TBD",
    "Haute": "High", "Moyenne": "Medium", "Basse": "Low", "présent": "present", "excusé": "excused", "absent": "absent",
    # sections
    "Ordre du jour": "Agenda", "Délibérations": "Deliberations", "Positions exprimées :": "Positions expressed:", "Décision(s) :": "Decision(s):",
    "Relevé des décisions": "Record of decisions", "Plan d'actions": "Action plan", "Actions à mener": "Actions to take",
    "Suivi des actions antérieures": "Follow-up of earlier actions", "Recoupement avec les pièces jointes": "Cross-check with the attachments",
    "Points de vigilance": "Points of attention", "Questions restées ouvertes": "Open questions", "Prochaine réunion": "Next meeting",
    "La séance est levée. Le présent procès-verbal est établi pour servir et valoir ce que de droit.": "The meeting is closed. These minutes are drawn up to serve and be valid as required.",
    "Le/la secrétaire de séance": "The meeting secretary", "Le/la président(e) de séance": "The chair of the meeting",
    "Résumé": "Summary", "Points abordés": "Topics discussed", "Synthèse": "Summary", "Points clés": "Key points", "Décisions prises": "Decisions made",
    "Autres points abordés": "Other topics discussed", "Prochaines étapes": "Next steps", "La réunion en chiffres": "The meeting in figures",
    "Pièces jointes": "Attachments", "Pièces jointes citées": "Attachments cited", "Annexes — pièces jointes": "Annexes — attachments", "Annexes": "Annexes",
    "Pièce jointe": "Attachment", "Type": "Type", "Résumé du modèle": "Summary",
    "Recoupement": "Cross-check", "Suivi antérieur": "Earlier follow-up", "Sujet": "Topic", "En réunion": "In the meeting", "Constat": "Finding",
    "Action antérieure": "Earlier action", "Commentaire": "Comment", "Source": "Source",
    "Confirmé": "Confirmed", "Écart": "Gap", "Complément": "Addition", "Soldée": "Closed", "En cours": "In progress", "Reportée": "Postponed", "Non évoquée": "Not discussed",
    "Pièces jointes de ce message :": "Attachments of this message:", "Extrait : le contenu complet figure dans la pièce jointe d'origine.": "Excerpt: the full content is in the original attachment.",
    "[…] Extrait : le contenu complet figure dans la pièce jointe d'origine.": "[…] Excerpt: the full content is in the original attachment.",
    # courriels (métadonnées des pièces jointes)
    "De": "From", "À": "To", "Cc": "Cc",
    # diapositives
    "Positions exprimées": "Positions expressed", "Points": "Points", "À clarifier": "To clarify", "décision": "decision", "décisions": "decisions",
    "action": "action", "actions": "actions", "participant": "participant", "participants": "participants",
    "point de vigilance": "point of attention", "points de vigilance": "points of attention",
    "RÉPARTITION PAR PRIORITÉ": "BREAKDOWN BY PRIORITY", "Visuel décoratif aux couleurs de l'organisation": "Decorative visual in the organisation's colours",
    "Visuel décoratif": "Decorative visual", "Logo": "Logo",
    # types de pièces jointes
    "E-mail Outlook (.msg)": "Outlook email (.msg)", "E-mail (.eml)": "Email (.eml)", "Document Word": "Word document", "Classeur Excel": "Excel workbook",
    "Fichier CSV": "CSV file", "Document PDF": "PDF document", "Présentation PowerPoint": "PowerPoint presentation", "Texte": "Text", "Image": "Image", "Fichier": "File",
    # pied de page et divers
    "Page": "Page", "Horodatage": "Timestamp", "Transcription": "Transcript", "Informations": "Details", "Sans titre": "Untitled",
}

PATTERNS: list[tuple[re.Pattern, Any]] = [
    (re.compile(r"^Annexe (\d+) — (.*)$", re.S), lambda m: f"Annex {m[1]} — {m[2]}"),
    (re.compile(r"^(\d+) première\(s\) ligne\(s\) sur (\d+)$"), lambda m: f"first {m[1]} row(s) of {m[2]}"),
    (re.compile(r"^Extrait : (.*)\. Données complètes dans la pièce jointe d'origine\.$", re.S), lambda m: f"Excerpt: {m[1]}. Full data in the original attachment."),
    (re.compile(r"^→ voir l'onglet « (.*) » \((\d+) ligne\(s\)\)$", re.S), lambda m: f"→ see the “{m[1]}” sheet ({m[2]} row(s))"),
    (re.compile(r"^Prochaine réunion : (.*)$", re.S), lambda m: f"Next meeting: {m[1]}"),
    (re.compile(r"^Resp\. : (.*)$", re.S), lambda m: f"Owner: {m[1]}"),
    (re.compile(r"^(.*) \((\d+)/(\d+)\)$", re.S), None),   # suffixe de pagination « (1/2) » : traité plus bas
    (re.compile(r"^(\d+) pièce\(s\) jointe\(s\)$"), lambda m: f"{m[1]} attachment(s)"),
]
_PJ = re.compile(r"\bPJ (\d+)")
_TAG = re.compile(r"\bPJ\b")


def tr(s: str, lang: str) -> str:
    """Traduit un intitulé fixe (exact ou motif) ; toute autre chaîne est rendue telle quelle."""
    if lang != "en" or not isinstance(s, str) or not s:
        return s
    core = s.strip()
    if core in EN:
        return s.replace(core, EN[core])
    for pat, f in PATTERNS:
        m = pat.match(core)
        if m and f is not None:
            return s.replace(core, f(m))
    # intitulés composés « Titre (suite) » : on traduit l'intitulé de base
    m = re.match(r"^(.*?)( \(\d+/\d+\)| \(suite\))$", core, re.S)
    if m and m[1] in EN:
        return s.replace(core, EN[m[1]] + (" (continued)" if m[2] == " (suite)" else m[2]))
    # références aux pièces jointes « PJ 2 » → « Att. 2 » (chaînes courtes générées par le code, jamais le texte rédigé)
    if len(core) < 80 and _TAG.search(core):
        return _TAG.sub("Att.", s)
    return s


def tr_deep(obj: Any, lang: str) -> Any:
    """Traduit récursivement les chaînes d'une structure de blocs / diapositives (dictionnaires, listes, tuples)."""
    if lang != "en":
        return obj
    if isinstance(obj, str):
        return tr(obj, lang)
    if isinstance(obj, list):
        return [tr_deep(x, lang) for x in obj]
    if isinstance(obj, tuple):
        return tuple(tr_deep(x, lang) for x in obj)
    if isinstance(obj, dict):
        # on ne traduit pas les clés ni les valeurs techniques (type de bloc, icône, couleur, identifiant…)
        keep = {"t", "layout", "icon", "tone", "id", "color", "chip_tone", "name_key"}
        return {k: (v if k in keep else tr_deep(v, lang)) for k, v in obj.items()}
    return obj


# comparaisons internes tolérantes aux deux langues (le modèle écrit « present » en anglais)
PRESENT = {"présent", "present"}
TBD = {"à définir", "tbd"}
