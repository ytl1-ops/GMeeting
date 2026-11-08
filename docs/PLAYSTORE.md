# GMeeting sur Google Play — décisions et marche à suivre

## Ce qui est honnête de dire d'abord
- Personne ne peut garantir qu'une application sera « incontournable » : le classement Play dépend des installations, des notes,
  de la rétention et de la concurrence (Plaud, Otter, Notta, Samsung…). Ce dossier maximise ce qui dépend du produit et de la fiche.
- **Seul le propriétaire du compte développeur peut publier** : compte Play (25 $, vérification d'identité), clé de signature,
  formulaires de conformité, tests sur de vrais téléphones. Rien de cela n'est fait ni simulable ici.
- Le code Android est compilé par la CI GitHub (workflow `android`) mais **n'a pas été exécuté sur un téléphone réel**.
  Prévoir un test manuel complet (liste ci-dessous) avant tout envoi.

## Positionnement décidé
**« Le compagnon de réunion qui reste chez vous. »** Plaud/Otter envoient l'audio dans leur cloud, facturent à la minute et
exigent un boîtier ou un abonnement. GMeeting : serveur auto-hébergé (données et clés IA chez l'utilisateur), PV / CR / note de
synthèse, exports Word/PDF/Excel/PowerPoint, pièces jointes qui enrichissent le compte rendu, enregistrement qui survit à l'appel
téléphonique, au verrouillage et au mode avion.
Cible : indépendants, cabinets, PME, DSI/sûreté/juridique soucieux de confidentialité (RGPD, secret professionnel).

## Architecture retenue
Application Android = **client du serveur de l'utilisateur** (modèle Nextcloud / Home Assistant), pas un service hébergé par nous.
- Coque Kotlin + WebView : réutilise 100 % de l'interface web (une seule base de code à maintenir).
- Enregistreur natif en service de premier plan (type microphone) : segments AAC d'une minute, enchaînement sans coupure,
  file d'envoi persistante (WorkManager), reprise automatique, journal des interruptions d'appel.
- « Partager vers GMeeting » : lien de visio, audio, mails Outlook, Word, Excel, PDF.
- HTTPS obligatoire, mot de passe chiffré (Keystore), aucune télémétrie, aucune publicité, aucune bibliothèque d'analyse.

## Points à décider/valider par le propriétaire (je ne peux pas le faire à votre place)
1. **Identifiant d'application** (`app.gmeeting.android` par défaut) : définitif après publication. Vérifier la marque « GMeeting »
   (risque de confusion avec Google Meet) — envisager un nom plus distinctif pour la fiche.
2. **Reviewer Play** : l'application exige un serveur. Fournir dans « Accès à l'application » l'adresse d'un serveur de démonstration
   et son mot de passe, sinon rejet quasi certain.
3. **Comptes personnels** : test fermé obligatoire (12 testeurs, 14 jours) avant la production.
4. **Déclaration du service de premier plan « microphone »** + courte vidéo de démonstration (enregistrement visible, notification).
5. **Politique de confidentialité** publique : `docs/PRIVACY_POLICY.md` à héberger sur une URL (GitHub Pages convient) en renseignant
   l'éditeur et le contact.
6. **Formulaire Sécurité des données** : voir réponses proposées ci-dessous.
7. **Signature et test interne** : procédure complète dans `docs/TEST_INTERNE_PLAY.md` (clé d'envoi via `android/tools/make-upload-key.sh`, secrets GitHub, workflow `android-release`, Play App Signing).
   **Cible API 36 (Android 16)** exigée pour toute nouvelle application depuis le 31/08/2026 : à relever chaque année (`android/tools/check-release.sh` en donne le minimum).

## Formulaire « Sécurité des données » (réponses proposées, à vérifier dans la console)
- **Point délicat** : l'éditeur ne reçoit aucune donnée, mais l'application **transmet** de l'audio et des fichiers hors de l'appareil (vers le serveur choisi par l'utilisateur).
  Selon la définition de Google, une donnée transmise hors de l'appareil peut compter comme « collectée » même si elle ne va pas chez l'éditeur. **Déclarer prudemment** :
  *Fichiers audio* et *Fichiers et documents* → collectés, **chiffrés en transit**, finalité « fonctionnalité de l'application », **suppression possible** par l'utilisateur,
  non partagés avec des tiers par l'éditeur ; et expliquer dans la description « Partage de données » que la destination est le serveur de l'utilisateur. Vérifier la formulation
  exacte avec l'assistant de la console et, au besoin, avec le support Google Play.
- Pas de publicité, pas d'identifiant publicitaire, pas d'analyse d'usage.
- Si le serveur de l'utilisateur utilise un fournisseur d'IA ou de transcription, c'est son choix et sa responsabilité : c'est dit dans la fiche et dans la page « Confidentialité » de l'application.
- Guide complet et mesures réelles : `docs/PROTECTION_DONNEES.md` ; politique à publier : `docs/PRIVACY_POLICY.md`.

## Fiche (français — à traduire en anglais pour l'international)
- **Titre (≤30)** : GMeeting – Comptes rendus
- **Description courte (≤80)** : voir `docs/store/FICHE.md` (accroche : « Le compte rendu est prêt avant que vous ayez rangé votre ordinateur »).
- **Mots-clés à placer naturellement dans la description** : compte rendu de réunion, procès-verbal, transcription, enregistreur de
  réunion, note de synthèse, dictaphone, Word, PowerPoint, auto-hébergé, confidentialité, hors ligne.
- **Texte long** : problème (réunions mal retranscrites) → solution (une touche, le PV/CR/synthèse arrive) → différenciateurs
  (continue pendant un appel, mode avion, partage depuis Outlook, pièces jointes qui renforcent le rapport, exports) →
  confidentialité (votre serveur) → prérequis honnête (nécessite un serveur GMeeting, guide Docker fourni).
- **Visuels** : icône 512, bannière 1024×500 et captures fournies dans `docs/store/` (voir `docs/store/FICHE.md`, textes FR/EN prêts à coller) ; remplacer les captures par celles du téléphone après vos essais.


## Ce qui fait vraiment monter une application (hors de ce dépôt)
Pas de raccourci : une fiche sincère, une première minute réussie (assistant de connexion simple), une note ≥ 4,5 obtenue par de vrais
utilisateurs, des mises à jour régulières, des réponses aux avis. Éviter tout achat d'avis/installations (interdit, risque de bannissement).
**Principal frein à l'adoption** : devoir installer un serveur. Pistes (hors périmètre actuel) : offre hébergée optionnelle, ou installation guidée en un clic.

## Test manuel obligatoire sur téléphone (avant envoi)
1. Installation, connexion (mauvais mot de passe, mauvaise adresse, certificat invalide) — messages clairs ?
2. Enregistrer 10 min écran verrouillé ; vérifier la notification permanente et le document final.
3. Recevoir un appel pendant l'enregistrement : l'enregistrement reprend-il ? l'interruption est-elle notée ?
4. Mode avion 5 min puis retour du réseau : tous les segments sont-ils envoyés, la réunion créée ?
5. Tuer l'application pendant l'enregistrement : la session est-elle récupérée au relancement ?
6. Partage depuis Outlook/Word/Excel/PDF, lien YouTube/Teams ; export et téléchargement des fichiers.
7. Appareils variés (Samsung, Xiaomi, Pixel) : économiseurs de batterie agressifs, Android 8 → 15.
