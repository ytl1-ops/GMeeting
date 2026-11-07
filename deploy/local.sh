#!/usr/bin/env bash
# Lance GMeeting sur CE poste, accessible depuis votre téléphone (même Wi-Fi). Un seul fichier à exécuter :
#     ./deploy/local.sh
# Première fois : crée l'environnement Python, génère un mot de passe fort (fichier .env, lecture réservée), affiche l'adresse à saisir
# dans l'application. Ensuite : relance simplement le serveur. Arrêt : Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"

command -v python3 >/dev/null || { echo "Python 3 est requis (https://www.python.org)."; exit 1; }
command -v ffmpeg  >/dev/null || echo "⚠ ffmpeg est introuvable : l'audio ne pourra pas être traité (macOS : brew install ffmpeg · Debian/Ubuntu : sudo apt install ffmpeg)."

if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env; chmod 600 .env
  pw="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  sed -i.bak "s|^GMEETING_PASSWORD=.*|GMEETING_PASSWORD=$pw|" .env && rm -f .env.bak
  echo "Mot de passe généré : $pw   (conservé dans .env)"
fi
set -a; . ./.env; set +a
[ -n "${GMEETING_PASSWORD:-}" ] || { echo "GMEETING_PASSWORD est vide dans .env : renseignez-le."; exit 1; }
[ -n "${ANTHROPIC_API_KEY:-}" ] || echo "⚠ ANTHROPIC_API_KEY est vide dans .env : sans elle, la rédaction (PV / CR / synthèse) est indisponible."
[ -n "${OPENAI_API_KEY:-}" ] || echo "ℹ Transcription : voir TRANSCRIBE_PROVIDER / OPENAI_API_KEY dans .env.example."

ip="$(python3 - <<'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("10.255.255.255", 1)); print(s.getsockname()[0])
except OSError:
    print("IP-DU-PC")
PY
)"
echo
echo "════════════════════════════════════════════════════════"
echo " Dans l'application GMeeting :  adresse  ${ip}:${PORT}"
echo " Mot de passe : voir GMEETING_PASSWORD dans le fichier .env"
echo " Test navigateur du téléphone : http://${ip}:${PORT}"
echo "════════════════════════════════════════════════════════"
echo "(Si le téléphone n'y accède pas : pare-feu du PC, port ${PORT}.)"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
