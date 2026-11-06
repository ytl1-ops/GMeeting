# Fonctions communes aux scripts de déploiement (chargé avec « source »).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

need_docker() {
  command -v docker >/dev/null || fail "Docker n'est pas installé (https://docs.docker.com/engine/install/)."
  docker compose version >/dev/null 2>&1 || fail "Le plugin « docker compose » (v2) est requis."
  docker info >/dev/null 2>&1 || fail "Le démon Docker ne répond pas (droits ? essayez avec sudo, ou : sudo systemctl start docker)."
}

# set_env CLE VALEUR : remplace la ligne CLE=… (même commentée) dans .env, sinon l'ajoute. Sans sed -i portable : réécriture atomique.
set_env() {
  local key="$1" val="$2" tmp; tmp="$(mktemp .env.XXXXXX)"
  # valeurs transmises par l'environnement (et non par « awk -v », qui interpréterait les « \ » d'un mot de passe)
  K="$key" V="$val" awk 'BEGIN{k=ENVIRON["K"]; v=ENVIRON["V"]; done=0} $0 ~ "^#? ?"k"=" && !done {print k"="v; done=1; next} {print} END{if(!done) print k"="v}' .env > "$tmp"
  chmod 600 "$tmp"; mv "$tmp" .env
}

# get_env CLE : valeur courante (vide si absente ou commentée)
get_env() { awk -F= -v k="$1" '$1==k {sub(/^[^=]*=/,""); print; exit}' .env 2>/dev/null || true; }

# Mot de passe aléatoire sans « tr … | head » : sous « set -o pipefail », head qui se ferme fait échouer tr (SIGPIPE) et avorte le script.
gen_password() { local p; p="$(LC_ALL=C tr -dc 'A-Za-z0-9' < <(head -c 1024 /dev/urandom))"; printf '%s' "${p:0:22}"; }

# wait_healthy [secondes] : attend que le conteneur « app » soit sain (sonde /healthz)
wait_healthy() {
  local timeout="${1:-150}" waited=0 cid status
  while [ "$waited" -lt "$timeout" ]; do
    cid="$(docker compose ps -q app 2>/dev/null || true)"
    status="$([ -n "$cid" ] && docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo absent)"
    [ "$status" = "healthy" ] && return 0
    sleep 3; waited=$((waited + 3))
  done
  docker compose logs --tail 40 app >&2 || true
  return 1
}
