#!/bin/zsh
# Records every store still with the macOS (DesktopGL) build into <dir> (default: a temporary
# folder), then builds the store images in store/ and the support page.
#
#   tools/capture_all.sh [dir]
#
# The capture mode plays the walkthrough on autopilot and saves 20 stills (01-title .. 20-instructions)
# at 2400 x 2240 into <dir>/<en|fr>/<desktop|mobile>/stills, then quits. Mobile captures show the
# touch layout (arrow buttons and WORDS). Videos: tools/make_preview_videos.sh.
# Windows stills come from tools/build_windows.sh capture (release/windows/capture), if present.
set -euo pipefail
cd "$(dirname "$0")/.."

CAP=${1:-$(mktemp -d)/capture}
mkdir -p "$CAP"
dotnet build Diamond.DesktopGL -c Release -v q -o "$CAP/bin" >/dev/null
GAME=("dotnet" "$CAP/bin/Diamond.dll")

for lang in en fr; do
  "${GAME[@]}" --capture "$CAP/$lang/desktop" --lang $lang --scale 10
  "${GAME[@]}" --capture "$CAP/$lang/mobile" --mobile --lang $lang --scale 10
  if [[ -d release/windows/capture/$lang/stills ]]; then
    mkdir -p "$CAP/$lang/windows" && cp -R release/windows/capture/$lang/stills "$CAP/$lang/windows/"
  fi
done
python3 tools/make_store_assets.py stills "$CAP"
python3 tools/make_support_page.py "$CAP"
python3 tools/make_upload_copy.py
echo "captures in $CAP"
