#!/usr/bin/env bash
# Restaure une sauvegarde depuis le cloud désigné :  ./deploy/restore-cloud.sh [NOM] [--force]
#   NOM : fichier gmeeting-AAAAMMJJ-HHMMSS.tar.gz.gpg (défaut : la plus récente). Réglages : mêmes que backup-cloud.sh (.backup-cloud.env).
source "$(dirname "$0")/lib.sh"
CONF="$ROOT/.backup-cloud.env"
conf_get() { awk -F= -v k="$1" '$1==k {sub(/^[^=]*=/,""); print; exit}' "$CONF" 2>/dev/null || true; }
REMOTE="${BACKUP_REMOTE:-$(conf_get BACKUP_REMOTE)}"; PASS="${BACKUP_PASSPHRASE:-$(conf_get BACKUP_PASSPHRASE)}"
NAME=""; FORCE=()
for a in "$@"; do case "$a" in --force) FORCE=(--force) ;; -*) fail "option inconnue : $a" ;; *) NAME="$a" ;; esac; done
command -v rclone >/dev/null || fail "rclone est requis (https://rclone.org/install/)."
command -v gpg >/dev/null || fail "gpg est requis (sudo apt install gnupg)."
[[ "$REMOTE" =~ ^[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]*$ ]] || fail "cloud non configuré (.backup-cloud.env ou BACKUP_REMOTE)."
[ "${#PASS}" -ge 12 ] || fail "phrase secrète absente (celle utilisée à la sauvegarde)."
if [ -z "$NAME" ]; then NAME="$(rclone lsf "$REMOTE" --files-only 2>/dev/null | grep -E '^gmeeting-[0-9]{8}-[0-9]{6}\.tar\.gz\.gpg$' | sort | tail -1)"; fi
[ -n "$NAME" ] || fail "aucune sauvegarde trouvée dans $REMOTE."
[[ "$NAME" =~ ^gmeeting-[0-9]{8}-[0-9]{6}\.tar\.gz\.gpg$ ]] || fail "nom de sauvegarde invalide : $NAME"
TMP="$(mktemp -d)"; chmod 700 "$TMP"; trap 'rm -rf "$TMP"' EXIT
say "→ Téléchargement de $NAME"
rclone copyto "$REMOTE/$NAME" "$TMP/$NAME" || fail "téléchargement impossible."
say "→ Déchiffrement"
printf '%s' "$PASS" | gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 0 --decrypt -o "$TMP/${NAME%.gpg}" "$TMP/$NAME" \
  || fail "déchiffrement impossible : mauvaise phrase secrète, ou copie altérée (le chiffrement détecte toute modification)."
"${GMEETING_RESTORE_CMD:-$ROOT/deploy/restore.sh}" "$TMP/${NAME%.gpg}" ${FORCE[@]+"${FORCE[@]}"}
