# Pistes d'évolution (non engagées)

Idées étudiées et mises de côté volontairement. Aucune n'est implémentée. Priorité actuelle : essayer l'application sur de vrais téléphones
(`docs/ESSAI_LOCAL.md`), corriger ce qui casse, puis publier.

## Enrichissement par recherche web (Perplexity ou équivalent)
**Idée** : option du serveur, désactivée par défaut, qui interroge un moteur de recherche à réponses sourcées pour :
- vérifier l'orthographe ou l'identité d'un nom, d'une organisation ou d'un terme cité en réunion ;
- ajouter un contexte public (réglementation, actualité sectorielle) à la note de synthèse, avec sources ;
- renseigner un participant (fonction, société), uniquement sur demande explicite.

**Faisabilité** : simple. L'API Sonar de Perplexity suit un format proche de celui d'OpenAI ; le serveur appelle déjà des fournisseurs
externes. Non testé : aucune clé ni accès réseau dans l'environnement de développement.

**Pourquoi c'est en attente** :
- Contradiction avec la promesse « vos réunions restent chez vous » si du contenu de réunion part vers un tiers.
- Politique de confidentialité (`docs/PRIVACY_POLICY.md`) et formulaire « Sécurité des données » du Play Store à revoir.
- Peu de valeur tant que l'application n'a pas été éprouvée sur téléphone.

**Garde-fous si on la réalise** :
1. Désactivée par défaut ; clé API fournie par l'administrateur du serveur (variable d'environnement, jamais dans l'application).
2. Ne jamais envoyer la transcription ni le compte rendu : seulement des termes courts choisis par l'utilisateur, avec aperçu de ce qui part.
3. Résultats toujours présentés comme sources externes, séparés du contenu de la réunion (même principe que les pièces jointes : « documents de référence », jamais des propos tenus).
4. Journal des requêtes envoyées, et mention dans la politique de confidentialité.
5. Test avec un faux fournisseur dans la CI, comme pour la transcription et la rédaction.

## Autres pistes à garder en tête
- **Offre hébergée optionnelle** ou installation guidée en un clic : principal frein à l'adoption (il faut installer un serveur).
- **Partage natif des rendus** depuis l'application Android (feuille de partage : mail, messagerie) au lieu du seul téléchargement.
- **Reconnaissance des locuteurs** : actuellement relecture manuelle du PV avant diffusion.
- **Interface complète hors ligne** dans l'application (aujourd'hui, hors réseau, seuls Enregistrer et Terminer sont proposés).
