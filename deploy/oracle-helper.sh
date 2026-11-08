#!/usr/bin/env bash
# Aide, SUR VOTRE POSTE, pour installer GMeeting sur un serveur Oracle Cloud (Ubuntu) pas à pas. Rien n'est envoyé à Oracle : seulement des commandes ssh/scp vers VOTRE serveur.
#     ./deploy/oracle-helper.sh keygen                       crée une clé SSH dédiée (~/.ssh/gmeeting_oracle) et affiche la partie publique à coller dans la console Oracle
#     ./deploy/oracle-helper.sh pack                         empaquette la version COMMITÉE du dépôt (gmeeting.tar.gz), sans aucun secret
#     ./deploy/oracle-helper.sh send IP DOMAINE [--demo] [--data-dir CHEMIN] [--dry-run]
#                                                            envoie l'archive sur le serveur et affiche les commandes à y lancer
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${GMEETING_SSH_KEY:-$HOME/.ssh/gmeeting_oracle}"
OUT="${GMEETING_PACK_DIR:-$ROOT}"
USER_ON_SERVER="${GMEETING_SSH_USER:-ubuntu}"          # utilisateur des images Ubuntu d'Oracle
say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }
cmd="${1:-}"; [ $# -gt 0 ] && shift

case "$cmd" in
keygen)
  command -v ssh-keygen >/dev/null || fail "ssh-keygen est introuvable (installez OpenSSH)."
  [ ! -e "$KEY" ] || fail "$KEY existe déjà : je ne l'écrase pas. La partie publique est dans $KEY.pub"
  mkdir -p "$(dirname "$KEY")"; chmod 700 "$(dirname "$KEY")"
  ssh-keygen -t ed25519 -N "" -C "gmeeting-oracle" -f "$KEY" >/dev/null
  chmod 600 "$KEY"
  say "✔ Clé créée : $KEY (privée, ne la partagez JAMAIS) et $KEY.pub"
  echo "À coller dans la console Oracle (création de l'instance → « Ajouter des clés SSH » → « Coller des clés publiques ») :"; echo
  cat "$KEY.pub"; echo
  echo "Sauvegardez $KEY dans votre coffre de mots de passe : sans elle vous ne pourrez plus vous connecter au serveur." ;;
pack)
  command -v git >/dev/null || fail "git est requis."
  git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || fail "ce dossier n'est pas un dépôt git."
  [ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ] || say "⚠ Des modifications non enregistrées (commit) ne seront PAS dans l'archive : seule la version commitée est envoyée."
  mkdir -p "$OUT"
  git -C "$ROOT" archive --format=tar.gz -o "$OUT/gmeeting.tar.gz" HEAD
  say "✔ Archive : $OUT/gmeeting.tar.gz ($(du -h "$OUT/gmeeting.tar.gz" | cut -f1)) — version commitée uniquement, sans .env ni mot de passe" ;;
send)
  IP=""; DOMAIN=""; EXTRA=(); DRY=0; NEXT=""
  for a in "$@"; do
    if [ "$NEXT" = data ]; then EXTRA+=(--data-dir "$a"); NEXT=""; continue; fi
    case "$a" in --demo) EXTRA+=(--demo) ;; --dry-run) DRY=1 ;; --data-dir) NEXT=data ;; -*) fail "option inconnue : $a" ;;
      *) if [ -z "$IP" ]; then IP="$a"; elif [ -z "$DOMAIN" ]; then DOMAIN="$a"; else fail "argument en trop : $a"; fi ;; esac
  done
  [ "$NEXT" = data ] && fail "--data-dir demande un chemin absolu"
  [[ "$IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail "adresse IP invalide : « ${IP:-}» (celle de l'instance, affichée dans la console Oracle)"
  for o in ${IP//./ }; do [ "$o" -le 255 ] || fail "adresse IP invalide : $IP"; done
  [[ "$DOMAIN" =~ ^([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$ ]] || fail "nom de domaine invalide : « ${DOMAIN:-}»"
  [[ " ${EXTRA[*]:-} " != *" --data-dir "* ]] || [[ "${EXTRA[*]}" =~ --data-dir\ /[A-Za-z0-9_./-]+ ]] || fail "--data-dir : chemin absolu attendu, sans espace"
  [ -f "$KEY" ] || [ "$DRY" = 1 ] || fail "clé SSH introuvable ($KEY) : lancez d'abord  ./deploy/oracle-helper.sh keygen"
  [ -f "$OUT/gmeeting.tar.gz" ] || [ "$DRY" = 1 ] || fail "archive introuvable : lancez d'abord  ./deploy/oracle-helper.sh pack"
  SSHO=(-i "$KEY" -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes)
  run() { if [ "$DRY" = 1 ]; then printf '   [dry-run] %s\n' "$*"; else "$@"; fi; }
  say "→ Envoi de l'archive vers $USER_ON_SERVER@$IP"
  run scp "${SSHO[@]}" "$OUT/gmeeting.tar.gz" "$USER_ON_SERVER@$IP:~/gmeeting.tar.gz"
  run ssh "${SSHO[@]}" "$USER_ON_SERVER@$IP" "mkdir -p ~/gmeeting && tar xzf ~/gmeeting.tar.gz -C ~/gmeeting && rm ~/gmeeting.tar.gz"
  say "✔ Dépôt en place sur le serveur. Il reste à y lancer (copiez-collez) :"
  cat <<TXT

   ssh -i $KEY $USER_ON_SERVER@$IP
   cd gmeeting
   ./deploy/bootstrap-vps.sh $DOMAIN ${EXTRA[*]:-} --dry-run          # simulation : rien n'est modifié
   read -r -s -p "Clé Anthropic : " ANTHROPIC_API_KEY; export ANTHROPIC_API_KEY; echo
   read -r -s -p "Clé OpenAI : " OPENAI_API_KEY; export OPENAI_API_KEY; echo
   sudo -E ./deploy/bootstrap-vps.sh $DOMAIN ${EXTRA[*]:-}

   Puis, depuis VOTRE poste :  ./deploy/check-server.sh https://$DOMAIN <mot de passe affiché par l'installation>
TXT
  ;;
*) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; [ -z "$cmd" ] || fail "commande inconnue : $cmd"; exit 2 ;;
esac
