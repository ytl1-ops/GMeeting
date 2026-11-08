#!/usr/bin/env bash
# Crée la CLÉ D'ENVOI (upload key) du Play Store, À LANCER SUR VOTRE POSTE (jamais dans un dépôt, jamais sur un serveur partagé).
#     ./android/tools/make-upload-key.sh [dossier]          (défaut : ~/gmeeting-upload-key)
# Produit dans le dossier (droits 700) :
#     upload.jks              la clé (à SAUVEGARDER : coffre de mots de passe + copie chiffrée hors du poste)
#     secrets-github.txt      les 4 valeurs à coller dans GitHub → Settings → Secrets and variables → Actions
# Avec « Play App Signing » (recommandé), Google garde la vraie clé de signature : en cas de perte de la clé d'envoi, Google peut la réinitialiser (démarche
# manuelle auprès du support). Ne perdez pas ce dossier quand même.
set -euo pipefail

DIR="${1:-$HOME/gmeeting-upload-key}"
ALIAS="${KEY_ALIAS:-upload}"
DNAME="${KEY_DNAME:-CN=GMeeting upload key, O=GMeeting}"
command -v keytool >/dev/null || { echo "keytool est introuvable : installez un JDK 17 (https://adoptium.net)."; exit 1; }
command -v openssl >/dev/null || command -v python3 >/dev/null || { echo "openssl ou python3 est requis pour générer le mot de passe."; exit 1; }

if [ -e "$DIR/upload.jks" ]; then echo "Refus d'écraser $DIR/upload.jks (une clé existe déjà). Choisissez un autre dossier."; exit 1; fi
mkdir -p "$DIR"; chmod 700 "$DIR"; umask 077

if command -v openssl >/dev/null; then PW="$(openssl rand -base64 24 | tr -d '/+=\n' | cut -c1-24)"
else PW="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24).replace("-","x").replace("_","y")[:24])')"; fi

keytool -genkeypair -noprompt -keystore "$DIR/upload.jks" -storetype PKCS12 -alias "$ALIAS" -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass "$PW" -keypass "$PW" -dname "$DNAME" >/dev/null

B64="$(base64 < "$DIR/upload.jks" | tr -d '\n')"
cat > "$DIR/secrets-github.txt" <<TXT
# À coller dans GitHub (dépôt) → Settings → Secrets and variables → Actions → New repository secret
# NE PARTAGEZ JAMAIS ce fichier ; supprimez-le après avoir créé les secrets (gardez upload.jks et le mot de passe dans votre coffre).

ANDROID_KEYSTORE_PASSWORD=$PW
ANDROID_KEY_ALIAS=$ALIAS
ANDROID_KEY_PASSWORD=$PW
ANDROID_KEYSTORE_B64=$B64
TXT
chmod 600 "$DIR/secrets-github.txt" "$DIR/upload.jks"

echo "Clé créée : $DIR/upload.jks"
echo "Secrets à créer sur GitHub : $DIR/secrets-github.txt (4 valeurs)"
echo
keytool -list -v -keystore "$DIR/upload.jks" -storepass "$PW" -alias "$ALIAS" 2>/dev/null | grep -E "SHA256:|Valid from" | sed 's/^ */  /'
echo
echo "Étapes suivantes : docs/TEST_INTERNE_PLAY.md"
