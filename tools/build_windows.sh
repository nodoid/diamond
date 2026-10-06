#!/bin/zsh
# Builds the Windows version inside the Parallels "Windows 11" VM and packages it:
#   release/windows/Diamond-<version>-<x64|arm64>.msix  (upload both to Partner Center; the Store signs them)
#   release/windows/Diamond-<version>-<x64|arm64>.zip   (the same game unpackaged, for testing on a PC)
#
# The VM shares the Mac's Downloads folder (Z:\Downloads), so the source is staged in a temporary
# folder there, built and tested with the Windows .NET SDK in C:\Build\Diamond, and the published
# builds are copied back. Pass "capture" to also record the Microsoft Store screenshots (English and
# French) with the Windows build (written to release/windows/capture/<en|fr>/stills).
set -euo pipefail
cd "$(dirname "$0")/.."

VM=${DIAMOND_VM:-"Windows 11"}
VERSION=$(dotnet msbuild Diamond.WindowsDX/Diamond.WindowsDX.csproj -getProperty:Version)
BUILD=$(dotnet msbuild Diamond.WindowsDX/Diamond.WindowsDX.csproj -getProperty:BuildNumber)
# Package version major.minor.build.0: the Store needs it to rise with every upload and the last part to be 0.
PKGVER="${VERSION%.*}.$BUILD.0"
STAGE="$HOME/Downloads/diamond-vm-transfer"
WSTAGE='Z:\Downloads\diamond-vm-transfer'
out=release/windows

prlctl status "$VM" | grep -q running || prlctl resume "$VM" || prlctl start "$VM"
rm -rf "$STAGE" && mkdir -p "$STAGE"
git archive --format=tar -o "$STAGE/src.tar" HEAD

prlctl exec "$VM" --current-user powershell -NoProfile -Command "
  \$ErrorActionPreference = 'Stop'
  Remove-Item -Recurse -Force C:\Build\Diamond, C:\Build\out -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Force C:\Build\Diamond | Out-Null
  tar -xf $WSTAGE\src.tar -C C:\Build\Diamond
  Set-Location C:\Build\Diamond
  dotnet test Diamond.Tests
  if (\$LASTEXITCODE -ne 0) { throw 'tests failed' }
  foreach (\$a in 'x64','arm64') {
    dotnet publish Diamond.WindowsDX -c Release -r win-\$a --self-contained -o C:\Build\out\\\$a -p:DebugType=none
    if (\$LASTEXITCODE -ne 0) { throw 'publish failed' }
    Remove-Item C:\Build\out\\\$a\createdump.exe -ErrorAction SilentlyContinue
    Compress-Archive -Force -Path C:\Build\out\\\$a\* -DestinationPath $WSTAGE\win-\$a.zip
  }
"

if [[ ${1:-} == capture ]]; then
  prlctl exec "$VM" --current-user powershell -NoProfile -Command "
    Remove-Item -Recurse -Force C:\Build\cap -ErrorAction SilentlyContinue
    foreach (\$l in 'en','fr') {
      Start-Process -Wait -FilePath C:\Build\out\arm64\Diamond.exe -ArgumentList '--capture',('C:\Build\cap\' + \$l),'--lang',\$l
    }
    Copy-Item -Recurse -Force C:\Build\cap $WSTAGE\capture
  "
fi

rm -rf $out && mkdir -p $out
for arch in x64 arm64; do
  cp "$STAGE/win-$arch.zip" "$out/Diamond-$VERSION-$arch.zip"
  pkg=$(mktemp -d)/package
  mkdir -p $pkg && (cd $pkg && { unzip -q "$OLDPWD/$out/Diamond-$VERSION-$arch.zip" 2>/dev/null || [[ $? -eq 1 ]]; })
  mkdir -p $pkg/Assets
  cp Diamond.WindowsDX/Windows/Assets/*.png $pkg/Assets/
  sed -e "s/\$(VERSION)/$PKGVER/" -e "s/\$(ARCH)/$arch/" Diamond.WindowsDX/Windows/AppxManifest.xml > $pkg/AppxManifest.xml
  python3 tools/make_msix.py $pkg "$out/Diamond-$VERSION-$arch.msix"
  rm -rf "$(dirname $pkg)"
done
[[ -d "$STAGE/capture" ]] && cp -R "$STAGE/capture" "$out/capture"
rm -rf "$STAGE"
echo "Windows: $out/Diamond-$VERSION-{x64,arm64}.msix (package version $PKGVER)"
ls -la $out
