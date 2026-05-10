# F08 — Video Assembly (FFmpeg)

**Статус кода: реализовано в этой итерации.**

Принимает `RenderJob{job_id, segments[], music_uri?, output_format}`, собирает финальный 9:16 1080×1920 MP4 локальным FFmpeg, грузит в MinIO, возвращает публичный URL.

## User stories

- **US-F08-1**: As an orchestrator, I want to submit a `RenderJob` and receive an MP4 URL so that downstream publication can post it to Telegram.
- **US-F08-2**: As an editor, I want each segment cropped to portrait 9:16 with center crop so that horizontal stock clips don't look stretched.
- **US-F08-3**: As an editor, I want subtitles drawn as 3-word chunks in the lower-third area so that Shorts watchers can follow without sound.
- **US-F08-4**: As an editor, I want optional background music mixed at 0.01 volume so that the voiceover stays dominant.
- **US-F08-5**: As an operator, I want render jobs idempotent — re-submitting a `succeeded` job_id returns the existing URL без повторного рендера.
- **US-F08-6**: As an operator, I want failed renders to persist a human-readable error so that I can triage in the dashboard.
- **US-F08-7**: As a developer, I want the FFmpeg command construction to be a pure function so that I can unit-test it without invoking ffmpeg.

## User flow

```
POST /v1/renders {segments: [...], music_uri?: ...}
   └─► RenderJobRepo.create(status="pending")
       └─► Celery enqueue assemble_render(job_id)

assemble_render(job_id):
   job = RenderJobRepo.get(job_id)
   if job.status == "succeeded": return job.output_uri  ← idempotency
   RenderJobRepo.set_status(job_id, "running")
   try:
       cmd = FfmpegBuilder.build(job.segments, job.music_uri)
       local_path = FfmpegRunner.run(cmd, timeout=RENDER_TIMEOUT_SEC)
       output_uri = Storage.upload(f"renders/{job_id}.mp4", local_path)
       RenderJobRepo.set_succeeded(job_id, output_uri)
   except FfmpegError as e:
       RenderJobRepo.set_failed(job_id, error=str(e))

GET /v1/renders/{job_id} → JobStatusDTO
```

## Architecture decision: pure builder + IO runner

Чтобы можно было unit-тестировать без ffmpeg, разделяем:

- `services/ffmpeg_builder.py` — **чистая функция** `build(segments, music_uri) → list[str]` (argv).
- `infra/ffmpeg.py` — `FfmpegRunner.run(argv, timeout)` — обёртка над `subprocess.run`.

Так unit-тесты валидируют структуру команды (фильтры, маппинги, входы), а интеграционный тест рендерит реальный 1.5-секундный клип, чтобы убедиться, что аргументы валидны для ffmpeg.

## Subtitle chunking rule

```
words = subtitle_text.split()
chunks = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]
chunk_duration = segment_length / max(len(chunks), 1)
```

Пустой текст → ровно одна пустая «chunk», чтобы dur распределения был корректен.

## Out of scope F08

- Подбор клипов и озвучки — это F06/F07. F08 принимает уже готовые `audio_uri`, `video_uri`, `subtitle_text` per-segment.
- Публикация в Telegram — F09.
