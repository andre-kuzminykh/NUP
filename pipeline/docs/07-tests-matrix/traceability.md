# Traceability Matrix: Requirement → Test

Тесты помечены `@pytest.mark.req("REQ-...")`. Эта таблица генерируется вручную сейчас; план — автогенерация из маркеров (TO.3).

## F08 — Video Assembly (реализовано)

| REQ-ID | Уровень | Тест |
|---|---|---|
| REQ-F08-001 | e2e | `tests/e2e/test_render_endpoint.py::test_post_render_returns_202_and_uuid` |
| REQ-F08-001 | e2e | `tests/e2e/test_render_endpoint.py::test_full_render_round_trip` |
| REQ-F08-002 | int | `tests/integration/test_ffmpeg_real.py::test_render_output_is_1080x1920_h264` |
| REQ-F08-003 | unit | `tests/unit/test_ffmpeg_builder.py::test_each_segment_has_scale_crop_to_1080x1920` |
| REQ-F08-003 | int | `tests/integration/test_ffmpeg_real.py::test_render_output_is_1080x1920_h264` |
| REQ-F08-004 | unit | `tests/unit/test_ffmpeg_builder.py::test_voiceover_replaces_video_audio_in_filter_graph` |
| REQ-F08-005 | unit | `tests/unit/test_ffmpeg_builder.py::test_subtitle_drawtext_present_per_chunk` |
| REQ-F08-006 | unit | `tests/unit/test_ffmpeg_builder.py::test_music_uri_is_added_with_low_volume_when_provided` |
| REQ-F08-006 | unit | `tests/unit/test_ffmpeg_builder.py::test_no_music_input_when_music_uri_is_none` |
| REQ-F08-007 | unit | `tests/unit/test_video_assembly_service.py::test_uploads_to_deterministic_key` |
| REQ-F08-008 | unit | `tests/unit/test_render_job_state.py::test_legal_transitions` |
| REQ-F08-008 | unit | `tests/unit/test_render_job_state.py::test_illegal_transitions_raise` |
| REQ-F08-009 | unit | `tests/unit/test_video_assembly_service.py::test_ffmpeg_failure_marks_job_failed_with_message` |
| REQ-F08-010 | unit | `tests/unit/test_video_assembly_service.py::test_idempotent_resubmit_skips_ffmpeg` |
| REQ-F08-011 | unit | `tests/unit/test_ffmpeg_builder.py::test_builder_is_pure_no_io` |
| REQ-F08-011 | unit | `tests/unit/test_ffmpeg_builder.py::test_builder_returns_argv_list_starting_with_ffmpeg` |
| REQ-F08-012 | unit | `tests/unit/test_subtitle_chunking.py::test_chunk_three_words[*]` |

## Прочие фичи — план тестов

(каждое `pytest.mark.req` живёт в коде, эта таблица заполняется по мере добавления тестов)

| REQ-ID | Тест-кандидат |
|---|---|
| REQ-F01-003 | unit + httpx-mock: проверить, что HTTP идёт через `proxies=` |
| REQ-F01-006 | unit: канонизация URL (UTM, fragment, host case) |
| REQ-F02-002 | unit: regex проверка `*…*\n\n` |
| REQ-F03-001 | unit: фейковый clock + RateLimiter ≥60s |
| REQ-F05-001 | unit: jsonschema validate против fixture-ответа |
| REQ-F06-003 | int: ffprobe фикстурного MP3 |
| REQ-F07-003 | unit: пикер не возвращает уже выбранный URL |
| REQ-F09-003 | int: после publish строка БД содержит все три поля |
| REQ-F10-002 | int: убить handler один раз, доставка повторяется |
