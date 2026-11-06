# GMeeting

Un « Plaud » auto-hébergé pour vos réunions : enregistrez (ou collez un lien vidéo, importez un fichier, un texte) et obtenez une
**transcription**, un **procès-verbal**, un **compte rendu**, une **note de synthèse** et des **présentations** (sobre ou illustrée),
exportables en **PDF, Word, Excel et PowerPoint**, enrichis de vos **pièces jointes** (mails Outlook, Word, Excel, PDF…).

**En bref** : enregistrement fiable même après un appel ou en **mode avion** · audio compact (≈ 12 Mo/h) · pièces jointes qui renforcent
le texte (sources, recoupements, suivi des actions précédentes) · gabarit à vos couleurs · confidentialité maîtrisée (transcription locale
possible, rétention configurable, protection CSRF, mot de passe).

## Démarrage rapide

**En local**

```bash
sudo apt install ffmpeg            # ou brew install ffmpeg
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # renseigner ANTHROPIC_API_KEY, puis : export $(grep -v '^#' .env | xargs)
uvicorn app.main:app               # http://localhost:8000
```

**Avec Docker et HTTPS automatique** (recommandé pour l'usage sur téléphone : le micro n'est autorisé qu'en HTTPS ou sur localhost)

```bash
cp .env.example .env               # renseigner ANTHROPIC_API_KEY, GMEETING_PASSWORD et DOMAIN (ex. reunions.mon-domaine.fr)
docker compose up -d               # Caddy obtient et renouvelle le certificat ; l'application n'est jamais exposée directement
```

> Les fichiers Docker/Caddy ont été validés syntaxiquement (`docker compose config`) mais **l'image n'a pas pu être construite ni lancée**
> dans l'environnement de développement (pas de démon Docker) : faites un premier essai avant de l'exposer.

Ouvrez l'application **une fois en ligne** (elle se met en cache pour fonctionner ensuite hors-ligne) et installez-la sur l'écran d'accueil.

## Configuration (variables d'environnement, voir `.env.example`)

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | – / `claude-sonnet-5-5` | Rédaction des documents (sortie structurée forcée, consignes anti-hallucination, analyse en deux temps pour les très longues réunions) |
| `TRANSCRIBE_PROVIDER` | `auto` | `local` (faster-whisper, `pip install faster-whisper`, 100 % hors-ligne), `openai` (`OPENAI_API_KEY`) ou `auto` (local si installé) |
| `GMEETING_PASSWORD` | vide | Active l'authentification (HTTP Basic, nom d'utilisateur libre) sur **toute** l'application, interface comprise |
| `KEEP_AUDIO` | `false` | Conserve un fichier Opus compact réécoutable ; sinon l'audio est supprimé après traitement réussi |
| `RETENTION_DAYS` | `0` | Supprime automatiquement les réunions terminées plus anciennes que N jours (audio, archive et pièces jointes compris) ; `0` = jamais |
| `AUDIO_KBPS` / `AUDIO_ENHANCE` | `32` / `true` | Débit Opus du fichier de travail (12-128) ; passe-haut + normalisation du volume |
| `MAX_UPLOAD_MB` | `1024` | Taille maximale d'un fichier audio/vidéo importé |
| `MAX_ATTACH_MB` / `MAX_ATTACH_PER_MEETING` / `ATTACH_CONTEXT_CHARS` | `25` / `20` / `120000` | Limites des pièces jointes et texte transmis à l'IA |
| `DATA_DIR` | `./data` | Base SQLite, archives, pièces jointes |
| `DOMAIN` | `localhost` | (Docker) nom de domaine pour le certificat HTTPS |

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

Joignez à une réunion les documents qui l'éclairent (convocation reçue par mail, compte rendu précédent, budget…). Ils servent à trois choses :

1. **Mieux rédiger** : leur contenu est transmis à l'IA comme *documents de référence* (jamais comme des propos tenus en réunion, et cités
   comme tels) pour orthographier les noms et acronymes, retrouver l'ordre du jour, les chiffres, le contexte. L'IA écrit aussi un résumé par pièce.
2. **Renforcer le contenu du rapport** (pas seulement l'accompagner) :
   * **sources citées** : chaque sujet, décision ou action appuyé sur une pièce l'indique (`[PJ 2]`, « Sources : PJ 2 (budget.xlsx) ») ;
   * **recoupement réunion / pièces jointes** : tableau des confirmations, **écarts** (ex. « 120 k€ examinés » contre « 95 k€ fixés » dans le CR précédent)
     et compléments, écarts en tête ; consigne stricte : en cas de doute, rien n'est listé (un faux écart est pire qu'un écart manqué) ;
   * **suivi des actions antérieures** : en joignant le PV précédent, le nouveau PV indique pour chaque action si elle est soldée, en cours,
     reportée ou non évoquée ;
   * **cohérence dans le temps** : numérotation stable (« PJ 3 » reste la même pièce même si une autre est retirée) ; si les pièces changent
     après la rédaction, un bandeau propose de **régénérer** pour que les rapports en tiennent compte.
3. **Les insérer en annexe de tous les rapports** : PV, CR, note de synthèse (PDF, Word, Excel) et présentations (standard et illustrée).
   Sans annexes, la liste des pièces citées reste affichée pour que les références restent compréhensibles.

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

## Confidentialité et sécurité

* **Vos données restent chez vous** : base SQLite et fichiers dans `DATA_DIR`. Seuls partent vers l'extérieur : le texte à rédiger (API de rédaction)
  et, hors transcription locale, l'audio (API de transcription). Avec `TRANSCRIBE_PROVIDER=local`, **seul le texte** quitte la machine ; pour un
  cloisonnement total, il faudrait un modèle de rédaction hébergé en interne (non fourni).
* **Rétention** : audio supprimé après traitement réussi (conservé en cas d'échec pour pouvoir relancer), archive optionnelle, purge automatique
  des vieilles réunions (`RETENTION_DAYS`), suppression manuelle à tout moment.
* **Authentification** : `GMEETING_PASSWORD` protège toutes les routes (interface comprise, sauf la sonde `/healthz`).
* **Protection CSRF** : toute requête modifiante venant d'un autre site est refusée (indispensable avec l'authentification Basic, dont les
  identifiants sont renvoyés automatiquement par le navigateur).
* **En-têtes** : politique de contenu stricte (aucun script inline ni externe), pas d'intégration en cadre, `nosniff`, micro autorisé uniquement pour
  l'application, réponses de l'API jamais mises en cache, HSTS derrière HTTPS.
* **Pièces jointes = données non fiables** : jamais exécutées (macros ignorées), exécutables refusés, archives Office contrôlées (zip-bombes), images
  ré-encodées, téléchargement forcé ; leur contenu est transmis à l'IA comme donnée, avec consigne de n'exécuter aucune instruction qui s'y trouverait.
* Le micro exige **HTTPS** (ou `localhost`) : utilisez le déploiement Docker + Caddy ou votre propre reverse-proxy TLS.

## Limites connues

* **Écran verrouillé / arrière-plan** : un site web ne peut pas garantir l'enregistrement dans ces cas (surtout iOS) ; un appel occupe le micro
  (le **mode avion** l'évite). Un enregistrement garanti en arrière-plan exigerait une application mobile native (non fournie).
* **Pas de reconnaissance des locuteurs** : l'attribution des propos repose sur les noms cités et la liste des participants ; relire le PV avant diffusion.
* **Textes générés non évalués en conditions réelles** : les tests utilisent une IA simulée (aucune clé en développement) ; la qualité des résumés,
  recoupements et suivis doit être jugée sur de vraies réunions. Les recoupements sont volontairement prudents.
* **Pièces jointes** : insérées en extrait structuré (texte, tableaux, image), pas fusionnées telles quelles ; anciens `.doc/.xls/.ppt` conservés mais non lus ;
  `.msg` testés sur des fichiers conformes à la spécification, pas sur un large échantillon de courriers réels (sinon, enregistrer en `.eml`).
* **Liens privés** (Teams, Zoom, Drive protégés) inaccessibles : importer le fichier. **Audio d'onglet** : Chrome/Edge sur ordinateur.
* **Hors-ligne** : l'audio n'existe que sur l'appareil jusqu'à l'envoi ; certains navigateurs (Safari) purgent les données d'un site peu utilisé.
* **Gabarit unique** pour toute l'installation. **Docker** non éprouvé en session (voir plus haut).

## Tests et intégration continue

```bash
pip install -r requirements-dev.txt && pytest          # 128 tests : exports, audio, enregistrements, pièces jointes, sécurité…
# Scénarios navigateur (Chromium, micro simulé) : appel, coupure réseau, rechargement, mode avion, audio, présentations, pièces jointes
PYTHON=python tests/e2e/run_all.sh                     # nécessite playwright (npm i -g playwright)
```

GitHub Actions (`.github/workflows/ci.yml`) exécute les tests Python (3.12 et 3.13) et vérifie la syntaxe de l'interface à chaque PR.

## Architecture

`app/main.py` (API) · `security.py` (auth, CSRF, en-têtes) · `pipeline.py` (acquisition → transcription → rédaction) · `ingest.py`, `recordings.py`,
`transcribe.py`, `generate.py` · `attachments.py`, `annexes.py` (pièces jointes) · `exporters.py` (PDF/Word/Excel), `slides.py` + `pptx_export.py` (PowerPoint) ·
`branding.py` (gabarit) · `retention.py` · `static/` (interface JS sans build : `app.js`, `recorder.js`, `sw.js`).
