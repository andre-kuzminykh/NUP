# SPEC — Feature 1: CLI Core & Interactive REPL

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | CLI Core & Interactive REPL |
| **Description (Goal / Scope)** | Единая точка входа в Claw — исполняемый файл `claw`/`claw.exe`, поддерживающий три режима запуска (интерактивный REPL, one-shot prompt, shorthand), а также набор slash-команд для управления сессией, инициализации репозитория и работы с агентами. В скоупе: парсер CLI-аргументов, dispatcher slash-команд, REPL-loop, команда `init`, генерация help. Вне скоупа: маршрутизация моделей (F2), tools (F4), сессии (F5). |
| **Client** | Разработчики, использующие CLI напрямую; AI-агенты (claws), вызывающие `claw` через subprocess; CI/CD-пайплайны. |
| **Problem** | Без единого CLI-фронтенда у пользователя нет понятного способа запустить агента в нужном режиме — интерактивно для исследовательской работы или в one-shot для автоматизации. Без slash-команд невозможно on-the-fly менять модель/permissions/конфиг внутри сессии без перезапуска. |
| **Solution** | Бинарь `claw` парсит arguments через `clap`-подобный фреймворк, определяет режим (REPL / one-shot / shorthand / resume), запускает `ConversationRuntime` из крейта `runtime`. Slash-команды зарегистрированы в `commands` crate, dispatcher маршрутизирует ввод вида `/<name> <args>` на handler-функцию. Команда `init` генерирует `.claw/`, `.claw.json`, обновляет `.gitignore` и создаёт `CLAUDE.md`. |
| **Metrics** | (1) Время от запуска `claw` до первого готового prompt'а ≤ 800 мс на локальной машине; (2) ≥ 95% slash-команд из списка работают без падений в интеграционных тестах; (3) `claw --help` и `claw <verb> --help` генерируют help-текст для 100% подкоманд; (4) все три режима запуска покрыты integration-тестами. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Разработчик / AI-агент |
| **User Story ID** | US-1 |
| **User Story** | Как пользователь Claw, я хочу запускать агент в интерактивном REPL или одной командой (one-shot), чтобы выбирать между исследовательской работой и автоматизацией без переключения инструментов. |
| **UX / User Flow** | (1) `claw` без аргументов → REPL приглашение; ввод текста → ответ модели; `Ctrl+D` или `/exit` → выход. (2) `claw prompt "say hello"` или shorthand `claw "say hello"` → один turn → JSON или текст в stdout → exit code 0/1. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Пользователь установил `claw` (`cargo build --workspace`), бинарь доступен в `PATH`, переменная `ANTHROPIC_API_KEY` установлена, текущая директория — git-репозиторий. |
| **When** | Пользователь запускает `claw` без аргументов в терминале. |
| **Then** | (1) Запускается `ConversationRuntime` в режиме REPL; (2) на экране отображается приветствие (worker title, model alias, permission-mode); (3) появляется prompt-строка ожидания ввода; (4) ввод текста отправляется как user turn; (5) ответ модели стримится (SSE) на экран; (6) `/exit` или `Ctrl+D` корректно завершает loop с сохранением сессии. |
| **Input** | `argv = ["claw"]`, env: `ANTHROPIC_API_KEY=sk-ant-...`, cwd: `/path/to/repo` |
| **Output** | TTY-вывод REPL: header → prompt → stream ответа → prompt → … |
| **State** | Создана новая сессия в `.claw/sessions/<session-id>/`, файл `.claw/worker-state.json` обновлён в `running` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | Бинарь `claw` без аргументов запускает интерактивный REPL с использованием `ConversationRuntime::interactive()`. |
| FR-2 | REPL поддерживает редактирование строки (history, стрелки вверх/вниз) через библиотеку line-editor (например `rustyline` или эквивалент). |
| FR-3 | Стриминг ответа реализуется через SSE-поток крейта `api`, отрисовка построчно с возможностью прерывания (`Ctrl+C`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Время старта REPL до отрисовки приветствия ≤ 800 мс на dev-машине без cold-cache моделей. |
| NFR-2 | Прерывание `Ctrl+C` посередине стрима отменяет текущий turn, но не завершает процесс — пользователь возвращается в prompt. |
| NFR-3 | REPL корректно работает в Windows PowerShell, Git Bash и WSL без визуальных артефактов в ANSI. |

#### Use Case BDD 2

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Бинарь `claw` доступен, `ANTHROPIC_API_KEY` установлен, скрипт CI запускает one-shot. |
| **When** | Выполняется `claw prompt "explain README"` или shorthand `claw "explain README"`. |
| **Then** | (1) `ConversationRuntime` запускается в one-shot режиме; (2) prompt отправляется как один user turn; (3) ответ стримится в stdout (по умолчанию text), либо в JSON если указан `--output-format json`; (4) процесс завершается с кодом `0` при успехе, `1` при ошибке провайдера, `2` при ошибке валидации аргументов. |
| **Input** | `argv = ["claw", "prompt", "explain README"]` или `argv = ["claw", "explain README"]` |
| **Output** | stdout: текст или JSON ответа модели; stderr: warnings, retry messages |
| **State** | Создана сессия с одним turn в `.claw/sessions/`; `worker-state.json` финализирован в `finished` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | Парсер аргументов различает явный verb (`prompt`, `init`, `doctor`, …) и shorthand (первый позиционный аргумент трактуется как prompt, если он не совпадает с известным verb). |
| FR-5 | One-shot режим завершает процесс после первого assistant turn без ожидания следующего ввода. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-4 | One-shot exit code соответствует POSIX-конвенции: `0` — успех, `1–2` — ошибка пользователя/провайдера, `> 2` зарезервировано. |
| NFR-5 | При запуске в non-TTY (pipe) стриминг выводится без ANSI-кодов и без line-editor инициализации. |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Разработчик внутри REPL |
| **User Story ID** | US-2 |
| **User Story** | Как пользователь REPL, я хочу выполнять slash-команды (`/help`, `/status`, `/cost`, `/config`, `/model`, `/permissions`, `/export`, `/ultraplan`, `/teleport`, `/bughunter`), чтобы on-the-fly менять состояние сессии без перезапуска агента. |
| **UX / User Flow** | В строке REPL пользователь вводит `/<имя> [args]`. Dispatcher распознаёт команду, выполняет handler, печатает результат в pane. Неизвестная команда → ошибка с подсказкой `/help`. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | REPL запущен, активная сессия существует, текущий model alias — `sonnet`, permission-mode — `workspace-write`. |
| **When** | Пользователь вводит `/model opus`, затем `/status`, затем `/cost`. |
| **Then** | (1) `/model opus` → переключение на `claude-opus-4-6`, отображение confirm-сообщения; (2) `/status` → выводит worker state, текущую модель, permission-mode, ID сессии, число turns; (3) `/cost` → агрегированный расчёт токенов и цены за сессию (input + output по тарифу выбранной модели). |
| **Input** | Последовательно: `/model opus\n`, `/status\n`, `/cost\n` |
| **Output** | Для `/model`: `✓ model switched: opus (claude-opus-4-6)`. Для `/status`: таблица полей. Для `/cost`: суммарная стоимость в USD с разбивкой. |
| **State** | `runtime.config.model_alias = "opus"`, в сессионном `meta.json` записан model_change event |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | Реестр slash-команд (`commands` crate) предоставляет API регистрации: `register(name, help, handler_fn)`. |
| FR-7 | `/model <alias>` валидирует alias через резолвер Feature 2; при unknown alias возвращает ошибку без изменения state. |
| FR-8 | `/cost` агрегирует usage events из `telemetry` crate (input_tokens, output_tokens, cached_tokens) и применяет тариф provider'а. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-6 | Slash-команда не должна блокировать REPL дольше 200 мс для команд без сетевых вызовов (`/help`, `/status`, `/model`). |
| NFR-7 | Help-текст каждой команды читаемый из единого source of truth (используется и для `/help`, и для документации). |

#### Use Case BDD 2

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 (UC-2.2 в скоупе фичи) |
| **Use Case ID** | UC-2.2 |
| **Given** | REPL открыт, пользователь хочет получить план для сложной задачи. |
| **When** | Пользователь вводит `/ultraplan Refactor auth module to use OAuth2`. |
| **Then** | (1) Команда инициирует extended-reasoning turn с system-prompt'ом, ориентированным на декомпозицию; (2) Ответ модели возвращает структурированный план (шаги, зависимости, acceptance criteria); (3) План сохраняется в `.omc/plans/<plan-id>.json` и отображается в pane. |
| **Input** | `/ultraplan Refactor auth module to use OAuth2` |
| **Output** | Вывод JSON-плана (или markdown-таблицы) + лог `plan saved to .omc/plans/<id>.json` |
| **State** | Файл `.omc/plans/<id>.json` создан; событие `plan.created` отправлено в telemetry. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | `/ultraplan <task>` использует extended-reasoning через `api` crate (parameter `thinking: { type: "enabled", budget_tokens: ... }`). |
| FR-10 | Структура плана: `{ id, title, steps: [{ id, description, deps, acceptance }], created_at }`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-8 | План валидируется JSON-Schema перед сохранением; невалидный ответ → retry до 2 раз. |
| NFR-9 | Размер плана ограничен 100 шагами; превышение → возвращается `error.plan.too_large`. |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Разработчик / агент |
| **User Story ID** | US-3 |
| **User Story** | Как пользователь, я хочу инициализировать репозиторий командой `claw init`, чтобы получить готовую конфигурацию (`.claw/`, `.claw.json`, `CLAUDE.md`, обновлённый `.gitignore`) одной командой. |
| **UX / User Flow** | В пустом или существующем git-репо: `claw init` → опросник по дефолтным настройкам (interactive) или `--non-interactive` для CI → создаются файлы → печатается summary. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Текущая директория — git-репозиторий без `.claw/`. |
| **When** | Пользователь запускает `claw init` (interactive) или `claw init --non-interactive --model sonnet --permission-mode workspace-write`. |
| **Then** | (1) Создаётся директория `.claw/` с подпапкой `sessions/`; (2) Создаётся `.claw.json` с указанными model и permission-mode; (3) В `.gitignore` добавляются строки `.claw/sessions/`, `.claw/worker-state.json`, `.claw/settings.local.json`; (4) Создаётся (или обновляется) `CLAUDE.md` с дефолтным шаблоном; (5) Печатается итоговый summary с путями созданных файлов. |
| **Input** | `argv = ["claw", "init", "--non-interactive", "--model", "sonnet", "--permission-mode", "workspace-write"]` |
| **Output** | stdout: список созданных/изменённых файлов; exit code `0`. |
| **State** | Появились файлы: `.claw/`, `.claw/sessions/`, `.claw.json`, `CLAUDE.md`; `.gitignore` обновлён (без дублей строк, идемпотентно). |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | Команда `init` идемпотентна: повторный запуск не дублирует строки в `.gitignore` и не перезатирает существующий `CLAUDE.md` без явного `--force`. |
| FR-12 | Шаблон `CLAUDE.md` берётся из embedded-ресурса бинаря (через `include_str!`), чтобы не зависеть от внешних файлов. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-10 | Команда `init` работает корректно вне git-репозитория, но печатает warning о невозможности корректно настроить `.gitignore`. |
| NFR-11 | Все создаваемые файлы пишутся атомарно (temp file + rename), чтобы не оставлять полузаписанных артефактов при сбое. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | CLI бинарь `claw` / `claw.exe` (TTY и non-TTY режимы) |
| **User Entry Points** | (1) `claw` — REPL; (2) `claw <prompt>` — shorthand; (3) `claw prompt <text>` — explicit one-shot; (4) `claw init` — bootstrap; (5) `claw --resume latest` — resume |
| **Main Screens / Commands** | REPL pane с приглашением, system messages, stream output. Slash-команды: `/help /status /cost /config /session /model /permissions /export /ultraplan /teleport /bughunter`. Subcommands: `prompt`, `init`, `doctor`, `status`, `state`, `sandbox`, `version`, `agents`, `mcp`, `skills`, `system-prompt`, `acp` |
| **Input / Output Format** | Input: argv + stdin (для pipe-сценариев). Output: TTY с ANSI или JSON (`--output-format json` для diagnostic verbs); exit codes по POSIX. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `rusty-claude-cli` (binary) → `runtime::ConversationRuntime` |
| **Responsibility** | Парсинг CLI, выбор режима, инициализация runtime, REPL loop, dispatcher slash-команд, генерация help, команда `init`. |
| **Business Logic** | (1) `ArgParser` → `Mode` enum (Repl, OneShot{prompt}, Init{opts}, Verb{name, args}); (2) `Runtime::new(config)` → `Runtime::run(mode)`; (3) REPL loop: read line → if `/` → `commands::dispatch()` else → `runtime::send_user_turn()`. |
| **API / Contract** | `pub fn run(argv: Vec<String>) -> Result<ExitCode>` — единственная точка входа `main()` |
| **Request Schema** | argv (string array), env (HashMap<String,String>), stdin (для pipe) |
| **Response Schema** | stdout (text/JSON), stderr (warnings/errors), `ExitCode` (0/1/2/…) |
| **Error Handling** | Typed-error envelope: `{ operation, target, errno, hint, retryable }`. Невалидные args → exit 2 с usage. Сетевые ошибки → exit 1 с retry-hint. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `CliInvocation { argv, env, cwd, mode }`; `SlashCommand { name, help, handler }`; `InitOptions { model, permission_mode, force, non_interactive }` |
| **Relationships (ER)** | `CliInvocation` 1—1 `Mode`; `Mode::Repl` 1—N `SlashCommand`; `Mode::Init` 1—1 `InitOptions` |
| **Data Flow (DFD)** | `argv` → `parse()` → `Mode` → `Runtime::dispatch(Mode)` → (REPL: stdin → tokenize → if slash → `commands::dispatch` else `api::send`; OneShot: `api::send` → render → exit). |
| **Input Sources** | argv (process), env vars (process), config файлы (см. F5/Global), stdin (для prompt из pipe), TTY input (для REPL) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Host OS: macOS 12+, Linux glibc 2.31+, Windows 10+. Архитектуры: x86_64, aarch64. |
| Runtime: Rust toolchain (build); для пользователя — лишь скомпилированный бинарь. |
| TTY: цветной терминал с поддержкой ANSI (для REPL); fallback в plain text для non-TTY. |
| Сеть: исходящий HTTPS к провайдерам моделей (Feature 2). |
| Диск: ≥ 20 МБ под бинарь + размер сессий (зависит от использования, F5). |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Реализовать REPL-режим с line-editor и стримингом | crates `runtime`, `api` | REPL запускается, команды выполняются, `Ctrl+C` отменяет turn, сессия сохраняется | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Реализовать one-shot и shorthand-режимы | T-1 | `claw prompt "..."` и `claw "..."` возвращают ответ + корректный exit code | ST-4, ST-5 |
| UC-2.1 | T-3 | Реестр slash-команд + базовые команды (`/help /status /cost /model`) | T-1 | Все базовые slash-команды выполняются, `/help` генерируется автоматически | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Команды `/ultraplan`, `/teleport`, `/bughunter`, `/permissions`, `/export`, `/session`, `/config` | T-3, F2 | Все extended slash-команды покрыты integration-тестами | ST-9, ST-10 |
| UC-3.1 | T-5 | Команда `init` — генерация `.claw/`, `.claw.json`, `CLAUDE.md`, `.gitignore` | — | `claw init` идемпотентен, шаблоны embedded, проходит integration-тесты | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать REPL-режим: парсер argv → mode REPL → ConversationRuntime → loop с line-editor, стримингом ответов и обработкой `Ctrl+C`/`/exit`. |
| **Dependencies** | crates `runtime` (ConversationRuntime API), `api` (SSE streaming) |
| **DoD** | REPL запускается за ≤ 800 мс, поддерживает редактирование строки, стрим отображается, `Ctrl+C` отменяет turn без завершения, `Ctrl+D` и `/exit` корректно завершают сессию. Покрытие integration-тестами в `tests/repl_smoke.rs`. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Интегрировать line-editor (rustyline или эквивалент) с history-файлом `~/.claw/history` | — | Стрелки вверх/вниз листают историю; история персистентна между запусками |
| ST-2 | Реализовать рендер SSE-стрима в TTY с поддержкой прерывания | crate `api` | Стрим печатается построчно; `Ctrl+C` останавливает рендер и не завершает процесс |
| ST-3 | Обработка `/exit` и `Ctrl+D` с сохранением сессии и обновлением `worker-state.json` | crate `runtime` | После `/exit` файл сессии существует и валиден; `worker-state.json` в состоянии `finished` |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализовать one-shot режим (`claw prompt "..."`) и shorthand (`claw "..."`); поддержать `--output-format json`; вернуть POSIX-совместимые exit codes. |
| **Dependencies** | T-1 (общая инициализация runtime) |
| **DoD** | `claw "hello"` и `claw prompt "hello"` возвращают одинаковый ответ; в pipe (`claw "..." | jq`) формат корректен; exit codes документированы и покрыты тестами. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Парсер: распознавание shorthand (если первый позиционный аргумент не известен как verb — это prompt) | — | Все 4 verbs (`prompt`, `init`, `doctor`, …) и shorthand покрыты unit-тестами; ambiguity отсутствует |
| ST-5 | Маппинг ошибок API/runtime → exit code; JSON-output для prompt с `--output-format json` | crate `api` | Документированы exit codes 0/1/2; JSON прошёл валидацию схемой |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Реализовать реестр slash-команд (`commands` crate) и базовые команды `/help`, `/status`, `/cost`, `/model`, `/exit`. |
| **Dependencies** | T-1, crate `runtime`, crate `telemetry` (для `/cost`) |
| **DoD** | Команды доступны в REPL и one-shot resume режимах; `/help` генерируется автоматически из реестра; `/cost` агрегирует usage из telemetry. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | API регистрации: `register(name, help, handler)`; lookup за O(1); кейс-инсенситивность для команд | — | Реестр покрыт unit-тестами; дубликаты регистрации возвращают ошибку |
| ST-7 | Команды `/help`, `/status`, `/model`, `/exit` с unified rendering | T-1 | Каждая команда имеет integration-тест; вывод `/help` содержит все зарегистрированные команды |
| ST-8 | Команда `/cost`: агрегация usage events, расчёт по тарифам провайдера | crate `telemetry`, F2 | `/cost` показывает корректную сумму на тестовой сессии с известными usage |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Реализовать extended slash-команды: `/ultraplan`, `/teleport`, `/bughunter`, `/permissions`, `/export`, `/session`, `/config`. |
| **Dependencies** | T-3, F2 (extended-reasoning), F4 (permissions), F5 (sessions) |
| **DoD** | Все 7 команд имеют integration-тесты; `/ultraplan` сохраняет план в `.omc/plans/`; `/teleport` принимает symbol/path; `/export` пишет JSON/markdown сессии. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | `/ultraplan <task>` — extended reasoning, JSON-Schema валидация, сохранение в `.omc/plans/<id>.json` | crate `api`, F2 | План валидный JSON, ≤ 100 шагов, файл создан атомарно |
| ST-10 | `/teleport <symbol|path>`, `/bughunter`, `/permissions`, `/export`, `/session`, `/config` | F4, F5 | Каждая команда имеет integration-тест; неверные args → user-friendly error |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Реализовать команду `init`: генерация `.claw/`, `.claw.json`, `CLAUDE.md`, обновление `.gitignore`. Интерактивный и `--non-interactive` режимы; идемпотентность. |
| **Dependencies** | — |
| **DoD** | Команда работает на пустом и существующем репо; повторный запуск не ломает файлы; шаблоны embedded; покрытие integration-тестами для obeих веток (interactive/non-interactive). |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Шаблоны (`CLAUDE.md`, `.claw.json`) embedded через `include_str!`; функция `render_template(model, permission_mode)` | — | Шаблоны компилируются в бинарь; рендер unit-tested |
| ST-12 | Идемпотентная запись `.gitignore` (no duplicate lines), атомарная запись файлов (temp + rename), флаг `--force` для перезаписи | — | Повторный `init` не меняет файлы; `--force` перезаписывает; integration-тест проверяет оба сценария |
