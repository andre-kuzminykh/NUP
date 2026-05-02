# SPEC — Feature 3: Worker Lifecycle & Diagnostics

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Worker Lifecycle & Diagnostics |
| **Description (Goal / Scope)** | Явная state-machine жизненного цикла worker'а (`spawning → trust_required → ready_for_prompt → running → finished/failed`) и набор diagnostic-команд (`doctor`, `status`, `state`, `sandbox`, `version`), эмитирующих типизированные события вместо парсинга логов. Включает: эмиссию `.claw/worker-state.json`, preflight-проверки до запуска, классификатор failure-таксономии, типизированный envelope ошибок, blocked sub-phases (trust_prompt, prompt_delivery, MCP handshake). Решает проблему "phantom completion" через per-worktree isolation. Вне скоупа: recovery-recipes (F6), event schema для clawhip (F7). |
| **Client** | Оркестраторы (clawhip, OmO), CI-системы, claws (other agents); пользователи через `claw doctor`. |
| **Problem** | Без явных lifecycle states оркестратор должен парсить prose в логах, чтобы понять состояние worker'а — это хрупко и приводит к ложным "completed", когда worker фактически висит на trust prompt. Без preflight diagnostics стартап-failure обнаруживается уже после потраченного времени модели. |
| **Solution** | (1) State-machine с типизированным enum `WorkerState`; (2) Файл `.claw/worker-state.json`, обновляемый атомарно при каждом transition; (3) Подфазы для `blocked` (trust_prompt, prompt_delivery, MCP handshake, …); (4) Preflight diagnostics перед запуском (auth, контекст-окно, конфиг merge, trust-allowlist) с эмиссией `worker.startup_no_evidence` при тайм-ауте; (5) Команды `doctor`/`status`/`state`/`sandbox` с `--output-format json`; (6) Per-worktree isolation сессий — устраняет phantom completion. |
| **Metrics** | (1) Detection-rate ложного "completed" → 0% после внедрения per-worktree isolation; (2) Preflight отлавливает ≥ 90% старт-фейлов до запуска модели; (3) Failure classifier покрывает ≥ 6 категорий ошибок с machine-readable code; (4) `claw doctor` выполняется ≤ 1 секунды. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Оркестратор (clawhip / OmO) |
| **User Story ID** | US-1 |
| **User Story** | Как оркестратор, я хочу читать состояние worker'а из `.claw/worker-state.json` и получать типизированные события lifecycle, чтобы не парсить prose в логах и точно знать, готов ли worker принять prompt. |
| **UX / User Flow** | Worker запускается → пишет `state=spawning` в `worker-state.json` → проходит preflight → если требуется trust → `state=trust_required` (sub-phase `trust_prompt`); после resolve → `ready_for_prompt`; после ввода → `running`; после завершения → `finished` или `failed` с typed-error envelope. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Свежий worker запускается в репозитории, который НЕ в `trusted_roots`. Trust prompt появится. |
| **When** | Оркестратор стартует `claw` в worker-режиме и читает `.claw/worker-state.json`. |
| **Then** | (1) В первые ≤ 100 мс файл создан со state `spawning`; (2) После preflight state переходит в `trust_required` с `sub_phase: "trust_prompt"`; (3) Поле `evidence` содержит timestamp и pane-snapshot; (4) После resolve trust state становится `ready_for_prompt`; (5) Каждый transition атомарно перезаписывает файл (temp + rename). |
| **Input** | Запуск worker'а в untrusted репо |
| **Output** | Серия snapshot'ов файла; типизированные events `worker.state_changed { from, to, sub_phase, ts }` |
| **State** | `.claw/worker-state.json` отражает текущий state с monotonically-возрастающим `revision` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | `WorkerState` enum: `spawning`, `trust_required`, `ready_for_prompt`, `running`, `finished`, `failed`. Дополнительно `blocked` с обязательным `sub_phase`. |
| FR-2 | Файл `.claw/worker-state.json` имеет схему: `{ revision: u64, state, sub_phase?: String, evidence: { ts, pane_snapshot?, …}, error?: TypedErrorEnvelope, last_transition_ts }`. |
| FR-3 | Каждая запись файла атомарна (temp + rename); читатель не должен увидеть полузаписанное состояние. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Latency между фактическим transition и обновлением файла ≤ 50 мс. |
| NFR-2 | Файл валидируется JSON-Schema (под versioning); читатели могут безопасно игнорировать неизвестные поля (forward-compat). |

#### Use Case BDD 2

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Worker запускается, но из-за proxy-misconfig API-запросы зависают; первый prompt не обрабатывается за SLA. |
| **When** | Истекает SLA на acceptance первого prompt'а (например 30 секунд). |
| **Then** | (1) Эмитится событие `worker.startup_no_evidence` (US-001 PRD) с пакетом доказательств: `{ lifecycle_state, pane_command, ts, trust_prompt_detection_result, last_api_call_ts, network_check_result }`; (2) State worker'а переходит в `failed` с `error.errno = "startup.no_evidence"`. |
| **Input** | SLA timeout 30 с, prompt не получил response |
| **Output** | Событие `worker.startup_no_evidence` с full evidence packet; `worker-state.json` в `failed`. |
| **State** | Failure classifier помечает as `category: prompt_misdelivery` или `network` (по пакету доказательств). |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | SLA на первый prompt acceptance конфигурируется (default 30 с); по истечении эмитится `worker.startup_no_evidence`. |
| FR-5 | Failure classifier различает 6 категорий: `trust_required`, `prompt_misdelivery`, `network`, `auth_missing`, `mcp_handshake_failed`, `unknown`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | Evidence packet не должен содержать секретов (api keys, OAuth tokens) — redaction обязателен. |
| NFR-4 | Размер evidence packet ≤ 8 КБ (JSON). |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Разработчик / агент |
| **User Story ID** | US-2 |
| **User Story** | Как пользователь, я хочу запускать `claw doctor`, чтобы за один проход получить отчёт о здоровье установки (бинарь, конфиг, credentials, сеть, MCP, LSP) с человеко- и машинно-читаемым выводом. |
| **UX / User Flow** | `claw doctor` → запускаются preflight checks (build info, конфиг merge, credentials, ping endpoint провайдера, MCP discovery, LSP discovery) → таблица с `OK/WARN/FAIL` и hints. С флагом `--output-format json` — структурированный JSON для CI. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | У пользователя установлен `claw`, заданы все необходимые env vars, доступна сеть. |
| **When** | Пользователь запускает `claw doctor`. |
| **Then** | (1) Выполняется ≥ 6 проверок: build info, конфиг-merge валидация, credentials per provider, network reachability (HEAD к API), MCP discovery, LSP discovery, trusted_roots; (2) Результат — таблица с символами ✓/⚠/✗ и hint-сообщениями; (3) Exit code `0` если все checks прошли (warnings допустимы), `1` если есть FAIL. |
| **Input** | `argv = ["claw", "doctor"]` |
| **Output** | TTY-таблица с результатами; либо JSON при `--output-format json` |
| **State** | Отчёт пишется в `.claw/last-doctor-report.json` для последующего анализа |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | `doctor` выполняет проверки: (a) build/version, (b) config merge validation (US-013 PRD), (c) credentials per provider (US-009 ROADMAP), (d) network ping endpoints, (e) MCP server discovery + handshake, (f) LSP discovery, (g) trusted_roots resolution. |
| FR-7 | Каждая проверка возвращает `CheckResult { name, status: ok/warn/fail, message, hint?, duration_ms }`. |
| FR-8 | `--output-format json` сериализует все результаты в массив `CheckResult` под schema-version. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-5 | Полный прогон `doctor` ≤ 1 секунды (offline checks ≤ 100 мс, network checks параллельно с timeout 500 мс). |
| NFR-6 | Каждая network-проверка имеет timeout; даже при недоступности всех провайдеров команда возвращает результат, не зависает. |

#### Use Case BDD 2 (Edge: status & state diagnostic)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | В директории есть запущенный worker с `worker-state.json` в state `running`. |
| **When** | Пользователь запускает `claw status` и `claw state`. |
| **Then** | (1) `claw status` агрегирует: текущий state из файла, ID сессии, model, permission-mode, число turns, активные tools, расход токенов; (2) `claw state` просто выводит содержимое `.claw/worker-state.json` (опционально `--output-format json`); (3) Если файла нет → message "no active worker". |
| **Input** | `argv = ["claw", "status"]`, `argv = ["claw", "state"]`, `argv = ["claw", "state", "--output-format", "json"]` |
| **Output** | Таблица для `status`; raw JSON для `state` (или человекочитаемый wrap). |
| **State** | Файл `.claw/worker-state.json` не модифицируется (read-only). |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | `status` объединяет данные из `worker-state.json` и `.claw/sessions/<active>/meta.json`. |
| FR-10 | `state` поддерживает `--output-format json` и `--watch` (стримит изменения файла через inotify/FSEvents). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-7 | `state --watch` корректно работает на Linux (inotify), macOS (FSEvents), Windows (ReadDirectoryChangesW). |
| NFR-8 | При отсутствии активного worker'а — exit code `0` с сообщением (это не ошибка). |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Разработчик / claw |
| **User Story ID** | US-3 |
| **User Story** | Как разработчик, я хочу запускать `claw sandbox` для изолированной проверки тяжёлых операций (запуска tools, рискованных команд) и `claw version` для определения точной build-info, чтобы воспроизводимо отлаживать проблемы. |
| **UX / User Flow** | `claw sandbox --tool bash --cmd "ls"` → выполняется в sandbox-режиме (отдельная HOME, ограниченные permissions); `claw version` → печатает версию + git-commit + targets + поддерживаемые providers. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Пользователь хочет проверить, как именно работает Bash-tool без задействования модели. |
| **When** | Запускается `claw sandbox --tool bash --cmd "ls /"`. |
| **Then** | (1) Создаётся изолированная среда (отдельный `HOME=.sandbox-home`, без сетевого доступа по умолчанию); (2) Tool запускается с теми же permission-проверками, что и в production (F4); (3) Результат tool'а печатается в stdout; (4) Все side-effects логируются в `.claw/sandbox-runs/<id>.json`. |
| **Input** | `--tool bash --cmd "ls /"` |
| **Output** | Stdout/stderr команды + JSON-отчёт с metadata запуска |
| **State** | `.claw/sandbox-runs/<id>.json` создан; рабочая директория не модифицирована |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | `sandbox` поддерживает все встроенные tools (F4): bash, read_file, write_file, grep, glob, edit. |
| FR-12 | `version` выводит: `claw vX.Y.Z`, git commit hash, build target (triple), список зарегистрированных providers, список loaded MCP servers (с фактическими версиями). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-9 | Sandbox-runs не должны влиять на основной worker-state (изолированный `worker-state.json` в `.sandbox-home`). |
| NFR-10 | `version` поддерживает `--output-format json` для CI-интеграций. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Subcommands CLI (`doctor`/`status`/`state`/`sandbox`/`version`); файл-watcher (`state --watch`) |
| **User Entry Points** | `claw doctor [--output-format json]`, `claw status`, `claw state [--watch] [--output-format json]`, `claw sandbox --tool <name>`, `claw version` |
| **Main Screens / Commands** | Таблицы checks, JSON-структуры; интеграция с oркестраторами через файл `worker-state.json` |
| **Input / Output Format** | Input: argv. Output: text-table или JSON; events для оркестратора через файл; Schema-versioned. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `runtime::worker_state` + `commands::diagnostics` (часть `runtime` и `commands` крейтов) |
| **Responsibility** | (1) State-machine + атомарная запись `worker-state.json`; (2) Preflight orchestrator; (3) Failure classifier; (4) Diagnostic commands (doctor/status/state/sandbox/version) |
| **Business Logic** | Transition-функция: `transition(current, next, evidence) -> Result<()>`. Для запрещённых переходов (например `finished -> running`) → паника или typed-error в зависимости от mode. Preflight-orchestrator запускает чек-листы параллельно с timeout. |
| **API / Contract** | `pub fn current_state() -> WorkerStateSnapshot`; `pub fn transition(...)`; `pub fn doctor() -> DoctorReport`; `pub fn status() -> StatusReport`; `pub fn watch_state() -> impl Stream<Item=WorkerStateSnapshot>` |
| **Request Schema** | Для `state --watch` нет request, лишь stream подписки |
| **Response Schema** | `WorkerStateSnapshot { revision, state, sub_phase?, evidence, error?, last_transition_ts, schema_version }`; `DoctorReport { schema_version, checks: Vec<CheckResult>, summary }` |
| **Error Handling** | Typed envelope `{ operation, target, errno, hint, retryable }`. Для preflight: накапливаются все warnings/fails в массив; команда не падает на первой ошибке. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `WorkerState` (enum), `WorkerStateSnapshot`, `EvidencePacket`, `FailureCategory`, `CheckResult`, `DoctorReport`, `StatusReport`, `SandboxRun` |
| **Relationships (ER)** | `WorkerStateSnapshot` 1—1 `WorkerState`; `WorkerStateSnapshot` 0—1 `EvidencePacket`; `WorkerStateSnapshot` 0—1 `TypedErrorEnvelope`; `DoctorReport` 1—N `CheckResult` |
| **Data Flow (DFD)** | Worker startup → `transition(spawning, evidence)` → `write(worker-state.json)` → preflight checks → `transition(...)` → … → `transition(finished, evidence)`. `claw state --watch` → подписка на FS-события → emit snapshot. |
| **Input Sources** | Lifecycle events (внутренние из `runtime`), preflight checks (config, network, auth, MCP, LSP), pane snapshots от tmux-обёртки (если используется) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Файловая система с поддержкой atomic rename (любой современный POSIX FS, NTFS) |
| FS-watcher API: inotify (Linux), FSEvents (macOS), ReadDirectoryChangesW (Windows) |
| Опционально: tmux/screen для pane snapshots |
| Сеть для doctor network checks (с timeout) |
| Диск: `.claw/worker-state.json` (≤ 16 КБ), `.claw/sandbox-runs/` (растёт с использованием), `.claw/last-doctor-report.json` |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | State-machine + атомарная запись `worker-state.json` | crate `runtime` | Все 6+ states покрыты unit-тестами; форсированный crash при transitions не оставляет corrupt-файл | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Preflight orchestrator + emission `worker.startup_no_evidence` + failure classifier | T-1, F2, F8 | Preflight ловит ≥ 90% старт-фейлов; классификатор различает 6 категорий | ST-4, ST-5 |
| UC-2.1 | T-3 | Команда `doctor` со всеми проверками + JSON output | T-1, T-2, F2, F8 | `claw doctor` ≤ 1 с; покрытие integration-тестами | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Команды `status` и `state` (включая `--watch`) | T-1, F5 | `state --watch` работает на 3 OS; `status` агрегирует session+worker | ST-9, ST-10 |
| UC-3.1 | T-5 | Команды `sandbox` и `version` | T-1, F4 | `sandbox` запускает любой built-in tool изолированно; `version` печатает полную build-info | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать enum `WorkerState`, struct `WorkerStateSnapshot` с schema-version, атомарную запись/чтение `worker-state.json`, transition-функцию с валидацией legal transitions. |
| **Dependencies** | crate `runtime` |
| **DoD** | (1) Unit-тесты на legal/illegal transitions; (2) Тест на race conditions (concurrent writers — мьютекс или single-writer policy); (3) Crash-test: kill -9 во время записи не оставляет повреждённый файл. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | enum `WorkerState` + struct `WorkerStateSnapshot` + JSON-Schema файла | — | Сериализация/десериализация round-trip; backward-compat загрузка предыдущей версии |
| ST-2 | Атомарная запись (temp + rename) + чтение с проверкой revision | ST-1 | Concurrent reader не видит partial write; revision строго возрастает |
| ST-3 | Transition-функция с валидацией; запрещённые transitions возвращают typed-error | ST-1 | Все 6 states покрыты unit-тестами; matrix legal transitions |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Preflight orchestrator: параллельный запуск checks (auth, контекст-окно, конфиг merge, MCP handshake, trust resolution); SLA-таймер на acceptance первого prompt'а; emission `worker.startup_no_evidence`; failure classifier. |
| **Dependencies** | T-1, F2 (auth/network), F8 (MCP) |
| **DoD** | (1) Preflight ловит ≥ 90% классов старт-фейлов на тестовом наборе; (2) Failure classifier различает 6 категорий; (3) Evidence packet ≤ 8 КБ, без секретов. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Preflight orchestrator: параллельные checks с общим timeout, агрегация результатов | T-1 | Все checks запускаются параллельно; общий timeout ≤ 5 с |
| ST-5 | Failure classifier + evidence packet builder + redaction секретов | T-1 | 6 категорий покрыты тестами; integration-тест на каждый класс |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Команда `claw doctor`: запуск всех diagnostic checks, рендер таблицы, `--output-format json`, запись отчёта в `.claw/last-doctor-report.json`. |
| **Dependencies** | T-1, T-2, F2 (credentials, network), F8 (MCP/LSP discovery) |
| **DoD** | `claw doctor` ≤ 1 с; покрытие integration-тестами для каждого check; documented exit codes. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Реестр checks: build/version, config merge, credentials, network, MCP, LSP, trusted_roots | T-2, F2, F8 | Каждый check имеет unit-тест с моком зависимостей |
| ST-7 | Renderer таблицы и JSON; schema versioning отчёта | ST-6 | Snapshot-тесты на оба формата |
| ST-8 | Запись `last-doctor-report.json` атомарно; интеграционный smoke-test полного прогона | ST-6, ST-7 | Файл создаётся; формат валиден; `claw doctor --output-format json | jq .summary` работает |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Команды `claw status` и `claw state` (включая `--watch`); агрегация worker+session info; кроссплатформенный FS-watcher. |
| **Dependencies** | T-1, F5 (sessions) |
| **DoD** | `state --watch` стримит обновления на 3 OS; `status` корректно показывает все поля; integration-тесты на агрегацию. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | `status` — агрегация worker-state + session meta + cost/usage + tools | T-1, F5 | Snapshot-тест на полный output |
| ST-10 | `state` + `--watch` через notify-rs или эквивалент (cross-platform) | T-1 | Тест: внешний writer обновляет файл → подписчик получает событие за ≤ 200 мс на каждой OS |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | (1) Команда `sandbox` — изолированный запуск любого built-in tool с собственным `HOME=.sandbox-home`; (2) Команда `version` — полный build-info JSON/text. |
| **Dependencies** | T-1, F4 (tools) |
| **DoD** | `sandbox` запускает все 5+ tools; `version` содержит git-commit + список providers/MCP. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `sandbox` — изоляция HOME + permission-аудит + запись `.claw/sandbox-runs/<id>.json` | F4 | Sandbox-run не модифицирует репо; отчёт валиден |
| ST-12 | `version`: git commit (через `vergen` build-script), provider list, MCP versions, `--output-format json` | F2, F8 | Снапшот-тест на text-output; JSON под schema |
