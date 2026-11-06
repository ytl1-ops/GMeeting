#!/usr/bin/env bash
# Sauvegarde les données (base, pièces jointes, gabarit, audio conservé) dans ./backups/ sur le serveur.
#   ./deploy/backup.sh [--no-audio]        Variables : KEEP (nombre d'archives gardées, défaut 14)
# À planifier :  0 3 * * *  cd /opt/gmeeting && ./deploy/backup.sh >> backups/backup.log 2>&1
source "$(dirname "$0")/lib.sh"
need_docker
cid="$(docker compose ps -q app)"; [ -n "$cid" ] || fail "le service « app » ne tourne pas (docker compose up -d)."

out="$(docker compose exec -T app python -m app.backup create --keep "${KEEP:-14}" "$@")" || fail "la sauvegarde a échoué."
echo "$out"
file="$(docker compose exec -T app sh -c 'ls -1t /data/backups/gmeeting-*.tar.gz | head -1' | tr -d '\r')"
mkdir -p backups; chmod 700 backups
docker compose cp "app:${file}" "backups/$(basename "$file")" >/dev/null
chmod 600 "backups/$(basename "$file")"
# garde aussi un nombre limité d'archives côté hôte
ls -1t backups/gmeeting-*.tar.gz 2>/dev/null | tail -n +"$(( ${KEEP:-14} + 1 ))" | xargs -r rm --
say "✔ Copie sur l'hôte : backups/$(basename "$file")   (à copier AUSSI hors de ce serveur, chiffrée : elle contient vos comptes rendus)"
