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

## Соответствие крейтов и фич

| Крейт | Покрывает фичи |
|---|---|
| `rusty-claude-cli` | F1, F3 |
| `runtime` | F1, F4, F5 |
| `commands` | F1 |
| `api` | F2 |
| `tools` | F4 |
| `telemetry` | F3, F7 |
| `plugins` | F8 |
| `mock-anthropic-service` | F2 (тестирование) |
| `compat-harness` | F2, F8 (parity) |

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
F1 (CLI Core)
  └─ F2 (Providers) ─┐
  └─ F4 (Tools) ─────┼─ F5 (Sessions)
                     │
F3 (Lifecycle) ──────┼─ F6 (Branch/Recovery)
                     │
F7 (Events) ─────────┴─ F8 (Plugins/MCP)
```

---
*Источники: README.md, USAGE.md, PARITY.md, ROADMAP.md, PHILOSOPHY.md, prd.json, CLAUDE.md репозитория ultraworkers/claw-code на состояние 2026-05-02.*
