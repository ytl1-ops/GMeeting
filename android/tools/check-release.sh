#!/usr/bin/env bash
# Contrôle que la version PUBLIÉE de l'application garde ses protections (à lancer depuis le dossier android/, en CI avant tout envoi sur le Play Store).
#   - HTTPS obligatoire : la configuration réseau principale interdit le HTTP ; seule la version de test (src/debug) l'autorise
#   - aucune sauvegarde cloud, aucun drapeau de débogage, service d'enregistrement au premier plan déclaré (type micro)
#   - cible Android 16 / API 36 (exigence du Play Store pour les nouvelles applications depuis le 31/08/2026), écran protégé par défaut hors version de test
#   - si le manifeste fusionné de la version publiée existe (après compilation), il est contrôlé aussi
# Code de sortie non nul = ne PAS publier.
set -u
cd "${1:-.}"
MAIN=app/src/main; fail=0
ko() { echo "ÉCHEC : $1"; fail=1; }
ok() { echo "ok     : $1"; }

nsc=$MAIN/res/xml/network_security_config.xml
[ -f "$nsc" ] || ko "configuration réseau principale introuvable ($nsc)"
if [ -f "$nsc" ]; then
  grep -q 'cleartextTrafficPermitted="true"' "$nsc" && ko "$nsc autorise le HTTP" || ok "configuration réseau principale : HTTP interdit"
  grep -q '<base-config cleartextTrafficPermitted="false"' "$nsc" || ko "$nsc : base-config doit interdire le HTTP"
fi
man=$MAIN/AndroidManifest.xml
grep -q 'android:usesCleartextTraffic="false"' "$man" && ok "manifeste : usesCleartextTraffic=false" || ko "manifeste : usesCleartextTraffic doit être false"
grep -q 'android:allowBackup="false"' "$man" && ok "manifeste : pas de sauvegarde cloud" || ko "manifeste : allowBackup doit être false"
grep -q 'android:debuggable' "$man" && ko "manifeste : android:debuggable ne doit pas figurer dans le manifeste principal" || ok "manifeste : pas de drapeau de débogage"
grep -q 'FOREGROUND_SERVICE_MICROPHONE' "$man" && grep -q 'foregroundServiceType="microphone"' "$man" && ok "service d'enregistrement : type micro déclaré" || ko "service d'enregistrement : type micro non déclaré"
grep -q 'android:name="android.permission.RECORD_AUDIO"' "$man" && ok "permission micro déclarée" || ko "permission RECORD_AUDIO absente"
# la version de test est la seule à pouvoir autoriser le HTTP
if grep -rq 'cleartextTrafficPermitted="true"' app/src --include=*.xml --exclude-dir=debug; then ko "du HTTP est autorisé ailleurs que dans src/debug"; else ok "HTTP autorisé uniquement dans src/debug"; fi

gr=app/build.gradle.kts
t=$(grep -oE 'targetSdk *= *[0-9]+' "$gr" | grep -oE '[0-9]+' | head -1)
[ -n "${t:-}" ] && [ "$t" -ge 36 ] && ok "targetSdk $t (≥ 36)" || ko "targetSdk ${t:-?} : le Play Store exige au moins 36 (Android 16) pour les nouvelles applications depuis le 31/08/2026"
# le suffixe « .debug » ne doit exister que pour le type de compilation debug
if awk '/release *\{/{r=1} r&&/applicationIdSuffix/{print "x"} /\}/{if(r&&++c>0)r=0}' "$gr" | grep -q x; then ko "release : applicationIdSuffix interdit"; else ok "release : identifiant sans suffixe"; fi
grep -q '!BuildConfig.DEBUG' app/src/main/kotlin/app/gmeeting/MainActivity.kt && ok "écran protégé par défaut hors version de test" || ko "écran protégé : réglage par défaut introuvable"

# manifeste fusionné de la version publiée (présent après une compilation)
merged=$(find app/build -path '*release*' -name AndroidManifest.xml -path '*merged_manifests*' 2>/dev/null | head -1)
if [ -n "$merged" ]; then
  grep -q 'usesCleartextTraffic="true"' "$merged" && ko "manifeste fusionné : HTTP autorisé" || ok "manifeste fusionné : HTTP non autorisé"
  grep -q 'debuggable="true"' "$merged" && ko "manifeste fusionné : debuggable=true" || ok "manifeste fusionné : non débogable"
else
  echo "info   : pas de manifeste fusionné (compilation non faite) : contrôle des sources seulement"
fi
[ "$fail" = 0 ] && echo "CONTRÔLE OK : la version publiée garde ses protections" || echo "CONTRÔLE ÉCHOUÉ : ne pas publier"
exit "$fail"
