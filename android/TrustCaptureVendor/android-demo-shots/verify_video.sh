#!/usr/bin/env bash
# Forensic verification: extract 1 frame/sec from the ENCODED mp4, fingerprint
# each (16x16 gray signature), nearest-match against source stills, and build a
# timestamped contact sheet. This is the step that catches silently-dropped frames.
#
# Run from WSL:  bash verify_video.sh

set -euo pipefail
SHOTS_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$SHOTS_DIR/TrustCapture_Android_Demo_Narrated_v1.mp4"
WORK="$SHOTS_DIR/.verify"
mkdir -p "$WORK"; rm -f "$WORK"/* 2>/dev/null || true

if [[ ! -f "$OUT" ]]; then echo "No video found: $OUT"; exit 1; fi

echo "== Encoded video facts =="
ffprobe -v error -show_entries format=duration,format_name:stream=width,height,codec_name,pix_fmt,avg_frame_rate -of default=noprint_wrappers=1 "$OUT"

echo "== Faststart (moov atom) check =="
if ffprobe -v trace "$OUT" 2>&1 | grep -q "type:'moov'"; then echo "moov present"; fi

echo "== Black-frame check =="
ffmpeg -hide_banner -i "$OUT" -vf blackdetect=d=0.3:pix_th=0.1 -an -f null - 2>&1 | grep blackdetect || echo "No black segments."

echo "== Audio levels (no clipping / truncation) =="
ffmpeg -hide_banner -i "$OUT" -af "volumedetect" -f null - 2>&1 | grep -E "max_volume|mean_volume" || true

echo "== Extracting 1 frame/sec =="
ffmpeg -y -loglevel error -i "$OUT" -vf fps=1 "$WORK/f_%03d.png"

echo "== Fingerprint + nearest-source mapping =="
python3 - "$SHOTS_DIR" "$WORK" <<'PY'
import sys, os, glob
from PIL import Image

shots_dir, work = sys.argv[1], sys.argv[2]

def sig(path):
    im = Image.open(path).convert("L").resize((16,16))
    return list(im.getdata())

def dist(a,b):
    return sum((x-y)*(x-y) for x,y in zip(a,b))

# source signatures (the rendered captioned stills in .work)
src = {}
for p in sorted(glob.glob(os.path.join(shots_dir, ".work", "still_*.png"))):
    src[os.path.basename(p)] = sig(p)
closing = os.path.join(shots_dir, ".work", "closing.png")
if os.path.exists(closing):
    src["closing.png"] = sig(closing)

print("second -> nearest source")
for f in sorted(glob.glob(os.path.join(work, "f_*.png"))):
    s = sig(f)
    best = min(src.items(), key=lambda kv: dist(s, kv[1]))
    sec = int(os.path.basename(f).split("_")[1].split(".")[0]) - 1
    print(f"{sec:3d}s -> {best[0]}")
PY

echo "== Contact sheet (one labeled panel per ~segment) =="
# montage of the per-second frames, scaled down
ffmpeg -y -loglevel error -pattern_type glob -i "$WORK/f_*.png" \
  -vf "scale=216:-1,tile=4x8" "$SHOTS_DIR/contact_sheet_v1.png" || true
echo "Contact sheet: $SHOTS_DIR/contact_sheet_v1.png"
echo "== Verification complete =="
