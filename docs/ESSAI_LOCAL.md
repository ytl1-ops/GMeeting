# Essayer GMeeting aujourd'hui sur votre téléphone (avant le Play Store)

Deux éléments : **le serveur** (sur votre PC, ou sur votre serveur) et **l'application** (APK de test à installer à la main).

## 1. Lancer le serveur sur votre PC (même Wi-Fi que le téléphone)
```bash
git clone https://github.com/ytl1-ops/GMeeting && cd GMeeting
git checkout claude/meeting-recording-app-va7j0s
./deploy/local.sh
```
Le script (Linux/macOS ; sous Windows, utilisez WSL) crée l'environnement, génère un mot de passe fort dans `.env`, affiche l'adresse à saisir dans
l'application (par ex. `192.168.1.20:8000`) puis lance le serveur. Ouvrez le fichier `.env` pour y mettre vos clés (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`), relancez, et autorisez le port 8000 dans le pare-feu. `ffmpeg` doit être installé.
Test : ouvrez l'adresse affichée (`http://192.168.1.20:8000`) dans le navigateur du téléphone.

*Pour un usage durable (HTTPS, sauvegardes, démarrage automatique)* : `DEPLOY.md` (Docker + Caddy).

## 2. Installer l'application de test (APK « debug »)
1. GitHub → dépôt `ytl1-ops/GMeeting` → onglet **Actions** → workflow **android** → dernière exécution verte de la branche
   `claude/meeting-recording-app-va7j0s` → section **Artifacts** → télécharger **android-build** (zip) → extraire `app-debug.apk`.
2. Transférer l'APK sur le téléphone, l'ouvrir, autoriser « installer des applications inconnues » pour l'application utilisée.
3. Ouvrir GMeeting → adresse `192.168.1.20:8000` (sans http://, version de test uniquement) + mot de passe → **Se connecter**.
4. Autoriser le micro et les notifications quand c'est demandé. Sous Android, désactiver l'optimisation de batterie pour GMeeting
   (Réglages → Applications → GMeeting → Batterie → Sans restriction) : certains constructeurs (Xiaomi, Samsung, Huawei) tuent sinon l'enregistrement.

## 3. Tests à faire dès aujourd'hui (5 min chacun)
1. Enregistrer 2 min, écran verrouillé → Terminer → le compte rendu arrive ?
2. Passer un appel pendant l'enregistrement → l'enregistrement reprend ? L'interruption figure dans le rapport ?
3. Mode avion 3 min en enregistrant, puis réseau rétabli → la réunion apparaît ?
4. Partager un lien (Teams/YouTube), un PDF, un mail Outlook vers GMeeting.
5. Tuer l'application pendant l'enregistrement, la rouvrir → l'enregistrement partiel est-il récupéré ?
Notez ce qui casse (modèle de téléphone, version Android, moment) et transmettez-le : je corrige.

## Limites de cette version de test
- HTTP autorisé **uniquement** dans l'APK debug ; la version Play Store exigera HTTPS.
- Jamais testée sur téléphone réel avant vous : attendez-vous à des défauts sur certains modèles.
- Si le serveur est injoignable (mode avion), la page d'accueil propose des boutons Enregistrer/Terminer natifs ; l'interface complète reste inaccessible hors-ligne.
