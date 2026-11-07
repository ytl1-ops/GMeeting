# Fiche Google Play — textes prêts à coller

Visuels fournis dans ce dossier : `icone-512.png`, `banniere-1024x500.png`, `capture-*.png` (1079×1919, prises sur l'interface réelle avec des
données d'exemple — à remplacer par des captures du téléphone dès que vous aurez testé). Régénération : `python tests/e2e/store_assets.py`,
`node tests/e2e/store_screenshots.js` (serveur de test lancé).

## Français (langue par défaut)
**Accroche** : « Le compte rendu est prêt avant que vous ayez rangé votre ordinateur. »
**Titre (≤30)** : GMeeting – Comptes rendus
**Description courte (≤80)** : Le compte rendu de vos réunions, prêt à envoyer. Sur votre serveur, chez vous.
**Description complète** :
Le compte rendu est prêt avant que vous ayez rangé votre ordinateur.

Vous sortez de réunion, GMeeting a déjà rédigé le document : procès-verbal, compte rendu ou note de synthèse, à l'en-tête de votre cabinet ou de votre entreprise. Fini la rédaction du soir.

CE QUE VOUS OBTENEZ
• Un procès-verbal, un compte rendu et une note de synthèse rédigés à partir de l'enregistrement
• Des exports Word, PDF et Excel, et une présentation PowerPoint sobre ou illustrée de pictogrammes et de chiffres clés
• Votre logo, votre couleur, votre en-tête sur chaque document

POUR LES VRAIES RÉUNIONS
• L'enregistrement continue écran verrouillé et pendant un appel téléphonique : il reprend seul et l'interruption est notée
• Sans réseau, l'audio est conservé sur le téléphone et envoyé dès que la connexion revient
• Partagez un mail Outlook, un Word, un Excel ou un PDF vers GMeeting : ils enrichissent le compte rendu (noms, chiffres, ordre du jour), avec leurs sources
• Importez aussi un enregistrement existant, un lien vidéo ou un texte
• Audio mono optimisé pour la voix : net, et des fichiers légers

VOS RÉUNIONS RESTENT CHEZ VOUS
L'application se connecte à VOTRE serveur GMeeting. Nous ne recevons ni vos enregistrements ni vos documents. Aucune publicité, aucun pistage.

IMPORTANT — À SAVOIR AVANT D'INSTALLER
GMeeting ne fonctionne pas seul : il faut un serveur GMeeting (le vôtre, celui de votre entreprise, ou un serveur installé pour vous). Un guide d'installation par Docker est fourni avec le projet. La rédaction et la transcription utilisent les clés de service d'IA configurées sur ce serveur.

Relisez toujours le procès-verbal avant de le diffuser : les propos ne sont pas attribués automatiquement à chaque participant.

## English
**Hook**: "Your meeting minutes are ready before you have packed your laptop."
**Title**: GMeeting – Meeting Minutes
**Short description**: Meeting minutes ready to send, drafted on your own server. Data stays yours.
**Full description**:
Your meeting minutes are ready before you have packed your laptop.

You leave the meeting and GMeeting has already drafted the document: formal minutes, a meeting report or an executive summary, under your firm's or company's letterhead. No more writing up at night.

WHAT YOU GET
• Formal minutes, a meeting report and an executive summary written from the recording
• Word, PDF and Excel exports, plus a plain or illustrated PowerPoint deck with icons and key figures
• Your logo, colour and letterhead on every document

BUILT FOR REAL MEETINGS
• Recording keeps going with the screen locked and during a phone call: it resumes by itself and the interruption is noted
• Without a network, audio is kept on the phone and uploaded when the connection returns
• Share an Outlook email, a Word, Excel or PDF file to GMeeting: they enrich the report (names, figures, agenda), with sources
• You can also import an existing recording, a video link or text
• Voice-optimised mono audio: clear sound, small files

YOUR MEETINGS STAY WITH YOU
The app connects to YOUR GMeeting server. We receive neither your recordings nor your documents. No ads, no tracking.

IMPORTANT — BEFORE YOU INSTALL
GMeeting does not work on its own: it needs a GMeeting server (yours, your company's, or one set up for you). A Docker installation guide ships with the project. Drafting and transcription use the AI service keys configured on that server.

Always review the minutes before sharing them: statements are not automatically attributed to each participant.

## À valider avant publication (promesses de la fiche)
Chaque phrase ci-dessous n'est vraie que si elle a été constatée sur de vrais téléphones et avec de vraies clés IA. À cocher avant d'envoyer la fiche :
- [ ] « Prêt avant que vous ayez rangé votre ordinateur » : mesurer le délai réel entre « Terminer » et le document, sur des réunions de 15, 30 et 60 minutes. Si le délai
      dépasse quelques minutes, adoucir l'accroche (« prêt peu après la réunion »). Google Play refuse les promesses trompeuses.
- [ ] « Continue écran verrouillé et pendant un appel » : testé sur au moins 3 modèles (dont Samsung et Xiaomi).
- [ ] « Sans réseau : conservé puis envoyé » : testé en mode avion de 5 minutes.
- [ ] « Partagez un mail Outlook… » : testé depuis l'application Outlook Android.
- [ ] Les captures d'écran viennent du téléphone et montrent un vrai compte rendu, pas les données d'exemple.
- [ ] Le serveur de démonstration fourni aux relecteurs fonctionne avec de vraies clés IA.

## Formulaires
- **Catégorie** : Productivité. **Public** : adultes (18+), pas destiné aux enfants.
- **Accès à l'application (reviewers)** : adresse d'un serveur de démonstration + mot de passe (OBLIGATOIRE : sans cela l'application est inutilisable pour le relecteur).
- **Contenu / classification** : aucune publicité ; pas de contenu généré par les utilisateurs partagé publiquement.
- **Sécurité des données** : aucune donnée collectée par l'éditeur (voir `docs/PLAYSTORE.md`).
- **Service de premier plan « microphone »** : enregistrement de réunion lancé par l'utilisateur, notification permanente visible ; vidéo : démarrer, verrouiller l'écran, notification, arrêter.
- **Politique de confidentialité** : URL publique de `docs/PRIVACY_POLICY.md` (à héberger).
