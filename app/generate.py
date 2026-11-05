"""Analyse d'une transcription → structure unique exploitable pour PV, CR et note de synthèse."""
from __future__ import annotations

from typing import Any

from . import config

STR = {"type": "string"}
STR_LIST = {"type": "array", "items": STR}

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titre": {**STR, "description": "Titre court et explicite de la réunion."},
        "date": {**STR, "description": "Date de la réunion si mentionnée, sinon vide."},
        "lieu": {**STR, "description": "Lieu ou outil de visioconférence si mentionné, sinon vide."},
        "objet": {**STR, "description": "Objet / finalité de la réunion en 1-2 phrases."},
        "participants": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "nom": STR, "fonction": {**STR, "description": "Fonction/organisation si connue."},
                "statut": {"type": "string", "enum": ["présent", "excusé", "absent"]}},
                "required": ["nom"]},
        },
        "ordre_du_jour": STR_LIST,
        "resume": {**STR, "description": "Synthèse exécutive de 5 à 8 lignes."},
        "points_abordes": {
            "type": "array",
            "description": "Un élément par sujet traité, dans l'ordre de la réunion.",
            "items": {"type": "object", "properties": {
                "sujet": STR,
                "discussion": {**STR, "description": "Contenu des échanges, fidèle et neutre, au passé."},
                "positions": {**STR_LIST, "description": "Positions/avis divergents notables, avec attribution si connue."},
                "decisions": STR_LIST},
                "required": ["sujet", "discussion"]},
        },
        "decisions": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "decision": STR, "responsable": STR, "contexte": STR}, "required": ["decision"]},
        },
        "actions": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "action": STR,
                "responsable": {**STR, "description": "Nom ou 'À définir'."},
                "echeance": {**STR, "description": "Date ou délai exprimé, sinon 'À définir'."},
                "priorite": {"type": "string", "enum": ["haute", "moyenne", "basse"]}},
                "required": ["action", "responsable", "echeance"]},
        },
        "risques_vigilance": {**STR_LIST, "description": "Risques, blocages, points d'attention évoqués."},
        "enjeux": {**STR_LIST, "description": "Enjeux principaux pour la note de synthèse."},
        "recommandations": {**STR_LIST, "description": "Recommandations / arbitrages attendus de la direction."},
        "questions_ouvertes": STR_LIST,
        "prochaine_reunion": {**STR, "description": "Date/objet de la prochaine réunion si évoquée."},
    },
    "required": ["titre", "objet", "resume", "points_abordes", "decisions", "actions"],
}

SYSTEM = """Tu es un secrétaire de séance expert, rigoureux et neutre, spécialisé dans la rédaction de comptes rendus \
professionnels en français (gouvernance, sûreté, gestion des risques, pilotage de projets).

Règles impératives :
- Tu t'appuies UNIQUEMENT sur la transcription et le contexte fournis. N'invente aucun nom, chiffre, date, décision ou \
engagement. Si une information manque, laisse le champ vide ou écris « À définir ».
- Les transcriptions automatiques contiennent des erreurs (noms propres, acronymes, homophones) : corrige-les quand le \
contexte le permet, sans extrapoler.
- Distingue nettement ce qui a été DÉCIDÉ (décision), ce qui reste À FAIRE (action avec responsable et échéance si \
exprimés) et ce qui a seulement été DISCUTÉ.
- Style : phrases complètes, factuelles, au passé pour les échanges, à l'infinitif ou au présent pour les actions. \
Pas de jugement ni d'interprétation.
- Rédige en français, quelle que soit la langue source (traduis fidèlement si nécessaire)."""


def _context_block(meta: dict[str, Any]) -> str:
    rows = []
    for key, label in [("title", "Titre indiqué"), ("meeting_date", "Date"), ("location", "Lieu"),
                       ("participants", "Participants connus"), ("context", "Contexte / consignes")]:
        if meta.get(key):
            rows.append(f"- {label} : {meta[key]}")
    return "\n".join(rows) or "- (aucun contexte fourni)"


def _client():
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY non défini : impossible de rédiger les comptes rendus.")
    import anthropic
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _chunks(text: str, size: int) -> list[str]:
    out, cur, n = [], [], 0
    for line in text.splitlines():
        if n + len(line) > size and cur:
            out.append("\n".join(cur)); cur, n = [], 0
        cur.append(line); n += len(line) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def _partial_notes(client, transcript: str, progress) -> str:
    """Pour les très longues réunions : notes détaillées par tronçon, puis analyse sur les notes."""
    parts = _chunks(transcript, config.MAX_DIRECT_CHARS // 3)
    notes = []
    for i, part in enumerate(parts, 1):
        progress(f"Analyse du tronçon {i}/{len(parts)}…")
        r = client.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=8000, system=SYSTEM,
            messages=[{"role": "user", "content":
                       "Extrait de transcription (tronçon %d/%d). Produis des notes détaillées et fidèles : sujets, "
                       "arguments, positions, décisions, actions (qui/quoi/quand), chiffres, noms cités.\n\n%s"
                       % (i, len(parts), part)}],
        )
        notes.append(f"### Tronçon {i}\n" + "".join(b.text for b in r.content if b.type == "text"))
    return "\n\n".join(notes)


def analyze(transcript: str, meta: dict[str, Any], progress=lambda m: None) -> dict[str, Any]:
    client = _client()
    material = transcript
    if len(material) > config.MAX_DIRECT_CHARS:
        material = _partial_notes(client, material, progress)
    progress("Rédaction du PV, du CR et de la note de synthèse…")
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        system=SYSTEM,
        tools=[{"name": "enregistrer_analyse", "description": "Enregistre l'analyse structurée de la réunion.",
                "input_schema": ANALYSIS_SCHEMA}],
        tool_choice={"type": "tool", "name": "enregistrer_analyse"},
        messages=[{"role": "user", "content":
                   f"Contexte fourni par l'utilisateur :\n{_context_block(meta)}\n\n"
                   f"Transcription (horodatée si disponible) :\n<transcription>\n{material}\n</transcription>\n\n"
                   "Analyse cette réunion et appelle l'outil avec le résultat complet."}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return normalize(block.input, meta)
    raise RuntimeError("La réponse du modèle ne contient pas d'analyse exploitable.")


def normalize(a: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Garantit la présence de toutes les clés pour que les exports ne plantent jamais."""
    a = dict(a)
    for k in ("titre", "date", "lieu", "objet", "resume", "prochaine_reunion"):
        a[k] = (a.get(k) or "").strip()
    for k in ("participants", "ordre_du_jour", "points_abordes", "decisions", "actions",
              "risques_vigilance", "enjeux", "recommandations", "questions_ouvertes"):
        a[k] = a.get(k) or []
    a["titre"] = a["titre"] or meta.get("title") or "Réunion"
    a["date"] = a["date"] or meta.get("meeting_date") or ""
    a["lieu"] = a["lieu"] or meta.get("location") or ""
    return a
