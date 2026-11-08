#!/usr/bin/env bash
# Oracle Cloud (images Ubuntu) : ouvre les ports 80 et 443 dans le pare-feu DU SERVEUR.
#     sudo ./deploy/oracle-firewall.sh [--dry-run]
# Pourquoi : ces images n'utilisent pas ufw mais des règles iptables (/etc/iptables/rules.v4) qui se terminent par une règle de REJET. Une règle ajoutée APRÈS
# ce rejet est ignorée : il faut l'insérer AVANT. Les règles sont ensuite enregistrées pour survivre au redémarrage.
# (Ce n'est qu'une des DEUX barrières : la liste de sécurité du réseau virtuel du compte Oracle doit aussi autoriser 80 et 443 : docs/ORACLE.md.)
set -euo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }
[ "$DRY" = 1 ] || [ "$(id -u)" = 0 ] || fail "à lancer en administrateur : sudo ./deploy/oracle-firewall.sh"
command -v iptables >/dev/null || fail "iptables est introuvable."

for port in 80 443; do
  if iptables -C INPUT -p tcp --dport "$port" -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null; then say "   port $port : déjà ouvert"; continue; fi
  pos="$(iptables -L INPUT --line-numbers -n 2>/dev/null | awk '$2=="REJECT" {print $1; exit}')"; pos="${pos:-1}"
  if [ "$DRY" = 1 ]; then printf '   [dry-run] iptables -I INPUT %s -p tcp --dport %s -m conntrack --ctstate NEW -j ACCEPT\n' "$pos" "$port"
  else iptables -I INPUT "$pos" -p tcp --dport "$port" -m conntrack --ctstate NEW -j ACCEPT; say "   port $port : ouvert (règle insérée en position $pos, avant le rejet final)"; fi
done

if [ "$DRY" = 1 ]; then printf '   [dry-run] netfilter-persistent save\n'
elif command -v netfilter-persistent >/dev/null; then netfilter-persistent save >/dev/null && say "   règles enregistrées (elles survivront au redémarrage)"
else say "⚠ netfilter-persistent est absent : les règles seront perdues au redémarrage. Installez-le : sudo apt install iptables-persistent, puis relancez ce script."; fi
