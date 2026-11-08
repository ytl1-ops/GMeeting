#!/usr/bin/env bash
# Prépare un serveur NEUF (Ubuntu ou Debian) et y installe GMeeting en HTTPS : Docker, pare-feu, mises à jour de sécurité automatiques, puis deploy/install.sh.
#     sudo ./deploy/bootstrap-vps.sh DOMAINE [--demo] [--data-dir /chemin/absolu] [--dry-run]
#   DOMAINE   nom déjà pointé vers l'adresse IP du serveur (enregistrement DNS « A ») : Caddy en tire le certificat HTTPS
#   --demo    serveur de démonstration (relecteurs Google Play) : données effacées après 1 jour, fichier DEMO_ACCESS.txt
#   --data-dir données sur un disque DÉSIGNÉ (volume de bloc, disque monté…) au lieu du volume Docker par défaut : docs/STOCKAGE.md
#   --dry-run affiche ce qui serait fait, sans rien modifier (essayez-le d'abord)
# Variables optionnelles transmises à l'installeur : ANTHROPIC_API_KEY, OPENAI_API_KEY, GMEETING_PASSWORD.
# Ce script ne se connecte à aucun service de votre compte : il tourne sur le serveur, lancé par vous.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

DOMAIN=""; DEMO=0; DRY=0; DATADIR=""; NEXT=""
for a in "$@"; do if [ "$NEXT" = data ]; then DATADIR="$a"; NEXT=""; continue; fi; case "$a" in --demo) DEMO=1 ;; --dry-run) DRY=1 ;; --data-dir) NEXT=data ;; -*) fail "option inconnue : $a" ;; *) DOMAIN="$a" ;; esac; done
[ "$NEXT" = data ] && fail "--data-dir demande un chemin absolu"
[ -z "$DATADIR" ] || [[ "$DATADIR" =~ ^/[A-Za-z0-9_./-]+$ ]] || fail "--data-dir : chemin absolu attendu, sans espace ni caractère spécial : $DATADIR"
[ -n "$DOMAIN" ] || fail "indiquez le nom de domaine : sudo ./deploy/bootstrap-vps.sh reunions.exemple.fr"
[[ "$DOMAIN" =~ ^([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$ ]] || fail "nom de domaine invalide : $DOMAIN"

run() { if [ "$DRY" = 1 ]; then printf '   [dry-run] %s\n' "$*"; else "$@"; fi; }
[ "$DRY" = 1 ] && say "MODE SIMULATION : rien ne sera modifié."
if [ "$DRY" = 0 ]; then [ "$(id -u)" = 0 ] || fail "à lancer en administrateur : sudo ./deploy/bootstrap-vps.sh $DOMAIN"; fi

# système pris en charge
OS_ID="${OS_ID_OVERRIDE:-}"; CODENAME="${CODENAME_OVERRIDE:-}"
if [ -z "$OS_ID" ] && [ -r /etc/os-release ]; then OS_ID="$(. /etc/os-release; echo "${ID:-}")"; CODENAME="$(. /etc/os-release; echo "${VERSION_CODENAME:-}")"; fi
case "$OS_ID" in ubuntu|debian) ;; *) fail "système non pris en charge (« ${OS_ID:-inconnu} ») : Ubuntu ou Debian requis. Autre système : suivez DEPLOY.md." ;; esac
[ -n "$CODENAME" ] || fail "version du système indéterminée."

# le nom de domaine doit déjà pointer ici, sinon le certificat HTTPS ne pourra pas être obtenu
say "→ Contrôle du DNS pour $DOMAIN"
RESOLVED="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)"
if [ -z "$RESOLVED" ]; then say "⚠ $DOMAIN ne se résout pas encore : créez l'enregistrement DNS « A » vers l'adresse IP du serveur, attendez sa propagation, puis relancez."; [ "$DRY" = 1 ] || fail "DNS non prêt pour $DOMAIN"
else
  LOCALIPS="$(hostname -I 2>/dev/null || true)"
  case " $LOCALIPS " in *" $RESOLVED "*) say "   $DOMAIN → $RESOLVED (adresse de ce serveur)" ;; *) say "⚠ $DOMAIN → $RESOLVED, qui n'est pas une adresse locale de ce serveur ($LOCALIPS). Normal derrière une adresse IP translatée (nuage) ; sinon corrigez le DNS." ;; esac
fi

say "→ Paquets de base et mises à jour de sécurité automatiques"
run apt-get update -y
run env DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg ufw unattended-upgrades git
if [ "$DRY" = 0 ]; then echo "unattended-upgrades unattended-upgrades/enable_auto_updates boolean true" | debconf-set-selections; DEBIAN_FRONTEND=noninteractive dpkg-reconfigure -f noninteractive unattended-upgrades
else printf '   [dry-run] activation de unattended-upgrades\n'; fi

if [ -n "${DOCKER_PRESENT_OVERRIDE:-}" ]; then HAVE_DOCKER="$DOCKER_PRESENT_OVERRIDE"                       # (tests)
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then HAVE_DOCKER=1; else HAVE_DOCKER=0; fi
if [ "$HAVE_DOCKER" = 1 ]; then say "→ Docker et le plugin compose sont déjà installés"
else
  say "→ Installation de Docker (dépôt officiel docker.com)"
  run install -m 0755 -d /etc/apt/keyrings
  if [ "$DRY" = 0 ]; then curl -fsSL "https://download.docker.com/linux/$OS_ID/gpg" -o /etc/apt/keyrings/docker.asc; chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$OS_ID $CODENAME stable" > /etc/apt/sources.list.d/docker.list
  else printf '   [dry-run] ajout du dépôt https://download.docker.com/linux/%s (%s)\n' "$OS_ID" "$CODENAME"; fi
  run apt-get update -y
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  run systemctl enable --now docker
fi

say "→ Pare-feu : SSH, HTTP (certificat) et HTTPS seulement"
SSHPORT="$(ss -tlnp 2>/dev/null | awk '/sshd/ {n=split($4,a,":"); print a[n]; exit}' || true)"; SSHPORT="${SSHPORT:-22}"
run ufw default deny incoming
run ufw default allow outgoing
run ufw allow "$SSHPORT/tcp"          # AVANT d'activer le pare-feu : sinon vous perdriez l'accès
run ufw allow 80/tcp
run ufw allow 443/tcp
run ufw --force enable

say "→ Installation de GMeeting ($DOMAIN)"
ARGS=("$DOMAIN"); [ "$DEMO" = 1 ] && ARGS+=(--demo); [ -n "$DATADIR" ] && ARGS+=(--data-dir "$DATADIR")
if [ "$DRY" = 1 ]; then printf '   [dry-run] %s/deploy/install.sh %s\n' "$ROOT" "${ARGS[*]}"
else "$ROOT/deploy/install.sh" "${ARGS[@]}"; fi

say "✔ Terminé. Vérifiez le serveur depuis VOTRE poste :  ./deploy/check-server.sh https://$DOMAIN <mot de passe>"
[ "$DEMO" = 1 ] && echo "   Texte pour les relecteurs Google Play : $ROOT/DEMO_ACCESS.txt"
echo "   Sauvegardes, mises à jour, sécurité : DEPLOY.md."
