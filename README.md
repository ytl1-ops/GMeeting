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
```
