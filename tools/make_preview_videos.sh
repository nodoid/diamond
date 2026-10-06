#!/bin/zsh
# App preview videos for the App Store (iPhone, iPad) and the Mac App Store, in English and French.
# Run after every release build (tools/build_release.sh, tools/build_desktop.sh).
#
#   tools/make_preview_videos.sh
#
# The game's capture mode (--capture <dir> --video) plays the walkthrough's highlights and writes every
# frame at 30 fps plus a soundtrack (the Toccata and the sound effects). The touch layout (orders picked
# from the WORDS list) is used for iPhone and iPad, the desktop layout (orders typed) for the Mac.
# Each video is about 28 s (Apple allows 15-30 s), H.264 high profile, AAC stereo, saved (only) in
# ~/Movies/The Diamond of Cursed Island/ as "Cursed Island - <iPhone|iPad|Mac> app preview <size> - <language>.mp4".
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
dotnet build Diamond.DesktopGL -c Release -v q -o "$TMP/bin" >/dev/null

# encode <capture dir> <width> <height> <name>: the game centred over a blurred, darkened copy of itself.
encode() {
  local dir=$1 w=$2 h=$3 out="$MOVIES/$4.mp4"
  ffmpeg -y -loglevel error -framerate 30 -i "$dir/frames/%05d.jpg" -i "$dir/audio.wav" \
    -filter_complex "[0:v]split[a][b];[a]scale=${w}:${h}:force_original_aspect_ratio=increase,crop=${w}:${h},gblur=sigma=28,eq=brightness=-0.28[bg];[b]scale=-2:${h}:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]" \
    -map "[v]" -map 1:a -c:v libx264 -profile:v high -level 4.0 -preset slow -crf 17 -r 30 \
    -c:a aac -b:a 256k -ar 44100 -ac 2 -shortest -movflags +faststart "$out"
  printf '%s  %s s\n' "$out" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out" | cut -c1-5)"
}
MOVIES="$HOME/Movies/The Diamond of Cursed Island"
mkdir -p "$MOVIES"

typeset -A NAME=(en English fr French)
for lang in en fr; do
  for layout in mobile desktop; do
    dir="$TMP/$lang-$layout"
    flags=(--video --lang $lang --scale 6)
    [[ $layout == mobile ]] && flags+=(--mobile)
    dotnet "$TMP/bin/Diamond.dll" --capture "$dir" "${flags[@]}"
    if [[ $layout == mobile ]]; then
      encode "$dir" 1920 886 "Cursed Island - iPhone app preview 1920x886 - ${NAME[$lang]}"
      encode "$dir" 1600 1200 "Cursed Island - iPad app preview 1600x1200 - ${NAME[$lang]}"
    else
      encode "$dir" 1920 1080 "Cursed Island - Mac app preview 1920x1080 - ${NAME[$lang]}"
    fi
    rm -rf "$dir"
  done
done
