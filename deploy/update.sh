#!/usr/bin/env bash
# Met à jour GMeeting : sauvegarde, récupère la dernière version, reconstruit, redémarre, vérifie.
#   ./deploy/update.sh
# En cas de problème, la commande de retour arrière est affichée (version précédente + restauration possible).
source "$(dirname "$0")/lib.sh"
need_docker
git rev-parse --git-dir >/dev/null 2>&1 || fail "ce dossier n'est pas un dépôt git (installez par git clone pour pouvoir mettre à jour)."
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "des fichiers suivis ont été modifiés localement : validez-les ou annulez-les avant de mettre à jour."

PREV="$(git rev-parse HEAD)"
say "→ Sauvegarde préalable…"; ./deploy/backup.sh --no-audio || fail "sauvegarde impossible : mise à jour annulée (rien n'a été modifié)."
say "→ Récupération de la dernière version…"; git pull --ff-only
NEW="$(git rev-parse HEAD)"
[ "$PREV" = "$NEW" ] && say "Déjà à jour ($NEW)." || say "Mise à jour : ${PREV:0:7} → ${NEW:0:7}"

rollback_hint() { printf 'Retour arrière :  git checkout %s && docker compose up -d --build\n(l'"'"'état précédent des données est dans backups/ : ./deploy/restore.sh backups/<fichier> --force)\n' "$PREV" >&2; }
# Si la construction échoue, les conteneurs en service ne sont PAS remplacés : l'ancienne version continue de tourner.
if ! docker compose up -d --build; then
  printf '\033[31mLa construction de la nouvelle version a échoué : l'"'"'ancienne version continue de tourner.\033[0m\n' >&2
  rollback_hint; exit 1
fi
if wait_healthy 180; then
  say "✔ À jour et en bon état (${NEW:0:7})."
else
  printf '\033[31mL'"'"'application ne répond pas après la mise à jour.\033[0m\n' >&2
  rollback_hint; exit 1
fi
