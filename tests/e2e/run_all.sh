#!/usr/bin/env bash
# Lance le serveur de test (traitement réel, IA simulée) puis tous les scénarios navigateur.
# Prérequis : playwright (npm) ; variables optionnelles : PYTHON (défaut python), PJ (dossier des pièces jointes de test).
set -u
cd "$(dirname "$0")/../.."
PYTHON="${PYTHON:-python}"; PJ="${PJ:-/tmp/gmeeting_pj}"
"$PYTHON" tests/e2e/make_attachments.py "$PJ" >/dev/null
KEEP_AUDIO=true "$PYTHON" tests/e2e/run_stub.py &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
sleep 3
rc=0
for t in continuity decks audio native; do echo "== $t"; node "tests/e2e/$t.js" || rc=1; done
echo "== attachments"; FILES_DIR="$PJ" node tests/e2e/attachments.js || rc=1
echo; [ $rc -eq 0 ] && echo "TOUS LES SCÉNARIOS NAVIGATEUR PASSENT" || echo "ÉCHEC(S) DANS LES SCÉNARIOS NAVIGATEUR"
exit $rc
