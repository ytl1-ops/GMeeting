#!/usr/bin/env bash
# Installe GMeeting sur ce serveur : prépare .env, construit l'image, démarre, vérifie.
#   ./deploy/install.sh [DOMAINE] [--no-start] [--demo]
#   --demo : serveur de DÉMONSTRATION (relecteurs Google Play, essais) : conservation 1 jour, audio supprimé, fichier DEMO_ACCESS.txt prêt à coller dans la console
# Variables optionnelles : ANTHROPIC_API_KEY (sinon demandée), OPENAI_API_KEY, GMEETING_PASSWORD (sinon généré).
# Idempotent : relancer ne modifie pas un .env existant, sauf pour les valeurs fournies.
source "$(dirname "$0")/lib.sh"

DOMAIN_ARG="" ; START=1 ; DEMO=0
for a in "$@"; do case "$a" in --no-start) START=0 ;; --demo) DEMO=1 ;; -*) fail "option inconnue : $a" ;; *) DOMAIN_ARG="$a" ;; esac; done

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

if [ "$DEMO" = 1 ]; then      # données d'un relecteur ou d'un testeur : effacées automatiquement, audio jamais conservé
  set_env RETENTION_DAYS 1; set_env KEEP_AUDIO false
fi

GENERATED=""
if [ -n "${GMEETING_PASSWORD:-}" ]; then set_env GMEETING_PASSWORD "$GMEETING_PASSWORD"
elif [ -z "$(get_env GMEETING_PASSWORD)" ]; then GENERATED="$(gen_password)"; set_env GMEETING_PASSWORD "$GENERATED"; fi

DOM="$(get_env DOMAIN)"; DOM="${DOM:-localhost}"

write_demo_access() {         # texte prêt à coller dans Play Console → Contenu de l'application → Accès à l'application
  local f=DEMO_ACCESS.txt; umask 077
  cat > "$f" <<TXT
Serveur de démonstration GMeeting — à coller dans la Play Console (Accès à l'application), puis à ne pas réutiliser ailleurs.

Adresse du serveur : https://${DOM}
Mot de passe : $(get_env GMEETING_PASSWORD)

Instructions pour le relecteur (FR) :
1. Ouvrir l'application. Saisir l'adresse du serveur ci-dessus et le mot de passe, puis « Se connecter ».
2. Accepter l'accès au micro et aux notifications.
3. Appuyer sur REC, parler quelques secondes, puis « Terminer et générer ». Le procès-verbal, le compte rendu et la note de synthèse apparaissent à la fin du traitement.
4. Les données de ce serveur de démonstration sont supprimées automatiquement après 24 heures.

Instructions for the reviewer (EN):
1. Open the app. Enter the server address and password above, then tap "Sign in".
2. Allow microphone and notification access.
3. Tap REC, speak for a few seconds, then "Finish and generate". The minutes, the meeting report and the executive summary appear when processing ends.
4. Data on this demo server is automatically deleted after 24 hours.
TXT
  chmod 600 "$f"; say "→ Texte pour les relecteurs Google Play : $f (mot de passe inclus : ne le versionnez pas)"
}
[ "$DEMO" = 1 ] && write_demo_access
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
