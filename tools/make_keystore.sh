#!/bin/zsh
# Creates the Google Play upload key ~/keys/diamond-upload.jks (alias "diamond") with a random
# password kept in the macOS Keychain (service "Diamond Android upload keystore", account
# diamond-upload). Run once; keep a backup of the keystore and its password - Play needs the same
# upload key for every update (or a key reset through Play Console).
set -euo pipefail
KEY=~/keys/diamond-upload.jks
if [[ -f $KEY ]]; then
  echo "$KEY already exists"
  exit 0
fi
mkdir -p ~/keys
pass=$(openssl rand -hex 16)
security add-generic-password -a diamond-upload -s 'Diamond Android upload keystore' -w "$pass" -U
keytool -genkeypair -v -keystore $KEY -alias diamond -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass "$pass" -keypass "$pass" -dname "CN=Paul F. Johnson, O=all-the-johnsons, C=GB"
echo "created $KEY (password in the Keychain)"
