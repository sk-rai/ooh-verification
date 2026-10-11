#!/usr/bin/env bash
# TrustCapture Android Demo — Narrated video builder
# Mirrors the proven web pipeline: fit+pad, FORCED rgb24, measured-speech timing,
# concat assembly, closing card, narration mux, forensic per-second verification.
#
# Run from WSL:  bash build_narrated.sh
# Prereqs: ffmpeg, ffprobe, python3 + edge-tts

set -euo pipefail

# ---------- Config ----------
SHOTS_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$SHOTS_DIR/manifest.txt"
WORK="$SHOTS_DIR/.work"
OUT="$SHOTS_DIR/TrustCapture_Android_Demo_Narrated_v1.mp4"

# Target canvas (portrait). Fit+pad everything to this. Change if emulator differs.
CANVAS_W=1080
CANVAS_H=2340
FPS=30
BG_COLOR="0x0D3B2E"   # app's dark green background (approx) — padding color

VOICE="en-US-AndrewNeural"
RATE="-4%"            # edge-tts: use equals form --rate=-4%

LEAD=0.6             # seconds of silence before speech in a segment
TAIL=0.9            # seconds after speech
GAP=0.25            # gap between segments

mkdir -p "$WORK"
rm -f "$WORK"/*.png "$WORK"/*.mp3 "$WORK"/*.wav "$WORK"/seg_*.mp4 "$WORK"/concat.txt 2>/dev/null || true

# ---------- Helpers ----------
render_still() {
  # $1 = source png, $2 = caption text, $3 = output png
  local src="$1" cap="$2" dst="$3"
  # Fit within canvas preserving aspect, pad with bg, FORCE rgb24, burn caption bar.
  # Caption: dark semi-transparent bar bottom, white text.
  local esc_cap
  esc_cap=$(printf '%s' "$cap" | sed "s/'/\\\\'/g; s/:/\\\\:/g")
  ffmpeg -y -loglevel error -i "$src" -filter_complex "
    [0:v]scale=${CANVAS_W}:${CANVAS_H}:force_original_aspect_ratio=decrease,
         pad=${CANVAS_W}:${CANVAS_H}:(ow-iw)/2:(oh-ih)/2:color=${BG_COLOR},
         drawbox=x=0:y=ih-220:w=iw:h=220:color=black@0.55:t=fill,
         drawtext=text='${esc_cap}':fontcolor=white:fontsize=46:
                  x=(w-text_w)/2:y=h-150:line_spacing=10:
                  fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf,
         format=rgb24[v]" -map "[v]" -frames:v 1 "$dst"
}

measure_audio() {
  # $1 = audio file -> prints duration seconds
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"
}

# ---------- Build segments ----------
echo "== Generating narration + stills =="
idx=0
: > "$WORK/concat.txt"
: > "$WORK/timing.csv"
echo "segment,source,speech_sec,segment_sec" >> "$WORK/timing.csv"

while IFS='|' read -r fname caption narration; do
  # skip comments/blank
  [[ "$fname" =~ ^#.*$ || -z "${fname// }" ]] && continue
  idx=$((idx+1))
  n=$(printf "%02d" "$idx")
  src="$SHOTS_DIR/$fname"
  if [[ ! -f "$src" ]]; then
    echo "!! Missing screenshot: $src — did you capture it?"; exit 1
  fi

  # 1) narration mp3
  mp3="$WORK/seg_${n}.mp3"
  python3 -m edge_tts --voice "$VOICE" --rate="$RATE" --text "$narration" --write-media "$mp3" >/dev/null
  speech=$(measure_audio "$mp3")

  # 2) segment duration
  seg=$(python3 -c "print(round($LEAD + $speech + $TAIL, 3))")
  echo "$n,$fname,$speech,$seg" >> "$WORK/timing.csv"

  # 3) rendered captioned still (uniform rgb24)
  still="$WORK/still_${n}.png"
  render_still "$src" "$caption" "$still"

  # 4) per-segment video (still for seg duration) + padded audio
  seg_mp4="$WORK/seg_${n}.mp4"
  # audio: lead silence + speech + tail silence
  padded_wav="$WORK/aud_${n}.wav"
  ffmpeg -y -loglevel error -f lavfi -t "$LEAD" -i anullsrc=r=48000:cl=mono \
         -i "$mp3" -f lavfi -t "$TAIL" -i anullsrc=r=48000:cl=mono \
         -filter_complex "[0][1][2]concat=n=3:v=0:a=1[a]" -map "[a]" "$padded_wav"
  ffmpeg -y -loglevel error -loop 1 -t "$seg" -i "$still" -i "$padded_wav" \
         -c:v libx264 -r "$FPS" -pix_fmt yuv420p -c:a aac -b:a 160k -shortest "$seg_mp4"

  echo "file '$seg_mp4'" >> "$WORK/concat.txt"
  # inter-segment gap (silent still)
  gap_mp4="$WORK/gap_${n}.mp4"
  ffmpeg -y -loglevel error -loop 1 -t "$GAP" -i "$still" -f lavfi -t "$GAP" -i anullsrc=r=48000:cl=mono \
         -c:v libx264 -r "$FPS" -pix_fmt yuv420p -c:a aac -b:a 160k -shortest "$gap_mp4"
  echo "file '$gap_mp4'" >> "$WORK/concat.txt"
done < "$MANIFEST"

# ---------- Closing card ----------
echo "== Building closing card =="
close_png="$WORK/closing.png"
ffmpeg -y -loglevel error -f lavfi -i "color=c=${BG_COLOR}:s=${CANVAS_W}x${CANVAS_H}" -frames:v 1 \
  -vf "drawtext=text='TrustCapture':fontcolor=white:fontsize=90:x=(w-text_w)/2:y=(h/2)-120:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,
       drawtext=text='trusted evidence for field operations':fontcolor=white@0.85:fontsize=44:x=(w-text_w)/2:y=(h/2)+10:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf,
       format=rgb24" "$close_png"
close_mp4="$WORK/closing.mp4"
ffmpeg -y -loglevel error -loop 1 -t 3.0 -i "$close_png" -f lavfi -t 3.0 -i anullsrc=r=48000:cl=mono \
  -c:v libx264 -r "$FPS" -pix_fmt yuv420p -c:a aac -b:a 160k -shortest "$close_mp4"
echo "file '$close_mp4'" >> "$WORK/concat.txt"

# ---------- Assemble ----------
echo "== Concatenating =="
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/concat.txt" \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k "$OUT"

echo "== Done: $OUT =="
ffprobe -v error -show_entries format=duration:stream=width,height,codec_name,pix_fmt -of default=noprint_wrappers=1 "$OUT"
echo "Run verify_video.sh next for forensic per-second check."
