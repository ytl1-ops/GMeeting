# Fiche Google Play — textes prêts à coller

Visuels fournis dans ce dossier : `icone-512.png`, `banniere-1024x500.png`, `capture-*.png` (1079×1919, prises sur l'interface réelle avec des
données d'exemple — à remplacer par des captures du téléphone dès que vous aurez testé). Régénération : `python tests/e2e/store_assets.py`,
`node tests/e2e/store_screenshots.js` (serveur de test lancé).

## Français (langue par défaut)
**Titre (≤30)** : GMeeting – Comptes rendus
**Description courte (≤80)** : Enregistrez vos réunions : PV, CR et synthèse prêts à envoyer, chez vous.
**Description complète** :
Transformez chaque réunion en documents prêts à envoyer — sans confier vos enregistrements à un cloud tiers.

GMeeting enregistre vos réunions (ou importe un enregistrement, un lien vidéo, un texte) et rédige automatiquement :
• un procès-verbal, un compte rendu et une note de synthèse
• une présentation PowerPoint sobre, ou illustrée de pictogrammes et de chiffres clés
• des exports Word, PDF et Excel, avec votre logo et votre en-tête

Pensé pour les vraies réunions :
• L'enregistrement continue écran verrouillé et pendant un appel téléphonique
• Mode avion : l'audio est conservé et envoyé dès le retour du réseau
• Partagez un mail Outlook, un Word, un Excel ou un PDF vers GMeeting : ils enrichissent le compte rendu (noms, chiffres, ordre du jour)
• Audio mono optimisé voix : qualité claire, fichiers légers

Vos données restent chez vous : l'application se connecte à VOTRE serveur GMeeting. Aucune publicité, aucun pistage.

Prérequis : un serveur GMeeting (installation guidée par Docker, voir le guide du projet). L'application ne fonctionne pas sans serveur.

## English
**Title**: GMeeting – Meeting Minutes
**Short description**: Record meetings, get minutes & summaries ready to send — on your own server.
**Full description**: Turn every meeting into ready-to-send documents without handing recordings to a third-party cloud. GMeeting records (or imports
audio, video links, text) and writes formal minutes, a meeting report and an executive summary, plus plain or illustrated PowerPoint decks and
Word/PDF/Excel exports with your logo. Recording keeps going with the screen locked and during phone calls; airplane mode is supported (audio is
kept and uploaded later). Share Outlook emails, Word, Excel or PDF files to GMeeting to enrich the report. Your data stays on YOUR server — no ads, no
tracking. Requires a self-hosted GMeeting server (Docker guide included); the app does not work without one.

## Formulaires
- **Catégorie** : Productivité. **Public** : adultes (18+), pas destiné aux enfants.
- **Accès à l'application (reviewers)** : adresse d'un serveur de démonstration + mot de passe (OBLIGATOIRE : sans cela l'application est inutilisable pour le relecteur).
- **Contenu / classification** : aucune publicité ; pas de contenu généré par les utilisateurs partagé publiquement.
- **Sécurité des données** : aucune donnée collectée par l'éditeur (voir `docs/PLAYSTORE.md`).
- **Service de premier plan « microphone »** : enregistrement de réunion lancé par l'utilisateur, notification permanente visible ; vidéo : démarrer, verrouiller l'écran, notification, arrêter.
- **Politique de confidentialité** : URL publique de `docs/PRIVACY_POLICY.md` (à héberger).
