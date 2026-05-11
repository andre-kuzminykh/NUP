# F04 — Voiceover Script Generation

Превращает `Summary.content_ru` в дикторский текст 100–150 слов для Reels (~50 сек озвучки).

## User stories

- **US-F04-1**: As an editor, I want a tight 5-block voiceover (hook → essence → why → context → outro) so that Shorts hold attention to the end.
- **US-F04-2**: As a developer, I want the prompt versioned in `docs/05-prompts/voiceover-script.md` so that A/B-эксперименты можно ревьюить.
- **US-F04-3**: As an operator, I want voiceover stored in DB (`reels.voice_text_ru`) so that downstream (TTS, segmentation) reads from one place.

## User flow

```
trigger (manual or "article.published") ─► VoiceoverService(summary_id)
   └─► OpenAI(prompt + summary.content_ru) → text
       └─► ReelsRepo.upsert(article_id, voice_text_ru=text)
            └─► emit "reels.voiceover_ready"
```
