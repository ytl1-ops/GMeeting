# GMeeting

Un « Plaud » auto-hébergé : enregistrez une réunion (ou collez un lien vidéo, importez un fichier, un texte),
et obtenez automatiquement une **transcription**, puis un **procès-verbal**, un **compte rendu** et une
**note de synthèse**, exportables en **PDF, Word (.docx) et Excel (.xlsx)**.

## Fonctionnalités

| Entrée | Détail |
|---|---|
| 🎙 Enregistrement navigateur | Micro seul (présentiel) ou **micro + audio de l'onglet** (Teams / Meet / Zoom web), pause, niveau sonore, sauvegarde locale de l'audio |
| 🔗 Lien vidéo/audio | Toute source gérée par [yt-dlp](https://github.com/yt-dlp/yt-dlp) (YouTube, Vimeo, LinkedIn, Loom, Dailymotion, PeerTube…) + liens directs `.mp4/.mp3`. **Sous-titres natifs utilisés en priorité** (rapide, gratuit), sinon transcription de l'audio |
| 📁 Fichier | mp3, m4a, wav, mp4, webm, mkv… (Plaud, dictaphone, export Teams/Zoom) |
| 📝 Texte | Transcription existante → rédaction directe |

| Document | Contenu |
|---|---|
| **PV** | Formel : participants/statuts, ordre du jour, délibérations point par point (positions, décisions), relevé des décisions, plan d'actions, signatures |
| **CR** | Concis : résumé, points abordés, décisions, actions (responsable, échéance, priorité) |
| **Note de synthèse** | 1-2 pages orientée décideur : synthèse, enjeux, points clés, risques, actions prioritaires, arbitrages attendus |
| **Présentation** (.pptx) | Sobre : une diapositive par sujet (résumé, positions, décisions), tableaux des décisions et des actions, risques, suite. Aucune illustration |
| **Présentation illustrée** (.pptx) | Visuelle : image d'ouverture, **chiffres clés**, « l'essentiel » en cartes avec **pictogrammes**, avatars des participants, une diapositive illustrée par sujet, décisions en cartes, plan d'actions avec **graphiques** (priorités, charge par responsable), **frise** des prochaines étapes, risques, questions ouvertes |

Excel : un onglet par tableau (Participants, Décisions, Actions filtrables) + onglet Transcription horodatée.
La transcription est **éditable** (noms propres, acronymes) puis les 3 documents se **régénèrent** en un clic.

## Pièces jointes : mails Outlook, Word, Excel, PDF…

Joignez à une réunion les documents qui l'éclairent (convocation reçue par mail, compte rendu précédent, budget…). Ils servent à deux choses :

1. **Mieux rédiger** : leur contenu est transmis à l'IA comme *documents de référence* (jamais comme des propos tenus en réunion, et cités
   comme tels) pour orthographier les noms et acronymes, retrouver l'ordre du jour, les chiffres, le contexte. L'IA écrit aussi un résumé par pièce.
2. **Les insérer en annexe de tous les rapports** : PV, CR, note de synthèse (PDF, Word, Excel) et présentations (standard et illustrée).

| Format | Ce qui est extrait et inséré |
|---|---|
| **E-mail Outlook `.msg`** et **`.eml`** | de, à, cc, date, objet, corps (HTML converti en texte), liste des pièces jointes du message |
| **Word `.docx`** | texte, tableaux, titre et auteur |
| **Excel `.xlsx` / `.csv`** | valeurs calculées (macros jamais exécutées), dates et nombres formatés ; un **onglet par feuille** dans l'export Excel (200 lignes), extrait de 25 lignes en PDF/Word |
| **PDF** | texte des 30 premières pages (signale un PDF scanné ou protégé) |
| **PowerPoint `.pptx`** | texte des diapositives et notes |
| **Texte / images** | texte ; image ré-encodée en PNG et **insérée à l'échelle** |
| Anciens `.doc/.xls/.ppt`, autres | conservés et téléchargeables, contenu non extrait (enregistrez en `.docx/.xlsx/.pptx`) |

Où : à la création (« Informations et pièces jointes »), ou plus tard dans l'onglet **Pièces jointes** de la réunion (voir le contenu extrait,
inclure/exclure chaque pièce, télécharger l'original, supprimer, régénérer). À l'export, la case **« Insérer les pièces jointes en annexe »**
active ou non les annexes. Chaque pièce reste téléchargeable dans son format d'origine.

**Limites honnêtes** : les documents sont insérés sous forme d'*extrait structuré* (texte, tableaux, image), pas fusionnés tels quels (pas de
copie intégrale d'un Word ou d'un Excel dans le rapport) ; les `.doc/.xls/.ppt` anciens ne sont pas lus ; le `.msg` a été testé sur des fichiers
conformes à la spécification, pas sur un large échantillon de courriers réels (en cas de souci, enregistrer le mail en `.eml`).

**Sécurité** : une pièce jointe est une donnée non fiable. Jamais exécutée (macros ignorées), exécutables et scripts refusés, archives Office
contrôlées contre les zip-bombes, images ré-encodées, téléchargement forcé sans interprétation par le navigateur, taille et nombre limités.
Son contenu est transmis à l'IA entre balises de données avec consigne de n'exécuter aucune instruction qui s'y trouverait.

## Qualité audio et taille des enregistrements

Configuration choisie sur mesure (poids mesurés sur un signal de test ; sur de la voix réelle, ils sont en général plus bas) :

| Étape | Avant | Maintenant |
|---|---|---|
| **Capture navigateur** | stéréo, ≈ 128 kbps (≈ 52 Mo/h mesuré) | **mono, profil au choix** : Économique 24 kbps (≈ 11 Mo/h max), **Équilibré 32 kbps (≈ 14 Mo/h max, défaut)**, Haute qualité 64 kbps (≈ 29 Mo/h max) — soit ≈ 75 % de données en moins en Équilibré |
| **Fichier de travail** | MP3 48 kbps (≈ 21 Mo/h) | **Opus mono 16 kHz « voix » 32 kbps** (≈ 12-14 Mo/h) : fréquence utile à la parole et à Whisper, meilleure intelligibilité qu'un MP3 de même débit |
| **Archive** (`KEEP_AUDIO=true`) | tous les fichiers bruts | **un seul fichier Opus compact**, réécoutable dans l'interface (lecture avec avance/retour) |

Détails : passe-haut 70 Hz et normalisation du volume (`AUDIO_ENHANCE`, rattrape les enregistrements faibles) ; **VBR contraint** car, mesuré, le VBR
libre d'Opus dépassait sa cible de plus de 50 % sur certains sons ; débit réglable (`AUDIO_KBPS`, 12-128). Moins de données = envoi plus rapide
et **moins de stockage en mode avion**. Le choix du profil est mémorisé. Sur Safari (AAC), le plancher est de 32 kbps.

## Compagnon de réunion en continu

L'enregistreur est conçu pour **ne jamais perdre une réunion**, y compris après un appel téléphonique :

* **Écriture locale d'abord** : chaque segment audio (~4 s) est stocké sur l'appareil (IndexedDB) puis envoyé au
  serveur ; il n'est effacé qu'une fois acquitté. Réseau coupé ? L'audio s'accumule et part au retour de la connexion.
* **Reprise automatique du micro** : si le système coupe ou occupe le micro (appel entrant, autre application), l'état
  « interrompu » s'affiche, puis le micro est rouvert tout seul à la fin de l'appel. Si le navigateur exige un geste,
  un bouton « Reprendre l'enregistrement » apparaît. Les interruptions sont journalisées et transmises à la rédaction.
* **Enregistreur surveillé** : relance automatique si le système l'arrête, contexte audio réveillé, verrou d'écran
  repris au retour au premier plan.
* **Récupération** : page fermée ou rechargée en pleine réunion → bannière « Récupérer et générer les documents ».
  Un enregistrement non finalisé côté serveur peut aussi être finalisé depuis sa fiche.
* **Fin d'enregistrement hors-ligne** : la finalisation reprend seule au retour du réseau.
* **Mode avion** : l'enregistrement démarre, se poursuit et se termine **sans aucun réseau**. L'identifiant et l'heure de
  début sont générés sur l'appareil ; la réunion est déclarée au serveur au retour de la connexion (avec sa vraie date),
  puis l'audio est envoyé et les documents générés automatiquement. Un appel ne peut pas couper un micro en mode avion.
  Astuce : activez le mode avion puis rallumez le Wi-Fi seul si vous voulez garder l'envoi en continu sans réseau mobile.
  Prérequis : avoir ouvert l'application **une fois en ligne** (le service worker met l'interface en cache) ; l'installer sur
  l'écran d'accueil est recommandé. Le démarrage affiche un conseil tant que ce n'est pas prêt.
* **Marqueurs ⭐** : repérez les moments importants ; ils orientent la rédaction.
* **Indicateur REC** permanent dans l'en-tête, même en naviguant ; application **installable** (PWA) et interface
  ouvrable hors-ligne.
* En cas d'échec de traitement, l'audio est **conservé** et le traitement relançable (supprimé seulement après succès).

**Limites des navigateurs** : un site web ne peut pas garantir l'enregistrement écran verrouillé ou application en
arrière-plan (surtout iOS). Gardez la page ouverte et l'écran allumé ; pendant un appel, mettez l'appel en haut-parleur
ou utilisez le micro d'un autre appareil. Un enregistrement continu en arrière-plan garanti exigerait une application
native (non fournie). Hors-ligne, l'audio n'existe que sur l'appareil jusqu'à l'envoi : envoyez-le dans les jours qui suivent (certains
navigateurs, notamment Safari, purgent les données d'un site peu utilisé ; l'application installée est mieux protégée),
et gardez de la place (≈ 30-60 Mo par heure). Un avertissement s'affiche si l'espace est faible.

## Gabarit personnalisable (menu « 🎨 Gabarit »)

Logo, nom de l'organisation, texte d'en-tête, pied de page, mention de confidentialité (en rouge) et couleur des
titres/tableaux, avec aperçu en direct. Appliqué à tous les exports : en-tête sur chaque page en PDF et Word,
bandeau en tête de l'onglet principal et pied d'impression en Excel. Le logo est ré-encodé en PNG (≤ 800×300 px) et
stocké dans `DATA_DIR/branding/`. Sans configuration, le rendu par défaut est inchangé.

## Démarrage

```bash
sudo apt install ffmpeg            # ou brew install ffmpeg
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # renseigner les clés, puis : export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload      # http://localhost:8000
```

Ou avec Docker : `docker build -t gmeeting . && docker run -p 8000:8000 -v gmeeting:/data --env-file .env gmeeting`

### Moteurs

* **Rédaction** : Claude (`ANTHROPIC_API_KEY`, modèle configurable via `ANTHROPIC_MODEL`). Sortie structurée forcée ;
  consignes anti-hallucination (aucun nom/chiffre/décision inventé, « À définir » si absent). Réunions très longues :
  analyse en deux temps automatique.
* **Transcription** : `TRANSCRIBE_PROVIDER=local` (faster-whisper, `pip install faster-whisper`, **100 % hors-ligne**) ou
  `openai` (`OPENAI_API_KEY`, découpage automatique en segments de 10 min). `auto` = local si installé.

## Confidentialité et sécurité

* Audio **supprimé après traitement** (sauf `KEEP_AUDIO=true`). Données dans `DATA_DIR` (SQLite).
* `GMEETING_PASSWORD` active une authentification HTTP Basic (utilisateur quelconque, mot de passe défini).
* Pour des réunions sensibles : transcription `local` ; seul le **texte** est alors envoyé à l'API de rédaction.
  Pour un cloisonnement total, il faut un modèle de rédaction hébergé en interne (non fourni).
* Le micro exige **HTTPS** (ou `localhost`). En production, placez l'application derrière un reverse-proxy TLS.

## Limites connues

* Pas de reconnaissance des locuteurs (diarisation) : l'attribution des propos repose sur ce que dit la transcription
  (noms cités) et sur la liste de participants fournie ; vérifier toujours le PV avant diffusion.
* Liens privés (Teams, Zoom, Drive protégés) inaccessibles : télécharger puis importer le fichier.
* La capture de l'audio d'onglet nécessite Chrome/Edge (bureau) ; Firefox/Safari : micro seul.
* L'enregistrement navigateur est conservé en mémoire jusqu'à l'envoi : prévoir ≤ 3-4 h par session.

## Tests

```bash
pip install -r requirements-dev.txt && pytest
# Scénarios navigateur (appel, coupure réseau, rechargement…) – nécessite playwright :
python tests/e2e/run_stub.py &  node tests/e2e/continuity.js && node tests/e2e/decks.js && node tests/e2e/audio.js
# pièces jointes (+ lecteur audio) : python tests/e2e/make_attachments.py /tmp/pj ; KEEP_AUDIO=true python tests/e2e/run_stub.py &
FILES_DIR=/tmp/pj node tests/e2e/attachments.js
```
