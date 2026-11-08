#!/usr/bin/env bash
# Vérifie, DEPUIS N'IMPORTE QUEL POSTE, qu'un serveur GMeeting est prêt et protégé (HTTPS valide, mot de passe exigé, en-têtes de sécurité, configuration).
#     ./deploy/check-server.sh https://reunions.exemple.fr [MOT_DE_PASSE] [--allow-http]
# Sans mot de passe : seuls les contrôles publics sont faits. --allow-http : réseau local uniquement (essais).
# Code de sortie non nul = au moins un ÉCHEC (les avertissements ne comptent pas).
set -u
URL=""; PW=""; ALLOW_HTTP=0
for a in "$@"; do case "$a" in --allow-http) ALLOW_HTTP=1 ;; -*) echo "option inconnue : $a" >&2; exit 2 ;; *) if [ -z "$URL" ]; then URL="$a"; else PW="$a"; fi ;; esac; done
[ -n "$URL" ] || { echo "usage : $0 https://serveur [mot_de_passe] [--allow-http]" >&2; exit 2; }
URL="${URL%/}"; fail=0; warn=0
ok()  { echo "ok       : $1"; }
ko()  { echo "ÉCHEC    : $1"; fail=1; }
wa()  { echo "attention: $1"; warn=1; }
command -v curl >/dev/null || { echo "curl est requis" >&2; exit 2; }
C=(curl -sS --max-time 20)

case "$URL" in
  https://*) ok "adresse en HTTPS" ;;
  http://*) if [ "$ALLOW_HTTP" = 1 ]; then wa "HTTP non chiffré : réseau local uniquement"; else ko "adresse en HTTP : utilisez HTTPS (la version publiée de l'application refuse le HTTP)"; fi ;;
  *) ko "adresse invalide (attendu : https://nom-de-domaine)"; echo "CONTRÔLE ÉCHOUÉ"; exit 1 ;;
esac

# 1. le serveur répond, certificat valide (curl vérifie le certificat : jamais d'option -k)
H="$("${C[@]}" -D - -o /tmp/gm_health.$$ "$URL/healthz" 2>/tmp/gm_err.$$)"; rc=$?
if [ $rc -ne 0 ]; then
  case "$(cat /tmp/gm_err.$$)" in *certificate*|*SSL*|*TLS*) ko "certificat HTTPS invalide ou non reconnu : $(head -c 160 /tmp/gm_err.$$)" ;; *) ko "serveur injoignable : $(head -c 160 /tmp/gm_err.$$) (DNS, pare-feu, service arrêté ?)" ;; esac
  rm -f /tmp/gm_health.$$ /tmp/gm_err.$$; echo "CONTRÔLE ÉCHOUÉ : ne pas publier cette adresse"; exit 1
fi
grep -q '"status" *: *"ok"' /tmp/gm_health.$$ && ok "/healthz répond « ok » (certificat accepté)" || ko "/healthz ne répond pas comme GMeeting"
grep -q '"ffmpeg" *: *true' /tmp/gm_health.$$ && ok "ffmpeg disponible (traitement audio)" || wa "ffmpeg indisponible : l'audio ne pourra pas être traité"
rm -f /tmp/gm_health.$$ /tmp/gm_err.$$

# 2. en-têtes de sécurité
HDR="$("${C[@]}" -D - -o /dev/null "$URL/healthz" | tr -d '\r' | tr 'A-Z' 'a-z')"
echo "$HDR" | grep -q '^content-security-policy:' && ok "en-tête CSP présent" || ko "en-tête Content-Security-Policy absent"
echo "$HDR" | grep -q '^x-content-type-options: *nosniff' && ok "X-Content-Type-Options: nosniff" || ko "X-Content-Type-Options absent"
case "$URL" in https://*) echo "$HDR" | grep -q '^strict-transport-security:' && ok "HSTS présent" || ko "HSTS absent (Strict-Transport-Security)" ;; esac

# 3. le mot de passe est exigé (rien de lisible sans lui)
code="$("${C[@]}" -o /dev/null -w '%{http_code}' "$URL/api/config")"
[ "$code" = 401 ] && ok "sans mot de passe : accès refusé (401)" || ko "sans mot de passe : code $code au lieu de 401 : le serveur est OUVERT à toute personne qui l'atteint (GMEETING_PASSWORD vide ?)"
code="$("${C[@]}" -o /dev/null -w '%{http_code}' "$URL/")"
[ "$code" = 401 ] && ok "l'interface elle-même est protégée" || ko "l'interface répond sans mot de passe (code $code)"

# 4. avec le mot de passe
if [ -n "$PW" ]; then
  code="$("${C[@]}" -o /dev/null -w '%{http_code}' -u "gmeeting:$PW" "$URL/api/config")"
  [ "$code" = 200 ] && ok "mot de passe accepté" || ko "mot de passe refusé ou serveur en erreur (code $code)"
  code="$("${C[@]}" -o /dev/null -w '%{http_code}' -u "gmeeting:$PW-erreur" "$URL/api/config")"
  [ "$code" = 401 ] && ok "un mauvais mot de passe est refusé" || ko "un mauvais mot de passe n'est pas refusé (code $code)"
  P="$("${C[@]}" -u "gmeeting:$PW" "$URL/api/privacy")"
  CF="$("${C[@]}" -u "gmeeting:$PW" "$URL/api/config")"
  echo "$P" | grep -q '"password_set" *: *true' && ok "page Confidentialité : mot de passe actif" || ko "page Confidentialité : mot de passe non actif"
  case "$URL" in https://*) echo "$P" | grep -q '"https" *: *true' && ok "page Confidentialité : connexion vue comme chiffrée" || wa "le serveur ne se voit pas en HTTPS (en-tête X-Forwarded-Proto du proxy ?)" ;; esac
  echo "$CF" | grep -q '"has_anthropic" *: *true' && ok "rédaction par IA configurée" || wa "ANTHROPIC_API_KEY absente : les comptes rendus ne pourront pas être rédigés"
  echo "$CF" | grep -Eq '"transcribe_provider" *: *"(local|openai)"' && ok "transcription : $(echo "$CF" | grep -o '"transcribe_provider" *: *"[a-z]*"' | sed 's/.*: *//' | tr -d '"')" || wa "aucun moteur de transcription configuré"
  echo "$CF" | grep -q '"has_openai" *: *false' && echo "$CF" | grep -q '"transcribe_provider" *: *"openai"' && wa "transcription OpenAI choisie mais OPENAI_API_KEY absente"
  rd="$(echo "$CF" | grep -o '"retention_days" *: *[0-9]*' | grep -o '[0-9]*$')"
  [ "${rd:-0}" -gt 0 ] && ok "conservation limitée à $rd jour(s)" || wa "aucune suppression automatique des réunions (RETENTION_DAYS=0)"
else
  echo "info     : pas de mot de passe fourni : contrôles authentifiés ignorés"
fi
[ "$fail" = 0 ] && { [ "$warn" = 0 ] && echo "CONTRÔLE OK" || echo "CONTRÔLE OK (avec des avertissements à lire)"; } || echo "CONTRÔLE ÉCHOUÉ : ne pas publier cette adresse"
exit "$fail"
