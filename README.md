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

Excel : un onglet par tableau (Participants, Décisions, Actions filtrables) + onglet Transcription horodatée.
La transcription est **éditable** (noms propres, acronymes) puis les 3 documents se **régénèrent** en un clic.

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
python tests/e2e/run_stub.py &  node tests/e2e/continuity.js
```
