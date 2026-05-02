# SPEC — Feature 4: Built-in Tools & Permission System

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Built-in Tools & Permission System |
| **Description (Goal / Scope)** | Набор встроенных инструментов агента (`Bash`, `ReadFile`, `WriteFile`, `Edit`, `Grep`, `Glob`) с проверками безопасности и многоуровневая система разрешений. Включает: PermissionEnforcer, режимы `read-only` / `workspace-write` / `danger-full-access`, фильтр `--allowedTools`, защита от path-traversal (символические ссылки, `../`), лимиты размера на чтение/запись, обнаружение бинарных файлов. Вне скоупа: AskUserQuestion (заглушка по PARITY), MCP-инструменты (F8). |
| **Client** | `runtime` crate (вызывает tools при tool_use в ответе модели); агент через tool definitions, передаваемые в API. |
| **Problem** | Без встроенных tools модель не может взаимодействовать с файловой системой и shell — это базовое требование для coding-агента. Без permission-системы tools могут случайно (или по prompt injection) выйти за границы рабочей области, выполнить деструктивную команду или прочитать чувствительные файлы за пределами репо. |
| **Solution** | (1) Trait `Tool` с методом `execute(input, context) -> ToolResult`; (2) Реализации Bash/ReadFile/WriteFile/Edit/Grep/Glob; (3) PermissionEnforcer проверяет каждый вызов перед execute: разрешён ли write, не выходит ли путь за boundaries, не превышает ли лимиты; (4) Три permission-mode с разными настройками по умолчанию; (5) `--allowedTools` — explicit allowlist; (6) Boundary-проверка: канонизация пути → проверка, что начинается с workspace root, с резолвингом symlinks. |
| **Metrics** | (1) 100% blocked path-traversal атак на тестовом наборе (включая symlinks, encoded `..`); (2) Все 6 tools покрыты integration-тестами; (3) Permission-deny возвращается за ≤ 5 мс; (4) В режиме `read-only` ни один write-tool не выполняется (assertion в тестах). |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | AI-агент (claw) |
| **User Story ID** | US-1 |
| **User Story** | Как агент, я хочу читать/писать файлы и запускать shell-команды через типизированные tools, чтобы взаимодействовать с кодовой базой при выполнении задачи. |
| **UX / User Flow** | Модель эмитит `tool_use { name: "read_file", input: { path: "src/main.rs" } }` → runtime передаёт PermissionEnforcer → если allow → tool.execute → результат `tool_result { content, is_error? }` обратно к модели. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Worker запущен с `--permission-mode workspace-write`, модель эмитит `tool_use {name: "read_file", input: {path: "Cargo.toml"}}`. |
| **When** | `runtime` обрабатывает tool_use. |
| **Then** | (1) PermissionEnforcer проверяет: tool в allowlist режима workspace-write — ✓ (read разрешён); (2) Канонизация пути → проверка, что внутри workspace root — ✓; (3) Размер файла ≤ лимита (например 10 МБ) — ✓; (4) Tool читает файл и возвращает `{ content: "...", encoding: "utf-8", size: 1234 }`; (5) Telemetry фиксирует `tool.invoked { name, duration_ms, status: ok }`. |
| **Input** | `tool_use { name: "read_file", input: { path: "Cargo.toml" } }`, mode `workspace-write` |
| **Output** | `tool_result { content: "<file content>", is_error: false }` |
| **State** | Файловая система не изменилась; telemetry событие записано |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | `Tool` trait: `name() -> &str; schema() -> JsonSchema; execute(input, ctx) -> Result<ToolResult>`. |
| FR-2 | `ReadFile` поддерживает: абсолютные и относительные пути (резолвятся от `cwd`), encoding detection (UTF-8 / binary), opt-in `offset` и `limit` (для больших файлов). |
| FR-3 | Все file-tools канонизируют путь через `Path::canonicalize()` и сравнивают с `workspace_root` после канонизации; `..` и symlinks резолвятся до проверки. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | ReadFile с лимитом 10 МБ выполняется ≤ 100 мс на SSD; превышение лимита → typed-error `tool.read.too_large` без чтения файла в память. |
| NFR-2 | Бинарные файлы определяются по null-byte sniff в первых 4 КБ; для них возвращается metadata (`size, mime_guess`), но не raw bytes (если только не указан явный флаг). |

#### Use Case BDD 2 (Edge: path traversal attempt)

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Worker запущен в `/repo`, mode `workspace-write`. В репо есть symlink `evil -> /etc/passwd`. |
| **When** | Модель эмитит `tool_use { name: "read_file", input: { path: "evil" } }` или `{ path: "../../etc/passwd" }`. |
| **Then** | (1) Канонизация → реальный путь `/etc/passwd`; (2) Проверка boundary: `/etc/passwd` НЕ начинается с `/repo` → permission denied; (3) Возвращается `tool_result { is_error: true, content: { errno: "permission.path_outside_workspace", target, hint } }`; (4) Файл НЕ читается. |
| **Input** | `read_file` с подозрительным path |
| **Output** | Typed-error в tool_result |
| **State** | Файловая система не изменилась; telemetry событие `tool.denied { reason: path_outside_workspace }` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | Boundary-чек: канонизированный путь должен иметь префикс `workspace_root`; symlinks следуют до конечной цели. |
| FR-5 | URL-encoded sequences (`%2e%2e`) и Unicode-overlongs не должны обходить проверку (нормализация перед канонизацией). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | Permission denial возвращается за ≤ 5 мс (быстрый отказ без I/O чтения). |
| NFR-4 | Тест-набор path-traversal содержит ≥ 20 кейсов: `..`, symlinks, encoded `..`, абсолютные пути, NUL-инъекции. |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Разработчик |
| **User Story ID** | US-2 |
| **User Story** | Как пользователь, я хочу настроить permission-mode (`read-only` / `workspace-write` / `danger-full-access`) и явный список разрешённых tools (`--allowedTools`), чтобы безопасно запускать агент в production-кодах и CI. |
| **UX / User Flow** | (a) `claw --permission-mode read-only "what does this repo do?"` — агент может читать, но не писать и не выполнять bash; (b) `claw --allowedTools read,glob "..."` — только два tool'а доступны; (c) В REPL: `/permissions` — просмотр текущего состояния, `/permissions set <mode>` — смена режима. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Worker запущен с `--permission-mode read-only`. |
| **When** | Модель эмитит `tool_use { name: "write_file", input: { path: "x.txt", content: "hello" } }`. |
| **Then** | (1) PermissionEnforcer проверяет: `write_file` НЕ разрешён в режиме `read-only`; (2) Возвращается `tool_result { is_error: true, content: { errno: "permission.tool_not_allowed", tool: "write_file", mode: "read-only", hint: "switch to workspace-write" } }`; (3) Файл не создаётся. |
| **Input** | `--permission-mode read-only`, `tool_use write_file` |
| **Output** | Typed-error в tool_result, файл не записан |
| **State** | Файловая система не изменилась; telemetry `tool.denied { reason: mode_disallows }` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | `read-only` mode разрешает: `read_file`, `grep`, `glob`. Запрещает: `write_file`, `edit`, `bash` (последний по умолчанию). |
| FR-7 | `workspace-write` mode разрешает все tools, но ограничивает write-операции workspace-boundary. |
| FR-8 | `danger-full-access` mode отключает workspace-boundary check (но сохраняет remaining защиты — лимиты размера, бинарь-detect). Требует явного подтверждения (intent flag). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-5 | Смена режима в REPL (`/permissions set read-only`) применяется немедленно; следующий tool_use уже видит новый режим. |
| NFR-6 | `danger-full-access` всегда логируется в telemetry с warning-уровнем; в начале сессии печатается баннер. |

#### Use Case BDD 2 (Edge: --allowedTools narrower than mode)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Worker запущен с `--permission-mode workspace-write --allowedTools read,glob`. |
| **When** | Модель эмитит `tool_use { name: "bash", input: { cmd: "ls" } }`. |
| **Then** | (1) Mode разрешает bash, но `--allowedTools` НЕ включает его; (2) Эффективная политика — пересечение, bash отклоняется; (3) Возвращается `tool_result { is_error: true, content: { errno: "permission.tool_not_in_allowlist", tool: "bash", allowlist: ["read","glob"] } }`. |
| **Input** | `--permission-mode workspace-write --allowedTools read,glob`, `tool_use bash` |
| **Output** | Typed-error |
| **State** | Bash не запущен; telemetry событие |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | Эффективная политика = пересечение `mode_allowed_tools ∩ --allowedTools` (если последний задан). |
| FR-10 | `--allowedTools` принимает comma-separated имена; алиасы `read`/`write`/`bash`/`grep`/`glob`/`edit`. Невалидное имя → exit 2 с подсказкой. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-7 | Эффективная политика вычисляется один раз при старте сессии и кешируется; пересчёт только при `/permissions set`. |
| NFR-8 | Decision-table между mode и allowlist покрыта property-based тестами. |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | AI-агент / разработчик |
| **User Story ID** | US-3 |
| **User Story** | Как агент, я хочу запускать shell-команды через `bash` tool с инкрементной валидацией (например блокирование `rm -rf /`, sudo без явного intent) и редактировать файлы через `edit` (string-replace или patch), чтобы безопасно автоматизировать рутинные операции. |
| **UX / User Flow** | `tool_use { name: "bash", input: { cmd: "cargo test" } }` → bash-validator проверяет паттерны → execute с timeout → возвращается `{ stdout, stderr, exit_code, duration_ms }`. `tool_use { name: "edit", input: { path: ..., old_string, new_string, replace_all } }` → атомарный patch файла. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Worker в `workspace-write` mode; модель хочет запустить `cargo test --workspace`. |
| **When** | Модель эмитит `tool_use { name: "bash", input: { cmd: "cargo test --workspace", timeout_ms: 120000 } }`. |
| **Then** | (1) Bash-validator проверяет паттерны: `rm -rf /`, `sudo`, `:(){ :|:& };:` — отсутствуют → ✓; (2) Команда запускается через subprocess; cwd = workspace_root; env = inherited (за исключением secrets); (3) По завершении возвращается `{ stdout, stderr, exit_code, duration_ms }`; (4) Если timeout превышен → процесс убивается, возвращается `is_error: true, errno: "bash.timeout"`. |
| **Input** | `bash` tool с cmd и timeout |
| **Output** | `tool_result { stdout, stderr, exit_code, duration_ms }` |
| **State** | Файловая система может быть изменена самим subprocess; telemetry событие |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | Bash-validator проверяет дисqualifying-паттерны (deny-list) перед запуском; список включает: `rm -rf /`, `sudo`, fork-bomb, очевидные secrets-exfiltrate (curl с raw env). |
| FR-12 | `edit` tool принимает `{ path, old_string, new_string, replace_all? }`; ошибка если `old_string` не уникален (без `replace_all`); атомарная запись (temp + rename). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-9 | Bash subprocess запускается с обёрткой stdin (closed by default), stdout/stderr через pipe; deadlock на `BrokenPipe` устранён (см. ROADMAP про Linux race). |
| NFR-10 | `edit` требует, чтобы файл был прочитан в текущей сессии (track), иначе возвращает warning "file may have changed since last read". |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Не имеет UI; tools вызываются runtime'ом по tool_use |
| **User Entry Points** | `--permission-mode <mode>`, `--allowedTools a,b,c`; slash `/permissions [set <mode>]` |
| **Main Screens / Commands** | Вывод `/permissions` показывает текущий mode + effective allowlist + workspace root |
| **Input / Output Format** | Tool input = JSON по schema каждого tool; output = `ToolResult { content: ContentBlocks, is_error?: bool }` |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `tools` crate + `runtime::permissions::PermissionEnforcer` |
| **Responsibility** | (1) Реализации tools; (2) Канонизация и boundary-checks путей; (3) Validators (bash deny-list); (4) PermissionEnforcer dispatching gate; (5) Лимиты (размер, timeout). |
| **Business Logic** | На каждый tool_use: `enforce(tool_name, input, ctx) -> Allow|Deny(reason)`. Если allow → `tools[name].execute(input)`. Errors всегда возвращаются как `tool_result.is_error=true` (не паника). |
| **API / Contract** | `pub trait Tool { fn name() -> &str; fn schema() -> JsonSchema; fn execute(input, ctx) -> Result<ToolResult>; }`. `pub fn enforce(...)`. |
| **Request Schema** | Per-tool: read_file `{path, offset?, limit?}`; write_file `{path, content, encoding?}`; edit `{path, old_string, new_string, replace_all?}`; bash `{cmd, timeout_ms?, cwd?}`; grep `{pattern, path?, glob?, case_insensitive?}`; glob `{pattern, root?}`. |
| **Response Schema** | `ToolResult { content: Vec<ContentBlock>, is_error: bool }`. ContentBlock = text/json/file_meta. |
| **Error Handling** | Typed-error в tool_result.content при is_error=true: `{operation, target, errno, hint, retryable}`. Errors не паникуют; runtime передаёт их обратно модели. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Tool` (trait), `ToolInvocation`, `ToolResult`, `PermissionMode`, `EffectivePolicy`, `WorkspaceRoot`, `BashValidationResult` |
| **Relationships (ER)** | `Session` 1—1 `EffectivePolicy`; `EffectivePolicy` derived from `(PermissionMode, AllowedToolsList)`; `ToolInvocation` 1—1 `ToolResult` |
| **Data Flow (DFD)** | `Model → tool_use` → `runtime.handle_tool_use()` → `PermissionEnforcer.enforce(name, input)` → if Allow → `Tool.execute()` → `ToolResult` → `runtime.append_user_turn(tool_result)` → next API call |
| **Input Sources** | Tool inputs (от модели), permission mode (CLI/REPL), allowedTools (CLI), workspace_root (cwd при старте) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Файловая система (POSIX или NTFS) с поддержкой канонизации путей и symlinks |
| Доступ к `/bin/sh` (Linux/macOS) или `cmd.exe`/`pwsh` (Windows) для bash-tool |
| RAM: до `read_limit + write_limit` на одновременные tool-calls (обычно ≤ 50 МБ) |
| Диск: достаточно для temp-файлов при atomic-write |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | `Tool` trait + `ReadFile` + лимиты + binary detection | crate `tools` | Tool работает, лимиты применяются, binary detect | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Boundary-проверка путей (канонизация, symlinks, encoded `..`) | T-1 | ≥ 20 path-traversal тестов проходят | ST-4, ST-5 |
| UC-2.1 | T-3 | PermissionEnforcer + 3 mode + matrix tools per mode | T-1 | Все mode покрыты unit/integration; smoke на каждый | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | `--allowedTools` фильтр + intersection logic + slash `/permissions` | T-3, F1 | Intersection корректна; CLI-валидация | ST-9, ST-10 |
| UC-3.1 | T-5 | `Bash`, `WriteFile`, `Edit`, `Grep`, `Glob` + bash deny-list + atomic edit | T-1, T-2, T-3 | Все tools работают; deny-list блокирует тестовые паттерны | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Trait `Tool`, реализация `ReadFile` с offset/limit/encoding-detect, лимит 10 МБ, бинарь-detection через null-byte sniff. |
| **Dependencies** | crate `tools` |
| **DoD** | ReadFile работает на UTF-8/UTF-16/binary; лимит применяется; integration-тесты на больших файлах. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Trait `Tool` + структуры `ToolResult`/`ContentBlock` | — | Trait компилируется; mockable; round-trip JSON |
| ST-2 | `ReadFile` с offset/limit/encoding | ST-1 | Тесты на UTF-8/UTF-16; лимит 10 МБ — превышение возвращает typed-error |
| ST-3 | Binary detection (null-byte в первых 4 КБ) | ST-2 | Бинарь не читается полностью; metadata возвращена |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Boundary-проверка: канонизация пути, резолв symlinks, нормализация перед канонизацией (для encoded `..`); сравнение с `workspace_root`. |
| **Dependencies** | T-1 |
| **DoD** | ≥ 20 path-traversal атак заблокированы (включая encoded sequences, symlinks, NUL-инъекции). |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Канонизация и boundary-функция `path_within(root, path) -> bool` | T-1 | Unit-тесты: симлинки, `..`, абсолютные пути, NUL |
| ST-5 | Нормализация encoded sequences и Unicode-overlongs до канонизации | ST-4 | Тесты на `%2e%2e`, overlong UTF-8, mixed-case |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | `PermissionEnforcer` + три mode (`read-only`/`workspace-write`/`danger-full-access`) + matrix разрешённых tools per mode. Warning баннер для danger-mode. |
| **Dependencies** | T-1 |
| **DoD** | Каждый mode покрыт unit-тестами; integration-сценарий на каждый mode (read запрещён в read-only? и т.д.). |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | `PermissionEnforcer` API + matrix mode → tools | T-1 | Unit-тесты на матрицу |
| ST-7 | Реализация трёх mode + dangerous-mode banner | ST-6 | Banner печатается; режим логируется в telemetry |
| ST-8 | Интеграция enforcer'а в runtime; smoke-test для каждого режима | ST-6, F1 | Smoke-тесты: write_file deny в read-only; bash allow в workspace-write |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Парсинг `--allowedTools`, intersection с mode-allowlist, валидация имён tools, slash `/permissions [set <mode>]`. |
| **Dependencies** | T-3, F1 (CLI parser, slash registry) |
| **DoD** | Property-based тесты на intersection; CLI-валидация на невалидных именах. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Парсер comma-separated списка + валидация | T-3 | Невалидные имена → exit 2 + подсказка |
| ST-10 | Slash-команда `/permissions` (показ + set), пересчёт effective policy | T-3, F1 | Integration-тест: `/permissions set read-only` блокирует write на следующем turn |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Реализация остальных tools: `WriteFile` (atomic write), `Edit` (unique old_string check, atomic), `Bash` (subprocess, timeout, deny-list, BrokenPipe-fix), `Grep` (rg-like), `Glob`. |
| **Dependencies** | T-1, T-2 (boundary), T-3 (permissions) |
| **DoD** | Все 5 tools имеют integration-тесты; bash deny-list блокирует ≥ 5 опасных паттернов; edit идемпотентен. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `WriteFile` + `Edit` + atomic write (temp + rename) + uniqueness check | T-2, T-3 | Edit падает с понятной ошибкой при дублирующемся `old_string`; атомарность подтверждена crash-тестом |
| ST-12 | `Bash` (subprocess + timeout + deny-list + BrokenPipe-fix) + `Grep` + `Glob` | T-3 | Deny-list блокирует тест-паттерны; integration на cargo test; grep с regex; glob с `**` |
