#!/usr/bin/env bash
# Installe GMeeting sur ce serveur : prépare .env, construit l'image, démarre, vérifie.
#   ./deploy/install.sh [DOMAINE] [--no-start]
# Variables optionnelles : ANTHROPIC_API_KEY (sinon demandée), OPENAI_API_KEY, GMEETING_PASSWORD (sinon généré).
# Idempotent : relancer ne modifie pas un .env existant, sauf pour les valeurs fournies.
source "$(dirname "$0")/lib.sh"

DOMAIN_ARG="" ; START=1
for a in "$@"; do case "$a" in --no-start) START=0 ;; -*) fail "option inconnue : $a" ;; *) DOMAIN_ARG="$a" ;; esac; done

[ "$START" = 1 ] && need_docker
[ -f .env ] || { cp .env.example .env; chmod 600 .env; say "→ .env créé à partir de .env.example"; }
chmod 600 .env

[ -n "$DOMAIN_ARG" ] && set_env DOMAIN "$DOMAIN_ARG"
[ -n "${OPENAI_API_KEY:-}" ] && set_env OPENAI_API_KEY "$OPENAI_API_KEY"

if [ -z "$(get_env ANTHROPIC_API_KEY)" ]; then
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then set_env ANTHROPIC_API_KEY "$ANTHROPIC_API_KEY"
  elif [ -t 0 ] && [ "$START" = 1 ]; then read -r -s -p "Clé API Anthropic (rédaction des documents ; Entrée pour passer) : " k; echo; [ -n "$k" ] && set_env ANTHROPIC_API_KEY "$k"
  fi
fi
[ -n "$(get_env ANTHROPIC_API_KEY)" ] || say "⚠ Aucune clé ANTHROPIC_API_KEY : l'application démarrera mais ne pourra pas rédiger. Ajoutez-la dans .env puis : docker compose up -d"

GENERATED=""
if [ -n "${GMEETING_PASSWORD:-}" ]; then set_env GMEETING_PASSWORD "$GMEETING_PASSWORD"
elif [ -z "$(get_env GMEETING_PASSWORD)" ]; then GENERATED="$(gen_password)"; set_env GMEETING_PASSWORD "$GENERATED"; fi

DOM="$(get_env DOMAIN)"; DOM="${DOM:-localhost}"
if [ "$START" = 0 ]; then say "Configuration prête (.env). Démarrage : docker compose up -d --build"; exit 0; fi

say "→ Construction et démarrage (la première fois : plusieurs minutes)…"
docker compose up -d --build
say "→ Attente de l'application…"
wait_healthy 180 || fail "l'application n'est pas devenue saine (journaux ci-dessus)."

say "✔ GMeeting est en ligne : https://${DOM}"
echo "   Connexion : nom d'utilisateur libre, mot de passe = GMEETING_PASSWORD (fichier .env, lisible par vous seul)."
[ -n "$GENERATED" ] && echo "   Mot de passe généré : $GENERATED   ← notez-le maintenant dans un gestionnaire de mots de passe."
[ "$DOM" = "localhost" ] && echo "   (Sans nom de domaine : certificat local, le navigateur affichera un avertissement.)"
echo "   Prochaines étapes : DEPLOY.md (sauvegardes planifiées, mises à jour, pare-feu)."
