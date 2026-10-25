#!/usr/bin/env bash
# Build a 16.5 s vertical reel (1080x1920, 30 fps, H.264 + AAC) from a reel spec:
#   tools/make_reel.sh spec.json out.mp4
# Frames come from tools/reel.js, the music bed from tools/lofi.py (original, no licensed audio).
set -euo pipefail
spec=$1; out=$2
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
dur=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['duration'])" "$spec")
NODE_PATH=$(npm root -g) node "$here/reel.js" "$spec" "$work/frames"
python3 "$here/lofi.py" "$dur" "$work/bed.wav"
ffmpeg -y -hide_banner -loglevel error -framerate 30 -i "$work/frames/f%04d.jpg" -i "$work/bed.wav" \
  -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.1 -preset medium -crf 20 -r 30 \
  -c:a aac -b:a 128k -ar 48000 -shortest -movflags +faststart "$out"
