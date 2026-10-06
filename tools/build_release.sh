#!/bin/zsh
# Builds the mobile store packages into release/:
#   release/android/*.aab  (upload to Google Play)
#   release/android/*.apk  (for side-loading / testing)
#   release/ios/*.ipa      (upload to App Store Connect)
# Android: targets API 32; signed with ~/keys/diamond-upload.jks, whose password is read from the macOS
# Keychain (service "Diamond Android upload keystore", account diamond-upload). tools/make_keystore.sh
# creates both. iOS: "Apple Distribution: Paul Johnson (3UH7BE38T3)" and the rel-cursed profile
# (~/Downloads/relcursed.mobileprovision, installed by this script).
#
#   tools/build_release.sh            Android and iOS
#   tools/build_release.sh ios        iOS only
#   tools/build_release.sh android    Android only
set -euo pipefail
cd "$(dirname "$0")/.."
WHAT=${1:-all}

if [[ $WHAT != android ]]; then
  # Xcode's tools find provisioning profiles by UUID in these folders.
  for f in relcursed develcursed; do
    [[ -f ~/Downloads/$f.mobileprovision ]] || continue
    uuid=$(security cms -D -i ~/Downloads/$f.mobileprovision | plutil -extract UUID raw -)
    for dir in "$HOME/Library/MobileDevice/Provisioning Profiles" "$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"; do
      mkdir -p "$dir" && cp ~/Downloads/$f.mobileprovision "$dir/$uuid.mobileprovision"
    done
  done
  # Clean first: an incremental build can keep the previous build number in the app's Info.plist.
  rm -rf release/ios Diamond.iOS/obj/Release Diamond.iOS/bin/Release
  dotnet publish Diamond.iOS/Diamond.iOS.csproj -c Release -f net10.0-ios -p:DiamondIosProfile=rel-cursed -o release/ios
  ls -la release/ios/*.ipa
fi
[[ $WHAT == ios ]] && exit 0

export DIAMOND_KEYSTORE_PASS="$(security find-generic-password -a diamond-upload -s 'Diamond Android upload keystore' -w)"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"

rm -rf release/android
for format in aab apk; do
  dotnet publish Diamond.Android/Diamond.Android.csproj -c Release -f net10.0-android \
    -p:AndroidPackageFormat=$format -p:AndroidSdkDirectory="$SDK" -o release/android/$format
done
mkdir -p release/android/out
mv release/android/aab/*-Signed.aab release/android/apk/*-Signed.apk release/android/out/
rm -rf release/android/aab release/android/apk
mv release/android/out/* release/android/ && rmdir release/android/out
ls -la release/android
