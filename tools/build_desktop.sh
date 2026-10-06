#!/bin/zsh
# Builds the macOS store package into release/macos/:
#   release/macos/Diamond.app   (universal: Apple silicon and Intel; signed for the Mac App Store)
#   release/macos/Diamond.pkg   (upload to App Store Connect with Transporter)
#
# Signing uses "Apple Distribution: Paul Johnson (3UH7BE38T3)", the macOS App Store profile for
# uk.co.allthejohnsons.diamond (~/Downloads/relcursedmac.provisionprofile, or set
# DIAMOND_MAC_PROFILE) and "3rd Party Mac Developer Installer: Paul Johnson (3UH7BE38T3)" for the .pkg.
# The Windows build is made in Parallels by tools/build_windows.sh.
#
#   tools/build_desktop.sh        App Store build (.app + .pkg)
#   tools/build_desktop.sh dev    development-signed .app (devel-cursed-mac profile) that runs locally
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT=Diamond.DesktopGL/Diamond.DesktopGL.csproj
VERSION=$(dotnet msbuild $PROJECT -getProperty:Version)
BUILD=$(dotnet msbuild $PROJECT -getProperty:BuildNumber)
MODE=${1:-store}
APP_SIGN="Apple Distribution: Paul Johnson (3UH7BE38T3)"
PKG_SIGN="3rd Party Mac Developer Installer: Paul Johnson (3UH7BE38T3)"
PROFILE=${DIAMOND_MAC_PROFILE:-$HOME/Downloads/relcursedmac.provisionprofile}
out=release/macos
if [[ $MODE == dev ]]; then
  APP_SIGN="Apple Development: Paul Johnson (WFWPL93CN6)"
  PROFILE=${DIAMOND_MAC_PROFILE:-$HOME/Downloads/develcursedmac.provisionprofile}
  out=release/macos-dev
fi

app="$out/Diamond.app"
tmp=$(mktemp -d)
rm -rf $out && mkdir -p $out

# Universal: a runtime for each architecture in Contents/MonoBundle/<arch>; the universal
# launcher picks the one it is running as.
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
for arch in arm64 x64; do
  dotnet publish $PROJECT -c Release -r osx-$arch --self-contained -o "$app/Contents/MonoBundle/$arch" \
    -p:DebugType=none -p:GenerateDocumentationFile=false
  rm -f "$app/Contents/MonoBundle/$arch/Diamond" "$app/Contents/MonoBundle/$arch/createdump"
done

sdk=$(xcrun --sdk macosx --show-sdk-version)
clang -O2 -arch arm64 -arch x86_64 -mmacosx-version-min=12.0 -isysroot "$(xcrun --sdk macosx --show-sdk-path)" \
  -framework AppKit -o "$app/Contents/MacOS/Diamond" Diamond.DesktopGL/macOS/launcher.c
cp Diamond.DesktopGL/Diamond.icns "$app/Contents/Resources/"
# English and French names for the Finder and the menu bar.
for lang in en fr; do
  mkdir -p "$app/Contents/Resources/$lang.lproj"
  cp Diamond.iOS/Resources/$lang.lproj/InfoPlist.strings "$app/Contents/Resources/$lang.lproj/"
done
sed -e "s/\$(VERSION)/$VERSION/" -e "s/\$(BUILD)/$BUILD/" Diamond.DesktopGL/macOS/Info.plist > "$app/Contents/Info.plist"
plist="$app/Contents/Info.plist"
plutil -insert DTPlatformName -string macosx "$plist"
plutil -insert DTPlatformVersion -string "$sdk" "$plist"
plutil -insert DTSDKName -string "macosx$sdk" "$plist"
plutil -insert DTSDKBuild -string "$(xcrun --sdk macosx --show-sdk-build-version)" "$plist"
xcode=$(xcodebuild -version 2>/dev/null)
plutil -insert DTXcode -string "$(echo $xcode | awk '/Xcode/ {split($2, v, "."); printf "%02d%d%d", v[1], v[2], v[3]}')" "$plist"
plutil -insert DTXcodeBuild -string "$(echo $xcode | awk '/Build version/ {print $3}')" "$plist"
plutil -insert DTCompiler -string com.apple.compilers.llvm.clang.1_0 "$plist"
plutil -insert BuildMachineOSBuild -string "$(sw_vers -buildVersion)" "$plist"
printf 'APPL????' > "$app/Contents/PkgInfo"

# Entitlements take the app and team identifiers from the provisioning profile.
security cms -D -i "$PROFILE" > $tmp/profile.plist
app_id=$(plutil -extract Entitlements.com\\.apple\\.application-identifier raw $tmp/profile.plist)
team_id=$(plutil -extract Entitlements.com\\.apple\\.developer\\.team-identifier raw $tmp/profile.plist)
bundle_id=$(plutil -extract CFBundleIdentifier raw "$plist")
if [[ $app_id != "$team_id.$bundle_id" ]]; then
  echo "error: $PROFILE is for $app_id; the Mac App Store needs a macOS profile for $team_id.$bundle_id" >&2
  exit 1
fi
sed -e "s/\$(APP_ID)/$app_id/" -e "s/\$(TEAM_ID)/$team_id/" Diamond.DesktopGL/macOS/Entitlements.plist > $tmp/entitlements.plist
cp "$PROFILE" "$app/Contents/embedded.provisionprofile"

xattr -cr "$app"
find "$app/Contents/MonoBundle" -name '*.dylib' -print0 | xargs -0 codesign --force --sign "$APP_SIGN"
codesign --force --sign "$APP_SIGN" --entitlements $tmp/entitlements.plist "$app"
codesign --verify --strict --verbose=2 "$app"

rm -rf $tmp
if [[ $MODE == dev ]]; then
  echo "macOS (development): $app"
  exit 0
fi
productbuild --component "$app" /Applications --sign "$PKG_SIGN" "$out/Diamond.pkg"
echo "macOS: $out/Diamond.pkg (version $VERSION, build $BUILD, $app_id)"
