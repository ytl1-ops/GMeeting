# Protection des données personnelles — guide GMeeting

> Document technique et pratique, **pas un avis juridique**. Les points de conformité (RGPD) sont à faire valider par votre délégué à la protection
> des données (DPO) ou un juriste, surtout pour des réunions contenant des données sensibles (santé, syndical, disciplinaire, judiciaire…).

Une réunion enregistrée contient des **données personnelles** : voix, noms, fonctions, propos, parfois des informations sensibles. GMeeting est
conçu pour qu'elles restent chez vous.

## 1. Principe
- L'application Android et l'interface web sont des **clients de VOTRE serveur** : vos réunions sont stockées sur ce serveur, pas chez l'éditeur de l'application.
- L'éditeur n'a **aucun accès** à vos données : pas de compte, pas de télémétrie, pas de publicité, pas d'outil de mesure d'audience.
- Deux services extérieurs peuvent recevoir du contenu **si vous les configurez** (voir §2) : un service d'IA pour la rédaction et, au choix, un service de transcription.

## 2. Où vont les données
| Donnée | Où elle est | Qui la reçoit | Combien de temps |
|---|---|---|---|
| Audio de la réunion | votre serveur ; sur le téléphone le temps de l'envoi | **OpenAI** seulement si la transcription n'est pas locale | supprimé après la rédaction (sauf `KEEP_AUDIO=true`) |
| Transcription, contexte, pièces jointes incluses | votre serveur | **Anthropic** (rédaction par IA), si configuré | jusqu'à suppression de la réunion, ou `RETENTION_DAYS` |
| Comptes rendus, présentations, exports | votre serveur ; fichiers téléchargés sur l'appareil | vous | à vous de les gérer ; un téléchargement est un fichier ordinaire |
| Pièces reçues par partage non rattachées | votre serveur (zone d'attente) | — | **effacées automatiquement après 24 h** |
| Mot de passe du serveur (Android) | téléphone, chiffré (Keystore) | — | jusqu'à déconnexion / désinstallation |

La page **« 🔒 Confidentialité »** de l'application affiche l'état réel de *votre* serveur (transcription locale ou non, IA configurée ou non, durée de conservation,
mot de passe, HTTPS). Elle ne dit que des faits lus dans la configuration.

## 3. Ce qui protège vos données — et son niveau de preuve
| Mesure | Niveau de preuve |
|---|---|
| Mot de passe sur **toute** l'application (interface comprise) | testé automatiquement |
| Protection CSRF, en-têtes de sécurité, CSP stricte, pas de cache de l'API, HSTS | testé automatiquement |
| HTTPS automatique (Caddy) dans le déploiement Docker ; HTTPS **obligatoire** dans l'application publiée | Docker vérifié en CI ; application : code, non testé sur téléphone |
| Suppression complète d'une réunion (audio, archive, transcription, documents, pièces jointes) | testé automatiquement |
| Effacement automatique des pièces reçues par partage jamais rattachées (24 h), même sans rétention | testé automatiquement |
| Rétention automatique optionnelle (`RETENTION_DAYS`) | testé automatiquement |
| Audio supprimé après rédaction par défaut | testé automatiquement |
| Pièces jointes traitées comme données non fiables (exécutables refusés, archives piégées contrôlées, macros jamais exécutées, images ré-encodées) | testé automatiquement |
| Sauvegardes en lecture réservée (0600), restauration refusant les archives piégées | testé automatiquement |
| Transcription **locale** possible (l'audio ne quitte pas le serveur) | fonctionnalité existante ; qualité à juger |
| Android : mot de passe chiffré (Keystore), pas de sauvegarde cloud du téléphone, copie de partage effacée après envoi et au démarrage | code ; non testé sur téléphone |
| Android : **écran protégé** (aperçu masqué, captures bloquées) activé par défaut dans la version publiée, désactivable | code ; non testé sur téléphone |

## 4. Ce qui n'est PAS fait (à savoir, et à compenser)
- **Pas de chiffrement au repos** de la base et des fichiers par l'application : activez le **chiffrement du disque ou du volume** sur le serveur.
- **Un seul mot de passe** partagé : pas de comptes individuels, pas de droits par réunion, pas d'authentification à deux facteurs. À réserver à une équipe de confiance, ou à placer derrière un accès réseau restreint (VPN, SSO du proxy).
- **Pas de journal d'accès** (qui a consulté quoi).
- **Pas de pseudonymisation** avant l'envoi au service d'IA : le texte part tel quel. Si c'est inacceptable pour certaines réunions, utilisez la transcription locale, n'activez pas la rédaction par IA pour elles, ou ne les enregistrez pas.
- **Pas de mécanisme automatisé** de demande d'accès : l'export se fait par sauvegarde (`python -m app.backup`) ou depuis les fichiers téléchargés.
- Les fichiers **téléchargés** (PDF, Word…) sortent de la protection de GMeeting : ce sont des fichiers ordinaires sur l'appareil. Mettez une **mention de confidentialité** dans le Gabarit et transmettez-les par un canal sûr.

## 5. Repères RGPD (à valider avec votre DPO)
- **Rôles** : en général, l'organisation qui fait enregistrer les réunions est **responsable de traitement** ; les fournisseurs d'IA et de transcription sont des **sous-traitants** (contrat de traitement des données à vérifier, et transferts hors Union européenne). L'éditeur de l'application n'est destinataire d'aucune donnée.
- **Information** : les personnes dont la voix est enregistrée doivent être informées **avant** l'enregistrement (finalité, destinataires, durée, droits). Une base légale doit exister (intérêt légitime, consentement, obligation… selon le cas). Pour des participants externes ou des sujets sensibles, privilégiez le consentement explicite.
- **Durée** : fixez `RETENTION_DAYS` à la durée dont vous avez réellement besoin ; ne conservez l'audio (`KEEP_AUDIO`) que s'il le faut.
- **Droits** : effacement (supprimer la réunion depuis sa fiche), accès et rectification (corriger la transcription puis régénérer, exporter).
- **Registre et analyse d'impact** : inscrivez ce traitement dans votre registre ; une analyse d'impact peut être nécessaire pour des données sensibles ou à grande échelle.
- **Violation de données** : prévoir qui prévient l'autorité de contrôle (notification en principe sous 72 heures) et les personnes concernées si nécessaire.

## 6. Liste de contrôle de l'administrateur
1. `GMEETING_PASSWORD` fort défini (le script `deploy/install.sh` le génère) ; changé si une personne quitte l'équipe.
2. HTTPS actif (la page Confidentialité l'indique) ; jamais de HTTP hors réseau local.
3. Disque du serveur **chiffré** ; accès SSH par clé ; pare-feu limité aux ports utiles.
4. Transcription : locale si possible ; sinon contrat et conditions du fournisseur relus.
5. `RETENTION_DAYS` et `KEEP_AUDIO` réglés selon le besoin réel.
6. Sauvegardes (`deploy/backup.sh`) **chiffrées hors du serveur** : une archive contient tous les comptes rendus.
7. Mention de confidentialité ajoutée dans le Gabarit ; consigne aux utilisateurs sur le partage des exports.
8. Participants informés avant chaque enregistrement (modèle ci-dessous).
9. Registre des traitements à jour ; procédure en cas de violation connue de l'équipe.
10. Mises à jour appliquées (`deploy/update.sh`, qui sauvegarde d'abord).

## 7. Modèle de message d'information des participants
> « Cette réunion est enregistrée et transcrite automatiquement afin de rédiger le compte rendu. L'enregistrement et le texte sont stockés sur le serveur de [organisation]
> pendant [durée]. Pour rédiger le compte rendu, le texte est traité par [fournisseur d'IA], notre sous-traitant. Vous pouvez demander l'accès, la rectification ou l'effacement
> de vos données auprès de [contact]. Si vous ne souhaitez pas être enregistré, dites-le avant le début. »
