# Pistes d'évolution (non engagées)

Idées étudiées et mises de côté volontairement. Aucune n'est implémentée. Priorité actuelle : essayer l'application sur de vrais téléphones
(`docs/ESSAI_LOCAL.md`), corriger ce qui casse, puis publier.

## Pistes à garder en tête
- **Offre hébergée optionnelle** ou installation guidée en un clic : principal frein à l'adoption (il faut installer un serveur).
- **Partage natif des rendus** depuis l'application Android (feuille de partage : mail, messagerie) au lieu du seul téléchargement.
- **Reconnaissance des locuteurs** : actuellement relecture manuelle du PV avant diffusion.
- **Interface complète hors ligne** dans l'application (aujourd'hui, hors réseau, seuls Enregistrer et Terminer sont proposés).
- **Pseudonymisation avant l'envoi à l'IA** : remplacer noms, courriels et numéros par des jetons avant d'envoyer le texte au service d'IA, puis les rétablir dans le document. Réduit l'exposition des données personnelles ; à valider sur de vraies réunions (risque de perdre en qualité de rédaction).
- **Chiffrement au repos** de la base et des fichiers par l'application (aujourd'hui : chiffrement du disque du serveur recommandé).
- **Comptes individuels, droits par réunion, double authentification, journal d'accès** : aujourd'hui un seul mot de passe partagé.
- **Partage sécurisé d'un rendu** (lien à durée limitée ou envoi par la feuille de partage Android) : aujourd'hui, téléchargement puis partage par les moyens habituels.
