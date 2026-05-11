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

# --- F003 / F012 — Review callbacks (bilingual via core.i18n.bi) ----------

REVIEW_APPROVED_RU = "✅ Опубликовано в канал."
REVIEW_APPROVED_EN = "✅ Published to channel."

REVIEW_DECLINED_RU = "❌ Отклонено, в канал не уходит."
REVIEW_DECLINED_EN = "❌ Declined, will not be posted."

REVIEW_EDIT_STARTED_RU = "✏️ Режим редактирования включён. Полный UI кадров — в следующей итерации."
REVIEW_EDIT_STARTED_EN = "✏️ Edit mode on. Full per-frame UI is coming in the next iteration."

REVIEW_INVALID_RU = "⚠️ Неизвестное действие, попробуйте ещё раз."
REVIEW_INVALID_EN = "⚠️ Unknown action, please retry."

REVIEW_BACKEND_ERROR_RU = "⚠️ Бэкенд не отвечает, попробуйте позже."
REVIEW_BACKEND_ERROR_EN = "⚠️ Backend is unavailable, please retry later."
