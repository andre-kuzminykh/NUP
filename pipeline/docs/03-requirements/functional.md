# Functional Requirements

ID-конвенция: `REQ-Fxx-NNN`. Тесты помечают эти ID через pytest-маркер `@pytest.mark.req("REQ-F08-001")`.

## F01 — Source Ingestion

| ID | Требование |
|---|---|
| REQ-F01-001 | Система MUST поддерживать типы источников: `rss`, `html`, `youtube_channel`, `linkedin_profile`, `x_profile`, `telegram_channel`. |
| REQ-F01-002 | Каждый источник MUST хранить `id`, `kind`, `url`, `is_active`, `last_seen_link`, `failure_count`, `cooldown_until`. |
| REQ-F01-003 | Все исходящие HTTP-запросы к источникам MUST идти через прокси из `PROXY_POOL`. Запрос без прокси MUST падать с `ConfigError`, если `PROXY_POOL` не пуст и стратегия не `direct`. |
| REQ-F01-004 | После 3 подряд провалов на одном прокси этот прокси MUST быть помечен `unhealthy` на 10 минут. |
| REQ-F01-005 | После HTTP 429/403 MUST быть автоматический retry со следующим прокси (до исчерпания пула). |
| REQ-F01-006 | Дедупликация MUST идти по канонической форме `link` (нижний регистр host, убрать utm_*, фрагмент). |
| REQ-F01-007 | Адаптер MUST возвращать `Article{link, title, source_id, published_at?, raw_content}` или `None`. |

## F02 — Summarization

| ID | Требование |
|---|---|
| REQ-F02-001 | Промт MUST загружаться из `docs/05-prompts/article-summary.md` без хардкода в коде. |
| REQ-F02-002 | Вывод MUST содержать заголовок жирным (`*…*`) на первой строке и тело после пустой строки. |
| REQ-F02-003 | При нарушении формата MUST быть один retry с инструкцией "format strictly". |

## F03 — Telegram Text Publication

| ID | Требование |
|---|---|
| REQ-F03-001 | Между двумя последовательными публикациями в один и тот же `chat_id` MUST пройти ≥60 сек (Wait в исходном n8n воркфлоу). |
| REQ-F03-002 | При HTTP 5xx из Telegram MUST быть до 3 ретраев с backoff 1s/4s/16s. |
| REQ-F03-003 | Каждая публикация MUST логироваться в `publications` с `message_id`, `status`, `error?`. |

## F04 — Voiceover Script

| ID | Требование |
|---|---|
| REQ-F04-001 | Промт MUST загружаться из `docs/05-prompts/voiceover-script.md`. |
| REQ-F04-002 | Длина результата MUST быть 80–180 слов; вне диапазона — один retry. |
| REQ-F04-003 | Результат MUST сохраняться в `reels.voice_text_ru`. |

## F05 — Segment Decomposition

| ID | Требование |
|---|---|
| REQ-F05-001 | Вывод MUST быть валидным JSON со схемой `{segments: [{id:int, text:str, keywords:str[1..5], estimated_duration_sec:int}]}`. |
| REQ-F05-002 | При invalid JSON MUST быть один retry с инструкцией "ONLY JSON". |
| REQ-F05-003 | Каждый сегмент MUST иметь 1–5 ключевых слов на английском (1–3 слова в каждом). |

## F06 — TTS

| ID | Требование |
|---|---|
| REQ-F06-001 | TTS MUST использовать ElevenLabs `eleven_multilingual_v2`, voice_id берётся из конфига Reels. |
| REQ-F06-002 | MP3 MUST загружаться в S3 по ключу `tts/{reels_id}/{segment_id}.mp3`. |
| REQ-F06-003 | После загрузки MUST вычисляться `audio_duration_sec` через ffprobe и сохраняться в `Segment.audio_duration_sec`. |

## F07 — Stock & Vision

| ID | Требование |
|---|---|
| REQ-F07-001 | Pexels MUST вызываться с `orientation=portrait`, `per_page=3`. |
| REQ-F07-002 | Vision MUST использовать `gpt-4o-mini`, описание ≤2 предложений на русском. |
| REQ-F07-003 | Picker MUST вернуть один `best_video_url` per segment, отсутствующий в уже выбранных другими сегментами Reels. |

## F08 — Video Assembly **(имплементировано)**

| ID | Требование |
|---|---|
| REQ-F08-001 | API MUST принимать POST `/v1/renders` с N≥1 сегментов; ответ — `RenderJob{job_id, status="pending"}`. |
| REQ-F08-002 | Финальный файл MUST быть MP4 H.264 1080×1920 9:16. |
| REQ-F08-003 | Каждое видео сегмента MUST быть масштабировано+обрезано до 1080×1920 центром. |
| REQ-F08-004 | Каждый сегмент MUST использовать заданный `audio_uri` как звуковую дорожку (исходный звук видео заглушается). |
| REQ-F08-005 | Субтитры MUST резаться на чанки по 3 слова и распределяться равномерно по длине сегмента, в нижней трети кадра. |
| REQ-F08-006 | При наличии `music_uri` фоновая дорожка MUST быть смикширована с громкостью 0.01 на полную длину timeline. |
| REQ-F08-007 | Финальный файл MUST загружаться в S3 по детерминированному ключу `renders/{job_id}.mp4`. |
| REQ-F08-008 | Состояния задачи: `pending` → `running` → (`succeeded` ∣ `failed`). Любой иной переход MUST быть отклонён `IllegalStateError`. |
| REQ-F08-009 | При сбое FFmpeg задача MUST стать `failed`, сообщение об ошибке MUST быть сохранено в `error_message`. |
| REQ-F08-010 | Повторная отправка `succeeded` job_id MUST вернуть тот же `output_uri` без повторного рендера. |
| REQ-F08-011 | `FfmpegBuilder.build()` MUST быть чистой функцией (не делать I/O), детерминированно возвращать `argv: list[str]`. |
| REQ-F08-012 | Subtitle chunking MUST соответствовать правилу: пустой текст → одна пустая chunk; иначе — `ceil(N/3)` чанков по 3 слова. |

## F09 — Reels Publication

| ID | Требование |
|---|---|
| REQ-F09-001 | Заголовок и описание MUST генерироваться двумя независимыми промтами и склеиваться в одной caption. |
| REQ-F09-002 | На Telegram 5xx MUST быть один retry. |
| REQ-F09-003 | После успешной публикации в БД MUST обновляться `video_url`, `title_video_ru`, `caption_video_ru`. |

## F10 — Orchestration

| ID | Требование |
|---|---|
| REQ-F10-001 | Celery beat MUST публиковать задачи ингеста по расписанию из конфига источника. |
| REQ-F10-002 | События MUST публиковаться через единый `EventBus` (Redis Streams) с at-least-once-семантикой. |
| REQ-F10-003 | CLI `nup replay` MUST поддерживать перезапуск с шагов `summary`, `script`, `segments`, `tts`, `stock`, `assemble`, `publish`. |
