# Claw Code — Specification Index

> Полная спецификация проекта **ultraworkers/claw-code** — Rust-реализации публичного CLI-агента `claw`. Канонический workspace находится в `rust/`, исходник истины — `ultraworkers/claw-code`.

## Контекст репозитория

| Параметр | Значение |
|---|---|
| Репозиторий | https://github.com/ultraworkers/claw-code |
| Основной язык | Rust (96.5%) |
| Вспомогательный язык | Python (3.1%) |
| Платформы | macOS, Linux, Windows (PowerShell, Git Bash, WSL) |
| Workspace | 9 крейтов в `rust/crates/` |
| Размер | ~48 599 строк Rust + 292 коммита |
| Дистрибуция | `git clone` + `cargo build --workspace` (crate `claw-code` на crates.io — deprecated stub) |

## Высокоуровневая философия

> *"Humans set direction; claws perform the labor."*

Claw Code — это **machine-first coding harness**, в котором люди задают стратегическое направление, а AI-агенты ("claws") координируют и выполняют работу. Основная аудитория — не разработчики, а боты/агенты, подключённые через плагины и webhooks.

Три ключевых компонента экосистемы:
- **OmX** — конвертирует директивы в структурированные протоколы выполнения
- **clawhip** — маршрутизирует события и уведомления вне контекстного окна агента
- **OmO** — координация мульти-агентов и разрешение конфликтов

## Карта фич

| # | Feature | Описание | Файл |
|---|---------|----------|------|
| 1 | **CLI Core & Interactive REPL** | Главный бинарь `claw`, REPL, slash-команды, режимы запуска | [feature-01-cli-core-repl.md](./feature-01-cli-core-repl.md) |
| 2 | **Multi-Provider AI Integration** | Anthropic / xAI / OpenAI-совместимые / DashScope, маршрутизация по префиксам, model aliases | [feature-02-multi-provider.md](./feature-02-multi-provider.md) |
| 3 | **Worker Lifecycle & Diagnostics** | Типизированные lifecycle-state, `doctor`/`status`/`state`/`sandbox`, preflight, `worker-state.json` | [feature-03-worker-lifecycle.md](./feature-03-worker-lifecycle.md) |
| 4 | **Built-in Tools & Permission System** | Bash / FileRead / FileWrite / Grep / Glob / Edit, permission-modes, песочница | [feature-04-tools-permissions.md](./feature-04-tools-permissions.md) |
| 5 | **Session Management & Resume** | `.claw/sessions/`, `--resume latest`, per-worktree изоляция, идентичность сессии | [feature-05-session-management.md](./feature-05-session-management.md) |
| 6 | **Branch Awareness & Auto-Recovery** | Stale-branch detection, recovery ledger, 6 авто-рецептов, green-ness contract | [feature-06-branch-recovery.md](./feature-06-branch-recovery.md) |
| 7 | **Event Schema & Telemetry (Clawhip)** | Каноническая схема lane-событий, ordering, provenance, deduplication, аудиенс-views | [feature-07-event-telemetry.md](./feature-07-event-telemetry.md) |
| 8 | **MCP & Plugin Lifecycle** | McpToolRegistry, LspRegistry, plugin lifecycle contract, partial-success | [feature-08-mcp-plugins.md](./feature-08-mcp-plugins.md) |
| 9 | **TUI Enhancement** | Status bar, markdown stream, collapsible tool panel, diff coloring, темы, ratatui split-pane | [feature-09-tui-enhancement.md](./feature-09-tui-enhancement.md) |
| 10 | **ACP / Zed Integration** | JSON-RPC over stdio, `claw acp` server, session/tool frames, permission elevation | [feature-10-acp-zed.md](./feature-10-acp-zed.md) |
| 11 | **Compat-Harness** | Auto-extract tool manifests, mock anthropic service, 10 parity scenarios, capture script | [feature-11-compat-harness.md](./feature-11-compat-harness.md) |
| 12 | **Agents / Skills / System-Prompt** | `claw agents/skills/system-prompt` subcommands, реестры, effective-prompt composition | [feature-12-agents-skills-prompt.md](./feature-12-agents-skills-prompt.md) |

## Соответствие крейтов и фич

| Крейт | Покрывает фичи |
|---|---|
| `rusty-claude-cli` | F1, F3, F9, F10 |
| `runtime` | F1, F4, F5, F12 |
| `commands` | F1, F12 |
| `api` | F2 |
| `tools` | F4, F11 (extraction) |
| `telemetry` | F3, F7 |
| `plugins` | F8 |
| `mock-anthropic-service` | F2, F11 (тестирование) |
| `compat-harness` | F11 (manifests + parity), используется F2/F8 |

## Глобальные NFR (применимы ко всем фичам)

| ID | Требование |
|---|---|
| GNFR-1 | `cargo test --workspace` и `cargo clippy --workspace --all-targets -- -D warnings` проходят без warnings |
| GNFR-2 | Скрипт `scripts/fmt.sh --check` проходит для всего рабочего пространства |
| GNFR-3 | Все диагностические verbs поддерживают `--output-format json` для машиночитаемого вывода |
| GNFR-4 | Никаких `#[ignore]` тестов в production-ветке (нет скрытых отказов) |
| GNFR-5 | Кроссплатформенность: macOS, Linux, Windows (бинарь `claw`/`claw.exe`) |
| GNFR-6 | Конфигурация резолвится в порядке: `~/.claw.json` → `~/.config/claw/settings.json` → `<repo>/.claw.json` → `<repo>/.claw/settings.json` → `<repo>/.claw/settings.local.json` |

## Порядок чтения

Спецификации можно читать независимо, но рекомендуется следующий порядок для понимания зависимостей:

```
F1 (CLI Core) ──┬─ F9  (TUI поверх REPL)
                ├─ F10 (ACP — альтернатива REPL)
                ├─ F12 (agents/skills/system-prompt)
                ├─ F2  (Providers) ─┐
                └─ F4  (Tools) ─────┼─ F5 (Sessions)
                                    │
F3 (Lifecycle) ─────────────────────┼─ F6 (Branch/Recovery)
                                    │
F7 (Events) ────────────────────────┴─ F8 (Plugins/MCP)

F11 (Compat-Harness) — поперёк всех (тестирует F2/F4/F8)
```

## Known Stubs / Future Work

Реализации, явно отмеченные как **заглушки** или незавершённые в `PARITY.md` и `ROADMAP.md`:

| Артефакт | Статус | Комментарий |
|---|---|---|
| `AskUserQuestion` interactive tool | Stub — возвращает заглушку вместо реального UI | Нет real interactive prompt; ожидает реализации в F9/F10 (TUI/ACP-канал) |
| `RemoteTrigger` | Stub | Полная реализация требует clawhip-интеграции (out-of-repo) |
| Deep bash validation (18 submodules в Python) | 1 из 18 портирован | Остальные в отдельной ветке; не блокируют main |
| "Полный жизненный цикл MCP за пределами реестра" | Незавершён | F8 покрывает базовый lifecycle; advanced scenarios — TODO |
| Schema versioning for structured reports | Частично | F7 закладывает фундамент; полная миграционная стратегия — следующая итерация |
| P2 ROADMAP gaps | Не реализованы | Approval-token replay protection, cross-claw delivery transparency, token-risk aware guidance, workspace-scope weight preflight |

## Out-of-Repo Dependencies (экосистема UltraWorkers)

Эти компоненты **не входят** в `claw-code`, но `claw-code` спроектирован для интеграции с ними:

| Компонент | Роль | Контракт с claw-code |
|---|---|---|
| **OmX** | Конвертирует human-директивы в structured execution protocols | Принимает task packets из F8 TaskRegistry; эмитит lane events для F7 |
| **clawhip** | Маршрутизирует события и уведомления вне agent context window | Consumer событий F7 (HTTP webhook или Unix socket); audience=clawhip projection |
| **OmO** | Multi-agent coordination и conflict resolution | Использует TeamRegistry (F8) и Cron (F8); координирует claws через clawhip |
| **Jobdori** | Бизнес/HR-side dashboard | Consumer F7 событий с audience=jobdori projection (только бизнес-метрики, redacted technical) |
| **Discord-first interface** | Async chat-based direction (по PHILOSOPHY) | Реализуется поверх clawhip; не в claw-code |
| **Zed Editor (ACP-client)** | IDE-frontend | Подключается через F10 `claw acp` JSON-RPC stdio |

## Дополнительные артефакты репозитория (контекст, не отдельные фичи)

| Артефакт | Где упомянут | Описание |
|---|---|---|
| `Containerfile` | F3 (sandbox), упоминание в README spec | Docker/Podman-образ для воспроизводимого build/run |
| `install.sh` | README spec | Bootstrap-скрипт (cargo build + symlink) |
| `.claude.json` vs `.claw.json` | F5 (config hierarchy) | Двойственность: `.claude.json` — наследие/совместимость; `.claw.json` — канонический; runtime читает оба, `.claw.json` приоритетнее |
| `.clawd-todos.json` | rust/ корень | Локальный todo-tracker `clawd` (worker-side) — не пользовательский, internal state |
| `.omc/plans/` | F1 UC-2.2 (`/ultraplan`) | Хранилище планов, генерируемых через extended-reasoning; consumed by OmX |
| Python `src/` + `tests/` (3.1%) | Out of Rust scope | Reference-код и audit-helpers; используются для cross-checking, но не часть production binary |

---
*Источники: README.md, USAGE.md, PARITY.md, ROADMAP.md, PHILOSOPHY.md, prd.json, CLAUDE.md, TUI-ENHANCEMENT-PLAN.md, MOCK_PARITY_HARNESS.md, Cargo.toml крейтов репозитория ultraworkers/claw-code на состояние 2026-05-02.*
