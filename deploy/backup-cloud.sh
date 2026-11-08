#!/usr/bin/env bash
# Envoie une sauvegarde CHIFFRÉE vers le cloud de votre choix (Google Drive, OneDrive, Dropbox, S3, Nextcloud, WebDAV, SFTP… : tout ce que gère rclone).
#     ./deploy/backup-cloud.sh --init            # une fois : enregistre le cloud choisi et crée la phrase secrète de chiffrement
#     ./deploy/backup-cloud.sh [--no-audio]      # sauvegarde + chiffrement + envoi + vérification + nettoyage des anciennes copies
#     ./deploy/backup-cloud.sh --file ARCHIVE    # envoie une archive déjà faite (backups/gmeeting-….tar.gz)
# Le cloud ne reçoit JAMAIS vos comptes rendus en clair : l'archive est chiffrée ici (GnuPG, AES-256) avec VOTRE phrase secrète, avant l'envoi.
# Réglages (fichier .backup-cloud.env, droits 600, jamais versionné, jamais transmis au conteneur) ; les variables d'environnement du même nom les remplacent :
#     BACKUP_REMOTE=macloud:gmeeting-sauvegardes     (nom créé avec « rclone config » + dossier)
#     BACKUP_PASSPHRASE=…                            (12 caractères minimum ; SANS ELLE les copies du cloud sont illisibles, même pour vous)
#     BACKUP_KEEP_REMOTE=14                          (copies gardées dans le cloud)
# À planifier :  30 3 * * *  cd /opt/gmeeting && ./deploy/backup-cloud.sh >> backups/backup.log 2>&1
source "$(dirname "$0")/lib.sh"
CONF="$ROOT/.backup-cloud.env"
conf_get() { awk -F= -v k="$1" '$1==k {sub(/^[^=]*=/,""); print; exit}' "$CONF" 2>/dev/null || true; }
REMOTE="${BACKUP_REMOTE:-$(conf_get BACKUP_REMOTE)}"
PASS="${BACKUP_PASSPHRASE:-$(conf_get BACKUP_PASSPHRASE)}"
KEEPR="${BACKUP_KEEP_REMOTE:-$(conf_get BACKUP_KEEP_REMOTE)}"; KEEPR="${KEEPR:-14}"

INIT=0; FILE=""; NEXT=""; PASS_ARGS=()
for a in "$@"; do
  if [ "$NEXT" = file ]; then FILE="$a"; NEXT=""; continue; fi
  case "$a" in --init) INIT=1 ;; --file) NEXT=file ;; --no-audio) PASS_ARGS+=("$a") ;; *) fail "option inconnue : $a" ;; esac
done
[ "$NEXT" = file ] && fail "--file demande le chemin d'une archive"

valid_remote() { [[ "$1" =~ ^[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]*$ ]]; }

if [ "$INIT" = 1 ]; then
  [ -z "$REMOTE" ] && [ -t 0 ] && read -r -p "Cloud et dossier (nom rclone, ex. macloud:gmeeting-sauvegardes) : " REMOTE
  valid_remote "${REMOTE:-}" || fail "adresse du cloud invalide (attendu « nom:dossier », créé avec « rclone config »)."
  [ -f "$CONF" ] && [ -n "$(conf_get BACKUP_PASSPHRASE)" ] && fail "$CONF existe déjà avec une phrase secrète : ne l'écrasez pas (les anciennes copies deviendraient illisibles). Modifiez-le à la main si besoin."
  [ -n "$PASS" ] || PASS="$(gen_password)$(gen_password)"
  [ "${#PASS}" -ge 12 ] || fail "phrase secrète trop courte (12 caractères minimum)."
  ( umask 077; printf 'BACKUP_REMOTE=%s\nBACKUP_PASSPHRASE=%s\nBACKUP_KEEP_REMOTE=%s\n' "$REMOTE" "$PASS" "$KEEPR" > "$CONF" ); chmod 600 "$CONF"
  say "✔ Réglages enregistrés dans $CONF (droits 600)."
  echo "   ⚠ NOTEZ LA PHRASE SECRÈTE dans votre gestionnaire de mots de passe : sans elle, les copies du cloud sont illisibles, même pour vous."
  echo "     Elle est dans $CONF. Ne la partagez pas ; gardez-en une copie HORS de ce serveur."
  exit 0
fi

command -v rclone >/dev/null || fail "rclone est requis (https://rclone.org/install/ ; Debian/Ubuntu : sudo apt install rclone). Puis : rclone config"
command -v gpg >/dev/null || fail "gpg est requis (sudo apt install gnupg)."
valid_remote "$REMOTE" || fail "cloud non configuré : lancez d'abord  ./deploy/backup-cloud.sh --init"
[ "${#PASS}" -ge 12 ] || fail "phrase secrète absente ou trop courte (12 caractères minimum) : ./deploy/backup-cloud.sh --init"

if [ -z "$FILE" ]; then
  need_docker
  ./deploy/backup.sh ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} >/dev/null || fail "la sauvegarde locale a échoué."
  FILE="$(ls -1t backups/gmeeting-*.tar.gz 2>/dev/null | head -1)"
fi
[ -f "$FILE" ] || fail "archive introuvable : ${FILE:-aucune}"
NAME="$(basename "$FILE").gpg"

TMP="$(mktemp -d)"; chmod 700 "$TMP"; trap 'rm -rf "$TMP"' EXIT
say "→ Chiffrement de $(basename "$FILE") (AES-256, phrase secrète)"
printf '%s' "$PASS" | gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 0 --symmetric --cipher-algo AES256 --compress-algo none -o "$TMP/$NAME" "$FILE" \
  || fail "le chiffrement a échoué."
say "→ Envoi vers $REMOTE"
rclone copyto "$TMP/$NAME" "$REMOTE/$NAME" || fail "l'envoi a échoué (réseau, droits du cloud, « rclone config » à refaire ?)."
rclone lsf "$REMOTE" --files-only 2>/dev/null | grep -qxF "$NAME" || fail "envoi non confirmé : $NAME est absent du cloud."
say "✔ Copie chiffrée dans le cloud : $REMOTE/$NAME"

# nettoyage : on ne garde que les BACKUP_KEEP_REMOTE copies les plus récentes
rclone lsf "$REMOTE" --files-only 2>/dev/null | grep -E '^gmeeting-[0-9]{8}-[0-9]{6}\.tar\.gz\.gpg$' | sort | head -n -"$KEEPR" 2>/dev/null | while read -r old; do
  rclone deletefile "$REMOTE/$old" && echo "   ancienne copie supprimée du cloud : $old"
done
echo "   Restauration : ./deploy/restore-cloud.sh   (avec la même phrase secrète)"
