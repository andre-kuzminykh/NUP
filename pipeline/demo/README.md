# Sample Reel

`sample_reel.mp4` — реальный MP4, собранный тем же FFmpeg-пайплайном, что
будет работать в production-команде `python -m nup_pipeline.cli.make_reel`:

- 1080×1920 (вертикалка, формат Telegram Reels / Shorts).
- H.264 video + AAC audio, 15 сек, ~85 КБ.
- Тёмно-синий фон (`0x1e293b`).
- Жирный заголовок в верхней трети (Cyrillic — шрифт DejaVuSans-Bold).
- Субтитры по 3 слова в нижней трети, 5 чанков по 3 сек.
- Аудио — silence (демо без TTS; в боевой команде это сгенерированный голос).

## Как посмотреть

### Из VM
Если ты в `~/nup` на VM — файл там же лежит после `git pull`:
```bash
ls -lh pipeline/demo/sample_reel.mp4
```

Скачать на Mac через IAP:
```bash
gcloud compute scp human-1:~/nup/pipeline/demo/sample_reel.mp4 ~/Downloads/ \
    --project=i-crossbar-433120-v3 --zone=europe-west1-b --tunnel-through-iap
open ~/Downloads/sample_reel.mp4
```

### Через GitHub
Открой ветку `claude/google-sheets-articles-51f7C` на github.com, перейди в
`pipeline/demo/`, кликни `sample_reel.mp4` — GitHub покажет встроенный
плеер либо предложит скачать.

## Как пересобрать с другими параметрами

См. `make_reel.py` для боевого пайплайна (с реальным TTS и текстом из БД).
Чтобы пересобрать этот демо — посмотри в `regenerate.sh` рядом.
