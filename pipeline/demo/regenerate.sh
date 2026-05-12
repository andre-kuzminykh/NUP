#!/usr/bin/env bash
# Пересобрать sample_reel.mp4. Не требует TTS/OpenAI — pure ffmpeg lavfi.
# Если хочешь поменять текст / цвет / длительность — редактируй ниже.
set -euo pipefail

cd "$(dirname "$0")"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
[ -f "$FONT" ] || { echo "DejaVuSans-Bold not found; install fonts-dejavu"; exit 1; }

ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "color=c=0x1e293b:s=1080x1920:d=15" \
  -f lavfi -i "anullsrc=cl=stereo:r=44100" \
  -vf "drawtext=fontfile=${FONT}:text='Демо смок-теста Reels':fontcolor=white:fontsize=72:box=1:boxcolor=black@0.6:boxborderw=22:x=(w-text_w)/2:y=h*0.18,\
drawtext=fontfile=${FONT}:text='Это видео собрано':fontcolor=white:fontsize=68:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h*0.72:enable='between(t,0,3)',\
drawtext=fontfile=${FONT}:text='тем же FFmpeg':fontcolor=white:fontsize=68:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h*0.72:enable='between(t,3,6)',\
drawtext=fontfile=${FONT}:text='что и боевые':fontcolor=white:fontsize=68:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h*0.72:enable='between(t,6,9)',\
drawtext=fontfile=${FONT}:text='Reels из новостей':fontcolor=white:fontsize=68:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h*0.72:enable='between(t,9,12)',\
drawtext=fontfile=${FONT}:text='Звук — заглушка':fontcolor=white:fontsize=68:box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h*0.72:enable='between(t,12,15)'" \
  -map 0:v -map 1:a \
  -c:v libx264 -pix_fmt yuv420p -preset veryfast \
  -c:a aac -shortest -movflags +faststart \
  -t 15 sample_reel.mp4

ls -lh sample_reel.mp4
