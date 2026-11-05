"""Analyse d'exemple (fixture) – représentative de la sortie du modèle."""
from app import generate

RAW = {
    "titre": "Comité de pilotage sûreté – Site Nord",
    "date": "2026-11-04", "lieu": "Teams",
    "objet": "Faire le point sur les incidents du T3 et arbitrer le budget vidéoprotection 2027.",
    "participants": [
        {"nom": "Awa Koné", "fonction": "Directrice sûreté", "statut": "présent"},
        {"nom": "Marc Dubois", "fonction": "DSI", "statut": "présent"},
        {"nom": "Léa Martin", "fonction": "Achats", "statut": "excusé"},
    ],
    "ordre_du_jour": ["Bilan des incidents T3", "Budget vidéoprotection", "Questions diverses"],
    "resume": "Le comité a constaté une baisse de 18 % des incidents au T3. Le renouvellement des caméras du site Nord a été validé sous réserve d'un second devis.",
    "points_abordes": [
        {"sujet": "Bilan des incidents T3", "discussion": "Awa Koné a présenté une baisse de 18 % des incidents. Les intrusions nocturnes restent le principal sujet. Le DSI a souligné des angles morts.",
         "positions": ["Le DSI souhaite prioriser l'accès nord.", "Les Achats demandent deux devis."], "decisions": ["Maintenir le dispositif de rondes renforcé jusqu'à fin décembre."]},
        {"sujet": "Budget vidéoprotection", "discussion": "Le budget de 120 k€ a été examiné. Un second devis est nécessaire avant engagement.", "positions": [], "decisions": []},
    ],
    "decisions": [{"decision": "Valider le principe du renouvellement des caméras.", "responsable": "Awa Koné", "contexte": ""}],
    "actions": [
        {"action": "Obtenir un second devis caméras", "responsable": "Léa Martin", "echeance": "15/11/2026", "priorite": "haute"},
        {"action": "Cartographier les angles morts", "responsable": "Marc Dubois", "echeance": "À définir", "priorite": "basse"},
    ],
    "risques_vigilance": ["Retard de livraison des caméras (délai fournisseur 10 semaines)."],
    "enjeux": ["Réduire les intrusions nocturnes", "Tenir l'enveloppe budgétaire"],
    "recommandations": ["Arbitrer le budget sous 2 semaines."],
    "questions_ouvertes": ["Faut-il mutualiser avec le site Sud ?"],
    "prochaine_reunion": "Le 2 décembre 2026, même format.",
}
ANALYSIS = generate.normalize(RAW, {})
TRANSCRIPT = "[00:00:03] Bonjour à tous, on commence.\n[00:00:20] Le bilan du T3 montre une baisse de 18 %."


def stress_analysis():
    """Jeu de données extrême (textes très longs, nombreux éléments) pour tester la mise en page des présentations."""
    long = ("Le comité a examiné en détail l'ensemble des scénarios envisageables pour le renouvellement du parc de caméras, en tenant "
            "compte des contraintes budgétaires, des délais fournisseurs, de la conformité réglementaire et de l'impact sur l'exploitation. ") * 3
    icons = ["budget", "securite", "planning", "equipe", "technique", "juridique", "communication", "qualite"]
    a = dict(RAW)
    a["points_abordes"] = [{"sujet": f"Sujet {i} — {ic}", "discussion": long, "positions": ["Position " + "x " * 60, "Autre avis"],
                            "decisions": [f"Décision n°{i} : " + "valider le périmètre " * 4], "icone": ic,
                            "essentiel": "Il faut arbitrer le périmètre avant la fin du mois.", "points_cles": ["Périmètre à confirmer", "Budget plafonné"]}
                           for i, ic in enumerate(icons, 1)]
    a["participants"] = [{"nom": f"Prénom{i} Nom-Composé{i}", "fonction": "Directeur des opérations et de la sûreté du site",
                          "statut": ["présent", "excusé", "absent"][i % 3]} for i in range(14)]
    a["decisions"] = [{"decision": "Valider " + "le renouvellement complet des équipements " * 3, "responsable": f"Resp {i}", "contexte": "Sous réserve"} for i in range(9)]
    a["actions"] = [{"action": f"Réaliser l'action {i} " + "avec un libellé assez long pour tester le retour à la ligne " * 2,
                     "responsable": f"Resp {i % 4}", "echeance": "%02d/12/2026" % (i + 1), "priorite": ["haute", "moyenne", "basse"][i % 3]} for i in range(17)]
    a["risques_vigilance"] = ["Risque " + "important " * 15 for _ in range(8)]
    a["chiffres_cles"] = [{"valeur": "-18 %", "libelle": "incidents au T3"}, {"valeur": "120 k€", "libelle": "budget"}]
    a["messages_cles"] = [{"titre": "Les intrusions nocturnes restent le premier sujet de préoccupation", "detail": "Baisse de 18 % au T3.", "icone": "securite"},
                          {"titre": "Budget validé sous réserve", "detail": "Second devis exigé.", "icone": "budget"}]
    return generate.normalize(a, {})
