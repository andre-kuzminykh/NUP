"""
Vocab — все строки, видимые пользователю, в одном месте.

## Трассируемость
Feature: F001 — Welcome and main menu
Feature: F002 — Render job status

## Бизнес-контекст
Не хардкодим тексты в Answer-ах: единый источник правды + готовое
место под локализацию.
"""

WELCOME = (
    "👋 *NUP Pipeline Bot*\n\n"
    "Доступные команды:\n"
    "• /start — это сообщение\n"
    "• /render\\_status `<job_id>` — статус задачи рендера"
)

RENDER_STATUS_FOUND = (
    "📹 *Render* `{job_id}`\n"
    "статус: `{status}`\n"
    "uri: {output_uri}"
)

RENDER_NOT_FOUND = "❌ Render с таким id не найден."

RENDER_INVALID_UUID = (
    "❌ Неверный формат UUID.\n"
    "Пример: `/render_status 11111111-2222-3333-4444-555555555555`"
)

RENDER_BACKEND_ERROR = "⚠️ Бэкенд временно недоступен, попробуйте позже."
