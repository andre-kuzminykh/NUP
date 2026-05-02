# SPEC — Feature 9: TUI Enhancement (rusty-claude-cli)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | TUI Enhancement (rendering, status bar, tool visualization, themes) |
| **Description (Goal / Scope)** | По плану `TUI-ENHANCEMENT-PLAN.md` — 6 фаз улучшений терминального UI: status bar (Phase 1), markdown stream rendering + thinking indicator (Phase 2), визуализация tool-вызовов с collapsible output и diff-coloring (Phase 3), pager + fuzzy session picker + tab-completion (Phase 4), темы и terminal capability detection (Phase 5), полноэкранный split-pane режим через ratatui (Phase 6). По умолчанию — inline REPL со scrollback; ratatui — opt-in. Вне скоупа: бизнес-логика runtime/tools (F1/F4). |
| **Client** | Разработчики, использующие интерактивный REPL; пользователи, читающие большие выводы tools. |
| **Problem** | Сейчас REPL — plain text без визуальной структуры: сложно отслеживать стоимость, неудобно читать markdown, tool output стенами заливает экран, цветные diff'ы отсутствуют. |
| **Solution** | Модуль `tui/` с подкомпонентами `status_bar.rs`, `tool_panel.rs`, `diff_view.rs`, `pager.rs`, `theme.rs`. Phase 1–5 апгрейдят inline-режим; Phase 6 добавляет ratatui-оверлей. |
| **Metrics** | (1) Status-bar обновляется ≤ 100 мс на event; (2) Markdown streaming без визуальных артефактов на 4+ терминалах; (3) Tool output > 50 строк автоматически collapsed; (4) Темы переключаются без рестарта; (5) Ratatui-режим работает на 3 OS. |

## 2. User Stories and Use Cases

### US-1: Status bar + markdown rendering (Phase 1+2)

| Field | Value |
|---|---|
| **Role** | Разработчик в REPL |
| **User Story** | Как пользователь, я хочу видеть persistent статус-строку (модель, mode, sessionID, tokens, $cost, git branch) и live-Markdown в стриме, чтобы не запускать `/status` и `/cost` вручную и читать ответы как структурированный текст. |
| **UX Flow** | Внизу терминала — закреплённая полоса статуса; стрим модели рендерится с заголовками/жирным/inline code; "thinking" индикатор — анимированные точки. |

**UC-1.1: Status bar live-update.** Given REPL запущен → When модель стримит ответ → Then статус-строка обновляет токены/cost после каждого `message_delta` и duration по таймеру turn'а.

**FR-1:** Status bar содержит поля model_alias, permission_mode, session_id (8 chars), tokens_in/out, cost_usd, git_branch, turn_duration. **FR-2:** Markdown-renderer поддерживает `# ## ###`, `**bold**`, `*italic*`, ` ``` ` блоки, inline `code`, lists. **NFR-1:** Status update не вызывает full-screen redraw (ANSI cursor save/restore). **NFR-2:** Markdown streaming не "заикается" — частичные блоки буферизуются до closing token.

**UC-1.2: Thinking indicator + remove artificial delay.** Given модель в режиме extended-thinking → When стрим начался, но контента ещё нет → Then показывается анимация (braille/dots) с текстом "thinking…"; после первого content_block — анимация исчезает.

**FR-3:** Thinking indicator анимируется на отдельной строке с erase-on-content. **FR-4:** Удалить искусственный 8 мс sleep между chunks (исторический throttle). **NFR-3:** Анимация не выводится в non-TTY (pipe).

### US-2: Tool visualization + diff coloring (Phase 3)

| Field | Value |
|---|---|
| **Role** | Разработчик, читающий tool-вывод |
| **User Story** | Как пользователь, я хочу видеть tool-вызовы как сворачиваемые блоки с syntax highlighting и цветной unified diff для edit, чтобы не утонуть в 500 строках bash output. |

**UC-2.1: Collapsible tool output.** Given tool вернул > 50 строк → When tool_result рендерится → Then показывается первые 20 строк + `[+] Expand (480 more lines)`; нажатие на индикатор раскрывает.

**FR-5:** Treshold collapse конфигурируется (default 50 строк). **FR-6:** Syntax highlighting через `syntect`/`tree-sitter` для bash, файлов с extension, REPL output. **FR-7:** Tool timeline — компактная строка `🔧 bash → ✓ | read_file → ✓ | edit → ⚠`. **NFR-4:** Highlighting lazy (только видимая часть).

**UC-2.2: Unified diff for edit.** Given `edit` tool заменил строки → When tool_result рендерится → Then показывается red `-` / green `+` unified diff с context ±3 строки.

**FR-8:** Diff-renderer строит unified diff из `(old_content, new_content)` или принимает готовый patch. **NFR-5:** Diff не должен требовать external `diff` binary — pure Rust (через `similar` crate). **NFR-6:** Длинные diff'ы автоматически paged.

### US-3: Themes + ratatui split-pane (Phase 5–6)

| Field | Value |
|---|---|
| **Role** | Разработчик с предпочтениями по UX |
| **User Story** | Как пользователь, я хочу выбирать тему (dark/light/solarized/catppuccin) и опционально включать full-screen split-pane режим, чтобы адаптировать UI под мои привычки. |

**UC-3.1: Theme switching.** Given пользователь работает в светлом терминале → When `/theme catppuccin-latte` → Then цвета status bar / syntax / diff обновляются немедленно; настройка сохраняется в `~/.claw/settings.json`.

**FR-9:** Реестр тем: dark, light, solarized-dark/light, catppuccin-mocha/latte; кастомные через TOML/JSON. **FR-10:** Detection capabilities: ANSI-256 vs truecolor — fallback автоматически. **NFR-7:** Spinner-стиль (braille/bar/moon) — отдельная настройка темы.

**UC-3.2: Full-screen ratatui mode.** Given `claw --tui full` → When запуск → Then экран делится: top — conversation+scrollback, bottom — input, sidebar — tool panel; мышь работает (scroll, expand, copy); PgUp/PgDn навигация; `?` — overlay help.

**FR-11:** Опт-ин full-screen через `--tui full` или `/tui full` slash. **FR-12:** Mouse capture (через crossterm) с поддержкой scroll, click-to-expand, drag-to-select. **NFR-8:** Layout responsive — корректно при resize терминала.

## 3. Architecture / Solution

| Area | Fill In |
|---|---|
| **Client Type** | Inline TTY (default) или ratatui full-screen (opt-in) |
| **Backend** | `tui/` модуль в `rusty-claude-cli` крейте с подкомпонентами status_bar/tool_panel/diff_view/pager/theme |
| **Libs** | `crossterm` (terminal control), `ratatui` (full-screen), `syntect`/`tree-sitter` (syntax), `similar` (diff), `unicode-width` (wide chars) |
| **Data Flow** | События runtime → tui-renderer → ANSI/ratatui draw calls. Theme → колоризатор оборачивает renderer. |
| **Infra** | TTY с поддержкой ANSI/cursor control; truecolor желательно но не обязательно |

## 4. Work Plan

| UC | Task | DoD | Subtasks |
|---|---|---|---|
| UC-1.1 | T-1: Status bar (Phase 1) с live update | Все поля обновляются; нет flicker | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2: Markdown stream + thinking indicator (Phase 2) | Markdown без артефактов; idle-anim удаляется на content | ST-4, ST-5 |
| UC-2.1 | T-3: Collapsible tool panel + syntax highlighting + timeline (Phase 3) | Tool > 50 строк collapsed; bash highlighted | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4: Unified diff renderer + pager + slash `/diff` улучшение (Phase 4) | Diff цветной; pager j/k/q работает | ST-9, ST-10 |
| UC-3.1, UC-3.2 | T-5: Themes (Phase 5) + ratatui full-screen (Phase 6) | 4+ тем; full-screen на 3 OS | ST-11, ST-12 |

## 5. Detailed Task Breakdown

**T-1 / Status bar.** ST-1: компонент с slots; ST-2: подписка на runtime/telemetry events; ST-3: ANSI cursor save/restore без full redraw.
**T-2 / Markdown + thinking.** ST-4: streaming Markdown parser (буферизация incomplete blocks); ST-5: braille-spinner в отдельной строке + erase on content.
**T-3 / Tool panel.** ST-6: collapse logic с indicator; ST-7: syntect-интеграция per-language; ST-8: timeline-line с emoji.
**T-4 / Diff + pager.** ST-9: similar-based unified diff renderer; ST-10: pager (j/k/q + half-page-down) с поддержкой ANSI passthrough.
**T-5 / Themes + ratatui.** ST-11: registry тем + capability detection + `/theme` slash; ST-12: ratatui split-pane layout (top/bottom/sidebar) + mouse capture.
