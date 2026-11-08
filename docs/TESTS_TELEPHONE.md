# Tests à faire sur téléphone

À cocher au fur et à mesure. **Durée** : environ 3 h au total (les parties A à E suffisent pour un premier verdict, ~1 h).
Tout ce qui est ici n'a **jamais été exécuté sur un vrai téléphone** : c'est le but. Notez ce qui se passe réellement, même si c'est « bien » ou « bizarre ».

## 0. Préparation (10 min)
- [ ] Serveur lancé sur le PC : `./deploy/local.sh` (voir `docs/ESSAI_LOCAL.md`) ; clés IA dans `.env` ; PC et téléphone sur le même Wi-Fi ; port 8000 ouvert. Test : `http://IP-DU-PC:8000` s'ouvre dans le navigateur du téléphone.
- [ ] APK de test installé (GitHub → Actions → workflow **android** → artefact **android-build** → `app-debug.apk`).
- [ ] Réglages Android → Applications → GMeeting → Batterie → **Sans restriction** (à refaire en « Optimisée » pour le test I3).
- [ ] Autoriser micro et notifications quand demandé.
- [ ] Noter : **modèle du téléphone**, **version d'Android**, langue du téléphone, adresse du serveur, réseau (Wi-Fi/4G).
- [ ] Un second téléphone ou un ami pour appeler (parties C).
- Version de test (« debug ») : accepte `http://`, écran protégé **désactivé** par défaut. La version publiée exige HTTPS et protège l'écran par défaut (voir H).

## A. Installation et connexion
| # | Test | Attendu | Résultat |
|---|---|---|---|
| A1 | Ouvrir l'application la première fois | écran de connexion (adresse + mot de passe), texte dans la langue du téléphone | |
| A2 | Adresse fausse (`foo`, `192.168.1.250:8000` éteinte) | message clair : adresse invalide / serveur injoignable | |
| A3 | Bon serveur, **mauvais mot de passe** | « Mot de passe refusé par le serveur. » | |
| A4 | Bon serveur, bon mot de passe | l'interface s'ouvre ; fermer et rouvrir l'application : plus de connexion demandée | |
| A5 | Saisir `IP:8000` sans `http://` | accepté (version de test uniquement) | |
| A6 | Bouton **retour** Android dans l'interface | revient en arrière dans les pages, puis quitte | |

## B. Enregistrement
| # | Test | Attendu | Résultat |
|---|---|---|---|
| B1 | Enregistrer 2 min, écran allumé, parler distinctement, **Terminer et générer** | notification permanente avec chronomètre, boutons Pause / Terminer ; la réunion apparaît, devient « Prêt », les documents sont cohérents | |
| B2 | **Écran verrouillé** pendant 5 min | l'enregistrement continue (notification toujours là) ; le texte couvre bien les 5 min | |
| B3 | Passer dans une autre application (messagerie, navigateur) pendant 3 min | continue sans interruption | |
| B4 | **Pause / Reprendre** depuis la notification, puis depuis l'application | l'état suit ; le chrono se fige en pause | |
| B5 | Bouton **⭐ Marquer** deux fois | repères pris en compte (mentionnés dans le contexte de la réunion) | |
| B6 | **Continuité** : compter « un, deux, trois… » sans s'arrêter pendant 3 min | aucun mot manquant autour de chaque minute pleine dans la transcription (segments d'une minute) | |
| B7 | Balayer l'application des applications récentes **pendant** un enregistrement | l'enregistrement continue (notification) ; rouvrir l'application : le chrono et les boutons sont retrouvés | |
| B8 | Terminer depuis la **notification** (bouton Terminer) | l'enregistrement se termine ; la réunion se crée | |
| B9 | Refuser l'autorisation micro | message clair, pas de plantage | |
| B10 | Android 13+ : refuser les notifications | noter ce qui se passe (l'enregistrement doit rester possible) | |

## C. Appels téléphoniques
| # | Test | Attendu | Résultat |
|---|---|---|---|
| C1 | **Appel entrant** pendant l'enregistrement, répondre 30 s, raccrocher | notification « Micro occupé (appel ?) — reprise automatique », puis reprise **toute seule** ; le texte reprend après l'appel | |
| C2 | Appel entrant **refusé / sans réponse** | l'enregistrement continue | |
| C3 | **Appel sortant** pendant l'enregistrement | même comportement que C1 | |
| C4 | Appel **WhatsApp / Teams / Meet** (audio) | noter si le micro est repris ou perdu | |
| C5 | Après C1 : ouvrir le compte rendu | l'interruption est mentionnée dans le contexte (« Interruptions techniques ») | |

## D. Mode avion et réseau
| # | Test | Attendu | Résultat |
|---|---|---|---|
| D1 | Démarrer l'enregistrement, **activer le mode avion 5 min**, le désactiver, terminer | rien n'est perdu ; la réunion se crée et se génère au retour du réseau | |
| D2 | **Mode avion avant** de lancer l'application | page « Serveur injoignable » avec boutons ● Enregistrer / ■ Terminer (ou interface en cache) | |
| D3 | Depuis D2 : enregistrer 2 min, terminer, **puis** réseau | la réunion apparaît dans la liste et se génère ; l'heure de début est celle de l'enregistrement | |
| D4 | Arrêter le serveur du PC pendant un enregistrement, le relancer ensuite | rien n'est perdu ; envoi repris | |
| D5 | Changer de Wi-Fi vers la 4G (serveur joignable) pendant un enregistrement | continue ; envoi repris | |

## E. Partager vers GMeeting
| # | Test | Attendu | Résultat |
|---|---|---|---|
| E1 | Partager un **lien** (YouTube / Teams) depuis le navigateur ou l'application source | « Envoi vers GMeeting… » puis ouverture de la réunion | |
| E2 | Partager un **fichier audio** depuis le gestionnaire de fichiers | réunion créée à partir du fichier | |
| E3 | Partager un **PDF**, un **Word**, un **Excel** | rattachés comme pièces jointes (« Pièce partagée ») du prochain rapport | |
| E4 | Partager un **mail** depuis Outlook (ou Gmail) | pièce jointe créée ; contenu lu (expéditeur, objet) | |
| E5 | Partager **plusieurs fichiers** à la fois | tous pris en compte | |
| E6 | Créer ensuite un rapport avec ces pièces | le rapport les cite et les annexe (« PJ 1 », annexes) | |
| E7 | Partager sans réseau | message d'échec clair, aucune copie ne reste (voir H5) | |
| E8 | Partager avec un mauvais mot de passe enregistré | « Mot de passe refusé : reconnectez-vous. » | |

## F. Récupérer les rendus (téléchargements)
Pour chacun : toucher le bouton d'export → une **notification de téléchargement** apparaît → toucher pour ouvrir.
| # | Rendu | Ouvrir avec | Résultat |
|---|---|---|---|
| F1 | PV en PDF / Word / Excel | lecteur PDF / Word / Excel (ou Drive) | |
| F2 | CR en PDF / Word / Excel | idem | |
| F3 | Note de synthèse en PDF / Word / Excel | idem | |
| F4 | Présentation (sobre) en PowerPoint | PowerPoint / Google Slides | |
| F5 | Présentation illustrée en PowerPoint | idem : pictogrammes et graphiques visibles | |
| F6 | Transcription « ⬇ .txt » | « Enregistré dans Téléchargements » | |
| F7 | **Android 8 ou 9** (si disponible) | demande d'autorisation de stockage, puis téléchargement | |
- [ ] Noms de fichiers lisibles (accents), logo et en-tête du **Gabarit** présents, pied de page numéroté.

## G. Français / anglais
| # | Test | Attendu | Résultat |
|---|---|---|---|
| G1 | Téléphone en **français** | application, notifications et écran de connexion en français | |
| G2 | Téléphone en **anglais** | tout en anglais | |
| G3 | Bouton **FR \| EN** dans l'en-tête | change la langue de l'interface (rechargement) ; choix mémorisé | |
| G4 | Créer une réunion avec « Langue du rapport » = **Anglais** (même interface en français) | documents (PV, CR, note, PowerPoint, Word, Excel, PDF) en anglais, intitulés compris | |
| G5 | Réunion parlée en anglais, rapport en français (et l'inverse) | rapport dans la langue demandée | |
| G6 | Onglet *Informations* : changer la langue du rapport, enregistrer, **Régénérer** | documents régénérés dans la nouvelle langue | |
- [ ] Noter tout texte resté dans la mauvaise langue (capture d'écran).

## H. Confidentialité et protection des données
| # | Test | Attendu | Résultat |
|---|---|---|---|
| H1 | Page **🔒 Confidentialité** | les valeurs correspondent à votre `.env` (transcription locale ou non, IA, conservation, mot de passe, HTTPS) | |
| H2 | Activer **« Protéger l'écran »** | captures d'écran refusées ; l'aperçu dans les applications récentes est **vide** | |
| H3 | Désactiver l'option | captures et aperçu de nouveau possibles | |
| H4 | Supprimer une réunion | disparaît de la liste ; fichiers du serveur supprimés (dossiers `audio/`, `archive/`, `attachments/` du volume de données) | |
| H5 | Après un partage (E1 à E5) | le dossier de cache de l'application ne contient plus de fichier de partage (Réglages → Applications → GMeeting → Stockage : le cache n'augmente pas durablement) | |
| H6 | Pièce partagée **jamais rattachée** | disparue du serveur après 24 h (vérifier le lendemain dans le dossier `attachments/`) | |
| H7 | Sans mot de passe sur le serveur (`GMEETING_PASSWORD` vide, à essayer sur le réseau local seulement) | la page Confidentialité affiche l'alerte | |
| H8 | **Version publiée** (bundle signé, via test interne Play) | écran protégé **activé par défaut** ; HTTP refusé, HTTPS exigé | |

## I. Durée, batterie, stockage
| # | Test | Mesure | Résultat |
|---|---|---|---|
| I1 | Enregistrement de **30 min** écran verrouillé | % de batterie consommé ; taille de l'audio envoyé (attendu ≈ 7 Mo, profil « Équilibré ») | |
| I2 | Enregistrement de **60 min** | ne s'arrête pas seul ; texte complet ; batterie | |
| I3 | Refaire B2 avec la batterie en **« Optimisée »** (réglage par défaut) | l'enregistrement survit-il à 30 min d'écran verrouillé ? sinon marque et modèle à noter | |
| I4 | Téléphone **en veille** (Doze) 30 min pendant l'enregistrement | continue | |
| I5 | Stockage presque plein | message d'avertissement, pas de perte | |

## J. Délai de génération (valide l'accroche de la fiche)
Mesurer avec de **vraies clés IA** : temps entre « Terminer et générer » et le document prêt.
| Réunion | Temps | Résultat |
|---|---|---|
| 15 min | | |
| 30 min | | |
| 60 min | | |
- [ ] Si le délai dépasse quelques minutes : adoucir l'accroche de la fiche (« prêt peu après la réunion »).
- [ ] Qualité du compte rendu : noms, chiffres, décisions et actions corrects ? À relire avant diffusion.

## K. Qualité audio (plusieurs téléphones)
- [ ] Téléphone posé sur la table, 4 personnes à 1–2 m : voix lisibles dans la transcription ?
- [ ] Salle bruyante : essayer les profils « Équilibré » puis « Haute qualité ».
- [ ] Au moins **3 modèles** dont **Samsung** et **Xiaomi** (ou Huawei) si possible, et **Android 8 à 15** couvert dans la mesure du possible.

## Si quelque chose casse — à me transmettre
1. Numéro du test (ex. C1) et ce qui était attendu / ce qui s'est passé.
2. **Modèle**, **version d'Android**, langue du téléphone, version de test (debug) ou publiée.
3. Capture d'écran ou courte vidéo ; l'heure approximative.
4. Côté serveur, les dernières lignes affichées dans le terminal de `./deploy/local.sh`.
5. Si l'application s'est fermée : « Réglages → Applications → GMeeting → Batterie » (restriction ou non).

## Synthèse (à remplir)
| Zone | OK | À corriger | Bloquant pour le Play Store |
|---|---|---|---|
| A. Connexion | | | |
| B. Enregistrement | | | |
| C. Appels | | | |
| D. Mode avion / réseau | | | |
| E. Partage | | | |
| F. Rendus | | | |
| G. Langues | | | |
| H. Confidentialité | | | |
| I. Batterie / durée | | | |
| J. Délai de génération | | | |
