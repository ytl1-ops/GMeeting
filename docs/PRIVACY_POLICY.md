# Politique de confidentialité — GMeeting (application Android)

*Dernière mise à jour : à renseigner. Éditeur : à renseigner (nom, adresse). Contact pour toute question de confidentialité : à renseigner.*

## En bref
- GMeeting est un **client** : il envoie vos enregistrements et fichiers **uniquement au serveur GMeeting dont vous avez saisi l'adresse** (le vôtre ou celui de votre organisation).
- L'éditeur de l'application **ne reçoit, ne stocke et ne consulte aucune de vos données**. Pas de publicité, pas de pistage, pas d'outil d'analyse, pas de compte chez l'éditeur.
- Vos réunions contiennent des données personnelles (voix, noms, propos) : leur protection dépend aussi du serveur que vous utilisez, voir « Votre serveur ».

## Données traitées par l'application
- **Audio** capté par le micro, uniquement quand vous lancez un enregistrement (notification permanente visible pendant toute la durée).
- **Fichiers, mails et liens** que vous choisissez de partager vers l'application (audio, Word, Excel, PDF, courriels…).
- **Adresse et mot de passe du serveur**, stockés chiffrés sur le téléphone (Android Keystore).
- **Segments audio en attente d'envoi**, conservés temporairement sur le téléphone puis supprimés après réception par le serveur.
- **Copies temporaires de partage** : faites le temps de l'envoi, supprimées aussitôt (et au démarrage suivant de l'application si elle a été interrompue).
- Le **réglage « écran protégé »** (préférence locale, sans donnée personnelle).

## Où vont les données
- Vers **votre serveur**, en HTTPS. Aucune autre destination dans l'application.
- Ce serveur peut utiliser des services extérieurs selon SA configuration : un service d'**IA** pour rédiger les comptes rendus et, au choix, un service de **transcription**. Ils agissent comme sous-traitants de l'administrateur du serveur, qui doit vous en informer. La page « Confidentialité » de l'application affiche ce que votre serveur fait réellement.

## Sécurité
- Connexion chiffrée (HTTPS obligatoire dans la version publiée), mot de passe stocké chiffré, aucune sauvegarde cloud des données de l'application.
- **Écran protégé** par défaut : l'aperçu dans les applications récentes est masqué et les captures d'écran sont bloquées (désactivable dans « Confidentialité »).
- Les pièces reçues par partage et jamais rattachées à une réunion sont **supprimées automatiquement après 24 heures** sur le serveur.
- Limites : les documents que vous exportez (PDF, Word, Excel, PowerPoint) sont des fichiers ordinaires sur votre téléphone ; protégez-les et partagez-les par un canal sûr. L'application ne chiffre pas elle-même les données du serveur : l'administrateur doit chiffrer son disque (voir le guide de protection des données du projet).

## Permissions
Micro (enregistrer), notifications (état de l'enregistrement), réseau, service de premier plan (enregistrer écran verrouillé), verrou de veille (ne pas couper l'enregistrement), stockage (Android 8 et 9 uniquement, pour enregistrer vos exports dans « Téléchargements »).

## Informer les personnes enregistrées
Avant d'enregistrer une réunion, informez les participants (finalité, destinataires, durée, droits) : la réglementation, dont le RGPD en Europe, l'exige. Un modèle de message figure dans `docs/PROTECTION_DONNEES.md`.

## Vos droits
Vous contrôlez vos données sur votre serveur : consultation, correction, export et **suppression définitive** d'une réunion (audio, transcription, documents et pièces jointes) depuis sa fiche. Pour une demande concernant les données d'une personne, adressez-vous à l'administrateur du serveur. Pour effacer les données locales de l'application : désinstaller l'application ou vider son stockage dans les réglages Android.

## Enfants
L'application s'adresse à des adultes dans un cadre professionnel.

## Modifications
Cette politique peut évoluer ; la date de dernière mise à jour figure en tête.
