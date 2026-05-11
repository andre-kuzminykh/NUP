# F06 — TTS Synthesis

Озвучка каждого сегмента через ElevenLabs, MP3 в MinIO под ключом `tts/{reels_id}/{segment_id}.mp3`.

## User stories

- **US-F06-1**: As an editor, I want each segment voiced with the same voice ID so that timbre is consistent across the Reels.
- **US-F06-2**: As an operator, I want TTS calls retried (3x backoff) and rate-limited to ElevenLabs quota так что мы не получим 429 при пакетной обработке.
- **US-F06-3**: As a developer, I want duration of each MP3 measured (ffprobe) and saved to `Segment.audio_duration_sec` so that assembly knows real timings.

## User flow

```
event "reels.segments_ready" ─► for each segment in reels:
   TTSService.synthesize(segment.text, voice_id)
     ├─► HTTP POST elevenlabs (via proxy) → mp3 bytes
     ├─► Storage.upload(key, bytes) → s3_uri
     ├─► ffprobe(s3_uri) → duration_sec
     └─► SegmentRepo.update(audio_uri, audio_duration_sec)
event "reels.tts_complete" when ALL segments have audio_uri
```
