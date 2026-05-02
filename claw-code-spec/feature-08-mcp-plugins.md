# SPEC — Feature 8: MCP & Plugin Lifecycle

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | MCP & Plugin Lifecycle |
| **Description (Goal / Scope)** | Phase 5 ROADMAP: first-class lifecycle contract для плагинов и MCP-серверов (Model Context Protocol). Включает: McpToolRegistry (мост между MCP-tools и встроенными tools), LspRegistry (диспетчеризация LSP-клиентов), TaskRegistry/TeamRegistry/CronRegistry (заменили stubs из Python), config validation, healthcheck, degraded mode (если один MCP-сервер failed — остальные работают), cleanup contract, partial-success reporting, plugin discovery isolation в тестах ($HOME). Вне скоупа: AskUserQuestion (по PARITY — заглушка), RemoteTrigger (заглушка). |
| **Client** | AI-агенты (используют MCP-tools как built-in); внутренние слои (`runtime` запускает discovery), оркестраторы (получают partial-success reports). |
| **Problem** | Без contract'а lifecycle plugin может зависнуть на старте, не очиститься при shutdown, или обвалить весь worker при single failure. Без partial-success reporting один плохой MCP-сервер из 5 ломает all-or-nothing старт. Без isolation плагины из глобального `$HOME` "просачиваются" в тесты, делая их не-detereministic. |
| **Solution** | (1) Trait `Plugin` с обязательными `validate_config`, `start`, `healthcheck`, `stop` и timeout'ами на каждый этап; (2) PluginManager собирает результаты по всем plugins → `StartupReport { healthy: [...], degraded: [...], failed: [...] }` (partial success); (3) Если plugin failed — его tools/resources помечаются недоступными, но остальные работают; (4) MCP wrapper реализует Plugin contract для MCP-серверов; LSP — для LSP-серверов; (5) Тесты используют изолированный `$HOME` (см. ROADMAP completed). |
| **Metrics** | (1) Один failed plugin не блокирует старт worker'а (≥ N-1 plugins работают); (2) Plugin start ≤ 5 секунд per plugin (timeout); (3) Cleanup при shutdown гарантированно вызывается (даже на panic) — verified тестами; (4) MCP discovery + handshake ≤ 2 секунды per server; (5) Тесты с изолированным $HOME — 0 cross-test leakage. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | AI-агент / разработчик |
| **User Story ID** | US-1 |
| **User Story** | Как агент, я хочу использовать tools, предоставленные MCP-серверами, как обычные built-in tools, чтобы расширять функционал без изменения core. |
| **UX / User Flow** | Пользователь конфигурирует MCP-серверы в `.claw/mcp.json` → при старте `claw` PluginManager запускает каждый сервер, делает handshake → получает list tools → регистрирует их в общем реестре через `McpToolRegistry` → агент видит их в системном prompt вместе с built-in. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | В `.claw/mcp.json` объявлены 2 MCP-сервера: `filesystem` (npx) и `postgres` (binary). У обоих валидные configs. |
| **When** | Пользователь запускает `claw` (worker startup). |
| **Then** | (1) PluginManager parses `mcp.json`; (2) Каждый сервер запускается параллельно (subprocess); (3) Handshake (initialize → list_tools) выполняется per server с timeout 2 с; (4) Tools регистрируются в `McpToolRegistry` под namespace (например `mcp__filesystem__read_file`); (5) System prompt модели включает их schemas; (6) Worker готов к prompt'у. |
| **Input** | `.claw/mcp.json` с двумя серверами |
| **Output** | Все MCP tools доступны агенту; `claw doctor` показывает их в OK |
| **State** | 2 child-процесса запущены; PluginManager отслеживает их PIDs |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | `Plugin` trait: `name() -> &str; validate_config(...) -> Result<()>; start(...) -> Result<RuntimeHandle>; healthcheck(handle) -> HealthStatus; stop(handle) -> Result<()>`. |
| FR-2 | `McpToolRegistry` регистрирует tools под namespace `mcp__<server-name>__<tool-name>`; конфликтов имён нет благодаря namespace. |
| FR-3 | MCP handshake реализован по протоколу: `initialize { protocolVersion, capabilities }` → `tools/list` → tools cached в registry. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Параллельный startup всех plugins (rayon/tokio); общее время старта ≤ max(per_plugin_timeout). |
| NFR-2 | Subprocess каждого MCP-сервера запускается в правильно настроенной среде (cwd, env), без наследования секретов из main process (kроме явно whitelisted). |

#### Use Case BDD 2 (Edge: один MCP failed → degraded mode)

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | В `.claw/mcp.json` объявлены 3 сервера: `filesystem`, `postgres`, `bad-server`. У `bad-server` невалидный config (например путь к binary не существует). |
| **When** | Worker запускается. |
| **Then** | (1) PluginManager пытается запустить все 3; (2) `bad-server` валится на `validate_config` с typed-error; (3) Остальные 2 успешно стартуют; (4) Эмитится событие `mcp.startup_partial { healthy: ["filesystem","postgres"], failed: [{name:"bad-server", reason:..., hint:...}] }` (US-007 PRD); (5) Worker помечен `ready_for_prompt` с warning; (6) `claw doctor` показывает 2 OK + 1 FAIL. |
| **Input** | Mixed-validity MCP config |
| **Output** | Partial-success report; worker готов несмотря на failed plugin |
| **State** | 2 plugins работают; bad-server не запущен; report записан |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | `StartupReport` структура: `{ healthy: Vec<HealthyPlugin>, degraded: Vec<DegradedPlugin>, failed: Vec<FailedPlugin> }`; ВСЕГДА эмитится по итогу startup. |
| FR-5 | Degraded mode: plugin запустился, но healthcheck WARN (например MCP-сервер ответил, но `tools/list` пустой) — записывается в degraded, не failed. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | Per-plugin timeout strict (default 5 с); превышение → failed без блокировки остальных. |
| NFR-4 | Failed plugin не должен оставлять "сирот" — child-процесс убивается с SIGKILL после graceful timeout. |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Разработчик / агент |
| **User Story ID** | US-2 |
| **User Story** | Как разработчик, я хочу, чтобы plugin lifecycle (start → healthcheck → stop) был детерминирован, всегда корректно очищался ресурсы (даже при panic), и работал с разными типами plugins (MCP, LSP, internal registries). |
| **UX / User Flow** | На каждый plugin — пара start+stop. PluginManager использует RAII-обёртку: при drop вызывается stop. На panic — std::panic::catch_unwind гарантирует cleanup. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Worker запущен с одним MCP-сервером и одним LSP. Они оба running. |
| **When** | Пользователь делает `Ctrl+C` (SIGINT) или сессия завершается через `/exit`. |
| **Then** | (1) PluginManager получает signal и инициирует graceful shutdown; (2) Для каждого plugin вызывается `stop(handle)` с timeout 3 секунды; (3) Если timeout — SIGKILL; (4) Все temp-файлы удаляются; (5) Эмитится `mcp.shutdown { plugins: [...statuses...] }`; (6) Процесс exits 0. |
| **Input** | SIGINT или `/exit` |
| **Output** | Clean shutdown, все child-процессы завершены, ресурсы освобождены |
| **State** | `ps -ef | grep mcp-server` ничего не возвращает; temp-files удалены |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | Graceful shutdown: первый attempt — `stop()` (для MCP — `shutdown` request); при timeout 3 секунды — SIGTERM; при +2 секунды — SIGKILL. |
| FR-7 | RAII через `Drop` для PluginHandle: гарантирует stop даже при unexpected drop (panic, early return). |
| FR-8 | Cleanup hooks для temp-файлов и unix-sockets; при rerun-старте сирые ресурсы детектятся и убираются (`mcp.cleanup_orphans`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-5 | Cleanup-test: kill -9 worker + restart → 0 orphan процессов через 1 секунду (cleanup_orphans). |
| NFR-6 | Shutdown общее время ≤ (3 + 2) × N_plugins / parallel_factor (например ≤ 10 секунд для 4 plugins при parallel=2). |

#### Use Case BDD 2 (Internal registries — TaskRegistry / TeamRegistry / CronRegistry)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Worker использует TaskRegistry для управления задачами (TaskPacket lifecycle), TeamRegistry для команд агентов, CronRegistry для расписания периодических заданий. Это internal plugins, не subprocess'ы. |
| **When** | Worker запускается. |
| **Then** | (1) Каждый registry имплементирует Plugin trait; (2) `start()` инициализирует in-memory state + опционально load из persistent backing-store; (3) `healthcheck()` возвращает количество задач/команд/заданий; (4) `stop()` сохраняет state на диск и закрывает handles; (5) `claw doctor` показывает их status. |
| **Input** | Worker startup |
| **Output** | TaskRegistry/TeamRegistry/CronRegistry готовы; их API доступно для slash-команд |
| **State** | In-memory state + persistent files synced |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | TaskRegistry хранит TaskPacket (objective/scope/branch_policy/commit_policy/escalation_policy) — структуры из F6/Roadmap Phase 4. |
| FR-10 | TeamRegistry + CronRegistry — in-process, persisted в `.claw/team-registry.json` и `.claw/cron-registry.json` соответственно. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-7 | Internal registries не имеют subprocess'ов, но обязаны имплементировать тот же Plugin trait — единый API для startup-report'а. |
| NFR-8 | Persistent state записывается атомарно (temp + rename). |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Разработчик / тестировщик |
| **User Story ID** | US-3 |
| **User Story** | Как разработчик тестов, я хочу, чтобы plugin discovery в тестах был полностью изолирован (свой `$HOME`, свои config-файлы), чтобы тесты не зависели от глобальной установки и не флакали из-за чужих plugins. |
| **UX / User Flow** | `cargo test` использует test-harness, который для каждого теста создаёт temp-`$HOME` (`tempfile::tempdir`) и точно-определённые plugins; реальные глобальные plugin'ы из `~/.claw/` не подгружаются. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | На dev-машине у пользователя есть глобальные плагины в `~/.claw/plugins/`. Запускается `cargo test` для plugin discovery. |
| **When** | Тест требует "пустого" plugin окружения. |
| **Then** | (1) Test-harness устанавливает `HOME=<tempdir>` и `CLAW_HOME=<tempdir>/.claw` для дочерних процессов; (2) Discovery читает только `<tempdir>/.claw/plugins/`; (3) Глобальные plugins НЕ видны; (4) После теста tempdir автоматически удаляется. |
| **Input** | Test environment override |
| **Output** | Discovery возвращает только тестовые plugins |
| **State** | Реальный `~/.claw/` не модифицирован |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | Plugin discovery читает `$CLAW_HOME` (если задан) или `$HOME/.claw`; никогда не делает hardcoded `/home/$USER/.claw`. |
| FR-12 | Test-harness exports `HOME=<tempdir>` для дочерних подпроцессов (subprocess.env), а не только для текущего процесса. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-9 | Параллельные тесты не должны мешать друг другу — каждый имеет свой tempdir. |
| NFR-10 | Discovery читает все plugin manifests параллельно (≤ 100 мс на 50 plugins). |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Internal Rust API; конфиги `.claw/mcp.json`, `.claw/plugins.json`; CLI: `claw mcp list/install/remove`, `claw skills list` |
| **User Entry Points** | `claw mcp ...` subcommands; конфиг-файлы; slash `/skills` |
| **Main Screens / Commands** | `claw mcp list` — таблица plugins+статусы; `claw skills list` — список tools per plugin |
| **Input / Output Format** | JSON-config для declaration; JSON-RPC для MCP-протокола |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `plugins` crate + `runtime::McpToolRegistry` + `runtime::LspRegistry` + internal Task/Team/Cron registries |
| **Responsibility** | Plugin discovery, lifecycle, healthcheck, registration tools, cleanup |
| **Business Logic** | На startup: `discover_plugins() → for each: validate_config → spawn → handshake → register tools/resources`. На shutdown: `for each plugin in reverse order: stop → cleanup`. На failure: `report partial → continue с healthy`. |
| **API / Contract** | `pub trait Plugin { ... }`; `pub struct PluginManager { plugins, handles }`; `pub fn startup() -> StartupReport`; `pub fn shutdown() -> ShutdownReport`. MCP-спец: `MCPSession::initialize/list_tools/call_tool/shutdown` |
| **Request Schema** | `.claw/mcp.json`: `{ servers: [{ name, command, args, env, cwd, timeout }] }` |
| **Response Schema** | `StartupReport { healthy, degraded, failed }`; `HealthStatus { ok|warn|fail, message?, last_check }` |
| **Error Handling** | Per-plugin failures изолированы; PluginManager не паникует на single failure. Cleanup всегда вызывается (RAII + panic-safe). |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Plugin`, `PluginManifest`, `PluginHandle`, `HealthStatus`, `StartupReport`, `MCPSession`, `LSPSession`, `TaskPacket`, `Team`, `CronJob`, `ToolNamespace` |
| **Relationships (ER)** | `PluginManager` 1—N `Plugin`; `Plugin` 1—1 `PluginHandle`; `MCPSession` 1—N `Tool`; `TaskRegistry` 1—N `TaskPacket`; `TeamRegistry` 1—N `Team`; `CronRegistry` 1—N `CronJob` |
| **Data Flow (DFD)** | `discover()` → `parse manifests` → `parallel: validate+start+handshake` → `register tools` → `run`. На shutdown: `signal → for each plugin: stop` (parallel) → `cleanup orphans`. |
| **Input Sources** | `.claw/mcp.json`, `.claw/plugins.json` (для общих plugins), `~/.claw/...` или `$CLAW_HOME` (глобальные); env (subprocess) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Subprocess capability (POSIX или Windows CreateProcess) для запуска MCP/LSP-серверов |
| stdin/stdout pipes для JSON-RPC общения с MCP-серверами |
| Опционально Unix-socket или named pipe для server-spec'ic transports |
| Файловая система для state (`.claw/team-registry.json`, `.claw/cron-registry.json`, etc.) |
| RAM: ≤ N × 50 МБ под subprocess'ы plugins (зависит от каждого plugin) |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Plugin trait + PluginManager + MCP-wrapper + namespaced tool registration | crate `plugins`, F4 | MCP-сервер успешно стартует, tools видны под `mcp__<server>__<tool>` | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Partial-success StartupReport + degraded mode + per-plugin timeouts | T-1, F7 | Один failed plugin не блокирует worker; report корректно эмитится | ST-4, ST-5 |
| UC-2.1 | T-3 | Graceful shutdown + RAII cleanup + cleanup_orphans + LSP wrapper | T-1 | Cleanup гарантирован при panic; LSP wrapper аналогично MCP | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Internal registries (Task/Team/Cron) с Plugin contract + persistent state | T-1 | Все 3 registries реализуют Plugin trait; state атомарно сохраняется | ST-9, ST-10 |
| UC-3.1 | T-5 | $CLAW_HOME / isolated discovery + test-harness helpers | T-1 | Параллельные тесты не пересекаются; discovery читает только override path | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Trait `Plugin`; PluginManager (parallel start, handshake, registration); MCP wrapper, реализующий Plugin поверх MCP-протокола (initialize/list_tools/call_tool/shutdown); namespaced tool registry. |
| **Dependencies** | crate `plugins`, F4 (Tool trait для регистрации) |
| **DoD** | Тест с реальным MCP-сервером (например `mcp-server-filesystem`): tools видны и вызываются; namespace prevents conflicts. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | `Plugin` trait + `PluginManager` skeleton (parallel start, store handles) | — | Trait компилируется; manager умеет start/stop |
| ST-2 | MCP wrapper (subprocess + JSON-RPC over stdio + initialize/list_tools/call_tool/shutdown) | ST-1 | Smoke-тест с фикстурным MCP-сервером проходит |
| ST-3 | `McpToolRegistry` с namespace `mcp__<server>__<tool>`; интеграция с F4 Tool trait | ST-2, F4 | Tool вызывается через runtime как обычный; namespace prevent conflicts |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | `StartupReport { healthy, degraded, failed }`; per-plugin timeout (default 5 с); один failed не блокирует остальных; emit event `mcp.startup_partial`. |
| **Dependencies** | T-1, F7 (telemetry) |
| **DoD** | Тест с одним bad-плагином и двумя good — worker готов с warning; event эмитится. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | StartupReport struct + сбор результатов параллельных стартов | T-1 | Тест: 1 fail + 2 ok → правильный shape |
| ST-5 | Per-plugin timeout + event `mcp.startup_partial` через telemetry | T-1, F7 | Тест: timeout срабатывает; event имеет healthy/failed/degraded поля |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Graceful shutdown (stop → SIGTERM → SIGKILL escalation), RAII через Drop для PluginHandle, panic-safe cleanup, cleanup_orphans на startup, LSP wrapper аналогично MCP. |
| **Dependencies** | T-1 |
| **DoD** | Crash-test (kill -9) → restart → 0 orphan процессов; panic в worker → cleanup всё равно вызывается. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Graceful shutdown ladder + Drop для PluginHandle | T-1 | Тест на panic в worker → child процесс не остаётся (drop trace) |
| ST-7 | cleanup_orphans на startup (детектит и убивает stale subprocess по lock-file/pid-file) | ST-6 | Crash-restart тест: 0 orphan через 1 секунду |
| ST-8 | LSP wrapper (LSP протокол поверх stdio); LspRegistry | T-1 | Smoke-тест с rust-analyzer: hover/definition работают |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Внутренние registries (TaskRegistry — TaskPacket lifecycle, TeamRegistry, CronRegistry) реализуют Plugin contract. Persistent state в JSON, atomic write. |
| **Dependencies** | T-1 |
| **DoD** | Все 3 registry plug into PluginManager; state pers и round-trip-stable. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | TaskRegistry + TaskPacket struct (objective/scope/branch_policy/commit_policy/escalation_policy) | T-1 | CRUD-операции работают; persistent JSON корректен |
| ST-10 | TeamRegistry + CronRegistry с persistent state (atomic write) | T-1 | Restart восстанавливает state |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Discovery читает `$CLAW_HOME` или `$HOME/.claw` (никогда hardcoded); test-harness helper для создания изолированного $HOME (tempdir). Subprocess наследует overridden HOME. |
| **Dependencies** | T-1 |
| **DoD** | Параллельные тесты не пересекаются; глобальные plugins из реального ~/.claw НЕ видны в тестах. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Discovery resolver: $CLAW_HOME > $HOME/.claw, никогда hardcoded | T-1 | Unit-тест: подмена env vars → resolver возвращает правильный путь |
| ST-12 | Test-harness helper `with_isolated_claw_home(|home| { ... })`; subprocess.env переопределяется | T-1 | Параллельный test-run: 100 тестов одновременно — 0 cross-leakage |
