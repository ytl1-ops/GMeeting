#!/usr/bin/env bash
# Restaure une sauvegarde :  ./deploy/restore.sh backups/gmeeting-AAAAMMJJ-HHMMSS.tar.gz [--force]
# --force : remplace des données existantes (une sauvegarde de sécurité est alors faite d'abord).
source "$(dirname "$0")/lib.sh"
need_docker
FILE="${1:-}"; [ -n "$FILE" ] && [ -f "$FILE" ] || fail "usage : $0 backups/gmeeting-….tar.gz [--force]"
FORCE="${2:-}"; BASE="$(basename "$FILE")"

say "Restauration de $BASE"
if [ "$FORCE" = "--force" ]; then
  read -r -p "Cela REMPLACE les données actuelles. Tapez « oui » pour continuer : " ok; [ "$ok" = "oui" ] || fail "annulé."
  if [ -n "$(docker compose ps -q app)" ]; then say "→ Sauvegarde de sécurité avant remplacement…"; ./deploy/backup.sh >/dev/null || fail "sauvegarde de sécurité impossible : restauration annulée."; fi
fi
say "→ Arrêt de l'application…"
docker compose stop app
# L'archive est transmise par l'entrée standard : un fichier de l'hôte (droits 600) monté dans le conteneur ne serait pas lisible par
# son utilisateur non-root. (Constaté lors des essais : « Permission denied ».)
if ! docker compose run --rm -T --no-deps app python -m app.backup restore - ${FORCE:+--force} < "$FILE"; then
  # Restauration refusée (ex. des données existent : --force oublié) ou archive invalide : on ne laisse JAMAIS le service arrêté.
  say "✖ Restauration non effectuée (message ci-dessus). Redémarrage de l'application avec les données actuelles…"
  docker compose up -d >/dev/null
  wait_healthy 120 || true
  fail "restauration non effectuée ; l'application a été redémarrée, vos données actuelles sont intactes."
fi
say "→ Redémarrage…"
docker compose up -d
wait_healthy 120 || fail "l'application n'est pas redevenue saine."
say "✔ Restauration terminée."
