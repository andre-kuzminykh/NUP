# SPEC — Feature 5: Session Management & Resume

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Session Management & Resume |
| **Description (Goal / Scope)** | Персистентное хранение conversation-сессий в `.claw/sessions/` с возможностью возобновления (`--resume latest` / `--resume <id>`). Включает: формат session-файла (turns + metadata), стабильную идентичность сессии (title/workspace/purpose), per-worktree isolation (фикс phantom-completion), `--cwd` и `--date` флаги для контроля контекста, slash `/session`/`/export`, конфиг-резолвер по уровням. Вне скоупа: telemetry events (F7), recovery (F6). |
| **Client** | Пользователи REPL/CLI; оркестраторы (восстанавливают context при retry); экспорт в человекочитаемые форматы. |
| **Problem** | Без персистентных сессий каждое прерывание (kill, exit, OOM) теряет контекст. Без идентичности сессий оркестратор не может надёжно сопоставить worker'ов и задачи. Без per-worktree isolation параллельные worker'ы в разных worktree-веткa х git могут "склеить" свои сессии и завершить друг друга (phantom completion, US-019 PRD). |
| **Solution** | (1) Каталог `.claw/sessions/<session_id>/` с `meta.json`, `turns.jsonl` (append-only), `tools.jsonl`; (2) Стабильный `session_id` = ULID, дополнительно стабильные `title`/`workspace`/`purpose` (US-016 PRD); (3) Worktree-aware key включает абсолютный путь worktree → каждая worktree имеет свою серию sessions; (4) Резолвер сессии по `--resume`: `latest`, `<id>`, или `name:<title>`; (5) Slash `/session list/show/rename`, `/export <fmt>`. |
| **Metrics** | (1) 0% случаев phantom-completion на регрессионном тесте с 10 параллельными worktree; (2) Resume восстанавливает 100% turns в правильном порядке; (3) Запись turn'а ≤ 20 мс (append-only JSONL); (4) Экспорт сессии в markdown/json — корректный round-trip. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Разработчик |
| **User Story ID** | US-1 |
| **User Story** | Как пользователь, я хочу автоматически сохранять каждую сессию и возобновлять её через `--resume latest` или `--resume <id>`, чтобы не терять контекст между запусками. |
| **UX / User Flow** | (1) `claw "do thing"` создаёт сессию, после exit она в `.claw/sessions/`. (2) `claw --resume latest "continue"` находит последнюю сессию (mtime), загружает все turns и продолжает диалог с моделью. (3) `claw --resume 01HXY... "..."` явный ID. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | В `.claw/sessions/` существует сессия `01HXY...` с 5 turns, последний — assistant turn с tool_use. |
| **When** | Пользователь запускает `claw --resume latest "продолжай"`. |
| **Then** | (1) Резолвер выбирает последнюю по mtime сессию; (2) `meta.json` валидируется; (3) `turns.jsonl` читается полностью и восстанавливает context; (4) Новый user turn `"продолжай"` добавляется; (5) Запрос к API содержит весь восстановленный history; (6) Worker-state переходит в `running` для существующего session_id (не создаётся новый). |
| **Input** | `--resume latest "продолжай"` |
| **Output** | Стрим ответа модели на основе восстановленного контекста |
| **State** | Сессия `01HXY...` обновлена: `+1 user turn`, `+1 assistant turn` в `turns.jsonl`; revision увеличена. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | `--resume latest` находит сессию по `max(mtime)` среди валидных в `.claw/sessions/<worktree-key>/`. |
| FR-2 | `--resume <id>` принимает полный или префиксный ULID; ambiguous prefix → exit 2 с подсказкой. |
| FR-3 | `--resume name:<title>` — поиск по title из `meta.json`; case-insensitive, exact match. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Загрузка сессии с 1000 turns ≤ 500 мс (потоковое чтение JSONL). |
| NFR-2 | Append-only гарантия: writer не модифицирует существующие строки `turns.jsonl`; corruption recovery — обрезка с последней валидной строки. |

#### Use Case BDD 2 (Edge: ambiguous prefix)

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | В `.claw/sessions/` две сессии с ID `01HXY...A` и `01HXY...B`. |
| **When** | Пользователь запускает `claw --resume 01HXY`. |
| **Then** | (1) Резолвер находит ≥ 2 совпадения; (2) Возвращается typed-error `session.ambiguous_prefix` с перечнем кандидатов и hint "укажите больше символов"; (3) Сессия не загружается; exit 2. |
| **Input** | `--resume 01HXY` |
| **Output** | Список кандидатов в stderr; exit code 2 |
| **State** | Никаких изменений |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | Ambiguous-prefix → typed-error с массивом `candidates: Vec<{id, title, last_modified}>` (≤ 10 элементов в выводе). |
| FR-5 | Если ни одна сессия не найдена — `session.not_found` с hint "запустите без --resume для новой сессии". |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | Lookup среди 10 000 сессий ≤ 200 мс (через индекс ID → mtime, обновляемый при записи). |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Оркестратор / разработчик с git-worktrees |
| **User Story ID** | US-2 |
| **User Story** | Как оркестратор, использующий несколько git worktrees параллельно, я хочу, чтобы сессии и worker-state были изолированы по worktree, чтобы worker в `feature-A` не завершал и не путал worker в `feature-B`. |
| **UX / User Flow** | Каждый worktree имеет свой `.claw/sessions/` (внутри worktree directory) и свой `.claw/worker-state.json`. Resume в worktree A не видит сессии worktree B (если только не указан путь). |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Один git-репо с двумя worktrees `/repo/wt-A` и `/repo/wt-B`. В каждом запущен worker. |
| **When** | Worker A завершает свою сессию (`/exit`). |
| **Then** | (1) Только `/repo/wt-A/.claw/worker-state.json` переходит в `finished`; (2) `/repo/wt-B/.claw/worker-state.json` остаётся в `running`; (3) Сессии в `/repo/wt-A/.claw/sessions/` не пересекаются с `/repo/wt-B/.claw/sessions/`; (4) `claw --resume latest` в `/repo/wt-A` НЕ видит сессии из `/repo/wt-B`. |
| **Input** | Параллельная работа двух worker'ов в разных worktree |
| **Output** | Файлы в каждой worktree независимы |
| **State** | Phantom completion НЕ возникает |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | Корень `.claw/` resolved относительно `cwd` worker'а (а не git common-dir); каждая worktree имеет свой `.claw/`. |
| FR-7 | Worker-state file включает поле `worktree_path: AbsolutePath`; читатели проверяют, что worktree совпадает с их cwd, иначе игнорируют. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-4 | Регрессионный тест: ≥ 10 параллельных worker'ов в разных worktree → 0% cross-affecting failures. |
| NFR-5 | Документация в README объясняет worktree-isolation поведение. |

#### Use Case BDD 2 (идентичность сессии)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Сессия создаётся с явным `--title "fix-auth-bug" --purpose "feature/AUTH-123"`. |
| **When** | Worker записывает первый turn. |
| **Then** | (1) `meta.json` сохраняет `{ id, title, purpose, workspace, created_at }` атомарно при создании; (2) Эти поля стабильны и не изменяются последующими turns (US-016 PRD); (3) Slash `/session show` возвращает все эти поля; (4) `--resume name:fix-auth-bug` корректно находит её. |
| **Input** | `--title "fix-auth-bug" --purpose "feature/AUTH-123"` при старте |
| **Output** | `meta.json` с полным набором identity-fields |
| **State** | Identity-fields незыблемы для всей жизни сессии |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-8 | `meta.json` имеет поля: `id (ULID), schema_version, title, purpose, workspace_root, model, permission_mode, created_at, owner?, assignee?` (US-020 PRD). |
| FR-9 | Identity-fields после создания доступны только через `/session rename` (отдельная операция с audit-log). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-6 | Изменение title через `/session rename` записывается в `meta.json` с обновлённым `last_renamed_at`; история rename'ов сохраняется в `meta.history.jsonl`. |
| NFR-7 | При попытке создать две сессии с одинаковым title в одном worktree — warning, но не ошибка (title не unique). |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Разработчик / оркестратор |
| **User Story ID** | US-3 |
| **User Story** | Как пользователь, я хочу контролировать рабочую директорию (`--cwd`), дату-контекст (`--date`) и экспортировать сессию в markdown/json (`/export`), чтобы воспроизводимо работать с агентом в скриптах и делиться сессиями. |
| **UX / User Flow** | (a) `claw --cwd ../other-repo "..."` запускает с другим cwd. (b) `claw --date 2026-04-04 "..."` фиксирует дату-контекст для системного prompt'а. (c) В REPL `/export markdown ./out.md` сохраняет всю историю в человекочитаемый md. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Активная сессия с 7 turns (микс user/assistant/tool_use). Пользователь хочет экспорт в markdown. |
| **When** | В REPL вводится `/export markdown ./conversation.md` (или из CLI `claw export --format markdown --out conversation.md --session-id <id>`). |
| **Then** | (1) Загружается `turns.jsonl`; (2) Каждый turn рендерится: user → `### User`, assistant → `### Assistant`, tool_use → блок ` ```tool_use ... ``` `; (3) Файл записывается атомарно; (4) Возвращается путь и количество экспортированных turns. Для JSON — структурированный full-fidelity dump. |
| **Input** | `/export markdown ./conversation.md` |
| **Output** | Файл `./conversation.md`; в REPL — `✓ exported 7 turns to ./conversation.md` |
| **State** | Сессия не модифицируется; экспортный файл создан |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-10 | `/export` поддерживает форматы: `markdown`, `json` (full-fidelity), `json-lite` (без бинарных tool-output). |
| FR-11 | `--cwd <path>` валидируется при старте: путь должен существовать и быть директорией; иначе exit 2. |
| FR-12 | `--date YYYY-MM-DD` устанавливает `today` в системном prompt'е (вместо реальной даты); используется для воспроизводимости и отладки. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-8 | Экспорт сессии в 1000 turns ≤ 1 секунды на dev-машине. |
| NFR-9 | `--date` валидируется по ISO 8601; невалидное значение → exit 2. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | CLI флаги + slash-команды (`/session`, `/export`); работа с файловой системой |
| **User Entry Points** | `--resume <id|latest|name:...>`, `--cwd`, `--date`, `--title`, `--purpose`; slash `/session list|show|rename`, `/export <fmt> <path>` |
| **Main Screens / Commands** | `/session list` — таблица id, title, last_modified; `/session show` — meta + count turns |
| **Input / Output Format** | Файлы: `meta.json`, `turns.jsonl`, `tools.jsonl`, `meta.history.jsonl` |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `runtime::session` (часть `runtime` крейта) |
| **Responsibility** | (1) CRUD сессий; (2) Резолвер `--resume`; (3) Запись turns атомарно; (4) Worktree-aware пути; (5) Identity-fields integrity; (6) Export. |
| **Business Logic** | На каждый turn: `session.append_turn(t)` → append в `turns.jsonl` + flush + telemetry. На resume: `parse_jsonl(file) -> Vec<Turn>`. На export: `render(turns, format) -> bytes` → atomic write. |
| **API / Contract** | `pub fn create(meta) -> Session`; `pub fn open(id) -> Session`; `pub fn append_turn(t)`; `pub fn list(worktree) -> Vec<SessionSummary>`; `pub fn export(id, format) -> bytes` |
| **Request Schema** | Turn = `{ id, role, content: Vec<ContentBlock>, ts, model?, usage?, tool_use_id? }` |
| **Response Schema** | `Session { meta, turns: Vec<Turn> }`. SessionSummary = `{ id, title, purpose, last_modified, n_turns }` |
| **Error Handling** | `session.not_found`, `session.ambiguous_prefix`, `session.corrupt_meta`, `session.corrupt_turns` (с offset невалидной строки) |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Session`, `SessionMeta`, `Turn`, `ContentBlock`, `ToolInvocation`, `WorktreeKey`, `SessionIndex` |
| **Relationships (ER)** | `Worktree` 1—N `Session`; `Session` 1—1 `SessionMeta`; `Session` 1—N `Turn`; `Turn` 1—N `ContentBlock`; `Session` 1—N `ToolInvocation` |
| **Data Flow (DFD)** | Создание: `meta.json` атомарно записан → `turns.jsonl` open в append. Запись turn: `append + flush(O_DSYNC)` → telemetry. Resume: `read meta → load turns.jsonl` → конструировать `runtime`. Index: при list — scan + cache mtime в `~/.claw/index.bincode`. |
| **Input Sources** | CLI флаги, REPL slash-команды, model output (новые turns), env (`CLAW_HOME` для глобальной директории, опционально) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Файловая система с поддержкой `O_APPEND` и `O_DSYNC` (POSIX) или соответствующих флагов NTFS |
| Достаточно места под `.claw/sessions/` (≈ 10–500 КБ на сессию, рост с числом turns) |
| Опционально: индексный кеш в `~/.claw/index.bincode` или `~/.claw/index.sqlite` для быстрого list |
| FS lock при concurrent writes (через flock или mandatory locks) |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Формат сессии (meta + turns.jsonl) + create/open/append API + `--resume latest/<id>` | crate `runtime` | Создание/открытие/append работают; resume на 1000-turn сессии ≤ 500 мс | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Резолвер ambiguous-prefix + name-search + индекс | T-1 | `--resume name:foo` работает; ambiguous → typed-error со списком | ST-4, ST-5 |
| UC-2.1 | T-3 | Worktree-aware пути + worker-state.json с worktree_path + регрессионный тест на phantom-completion | T-1, F3 | 10 параллельных worktree без cross-affecting | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Identity-fields в meta + `/session rename` с history | T-1, F1 | Identity иммутабельна; rename audit-log работает | ST-9, ST-10 |
| UC-3.1 | T-5 | `--cwd`, `--date` + `/export markdown|json|json-lite` + slash `/session list|show` | T-1, F1 | Все флаги валидируются; export round-trip; 1000 turns ≤ 1 с | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Дизайн формата `meta.json`/`turns.jsonl`/`tools.jsonl`; API `Session::create/open/append_turn`; парсер `--resume <id|latest>`. |
| **Dependencies** | crate `runtime` |
| **DoD** | Round-trip create→append→close→open→read стабилен; corruption recovery (truncate at last valid line) покрыт тестом; resume на 1000-turn ≤ 500 мс. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Структуры `Session`/`SessionMeta`/`Turn`/`ContentBlock` + JSON-Schema | — | Round-trip JSON; schema-version поле |
| ST-2 | Append-only writer (O_APPEND + flush) + parser (поточный, толерантный к truncated last line) | ST-1 | Crash-тест: kill -9 во время append → restart читает все полные строки |
| ST-3 | Резолвер `--resume <id|latest>` + lookup сессий в `.claw/sessions/` | ST-1, ST-2 | `--resume latest` находит max(mtime); ID lookup O(1) после индекса |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Расширение резолвера: prefix-matching ID (с детектом ambiguous), `name:<title>` поиск, persistent index (mtime + title) для быстрого list. |
| **Dependencies** | T-1 |
| **DoD** | Ambiguous-prefix → typed-error с кандидатами; name-search case-insensitive; lookup в 10 000 сессиях ≤ 200 мс. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Prefix matching + ambiguous detect + кандидаты в error | T-1 | Тест: 2 одинаковых префикса → exit 2 с обоими в выводе |
| ST-5 | Persistent index `~/.claw/index.bincode` (id, title, mtime); инвалидация при write | T-1 | Lookup в 10 000 сессий ≤ 200 мс; index перестраивается при corruption |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Worktree-aware пути: `.claw/` resolves относительно cwd worker'а, не git-common-dir. `worker-state.json` содержит `worktree_path`. Регрессионный тест на phantom-completion с 10 параллельными worktree. |
| **Dependencies** | T-1, F3 |
| **DoD** | 10 параллельных worker'ов в разных worktree → 0 cross-affecting (тест-фикстура). Документация в README. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Резолв `.claw/` от worker cwd; worktree_path в meta и worker-state | T-1, F3 | `claw` в `wt-A` НЕ видит `wt-B/.claw/sessions/` |
| ST-7 | Регрессионный тест с 10 worktree (concurrent) — phantom completion = 0 | ST-6 | CI-job: long-running, выявляет регрессии |
| ST-8 | Документация в README + CLAUDE.md о worktree-isolation | — | README содержит "Per-worktree isolation" секцию |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Identity-fields в `meta.json` (id/title/purpose/workspace/created_at/owner/assignee) — иммутабельны после create; `/session rename` записывает в `meta.history.jsonl`. |
| **Dependencies** | T-1, F1 (slash-commands) |
| **DoD** | Identity не меняется случайно; rename — единственный путь; history audit. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Schema meta + immutable check + valid optional fields | T-1 | Прямая запись поля title через append → ошибка |
| ST-10 | `/session rename <new-title>` + запись в history.jsonl | F1, T-1 | После rename: meta.title обновлён; history содержит запись с timestamp |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | `--cwd` (валидация существования), `--date` (ISO 8601, в system-prompt), `/export <fmt> <path>` (markdown/json/json-lite), `/session list|show`. |
| **Dependencies** | T-1, F1 |
| **DoD** | Все CLI флаги покрыты unit-тестами; export round-trip; список форматов задокументирован. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `--cwd`, `--date`, валидация + интеграция в runtime config | F1 | Невалидный cwd → exit 2; невалидная date → exit 2 |
| ST-12 | `/export markdown|json|json-lite` + `/session list|show` | T-1, T-2 | Snapshot-тесты на каждый формат; export 1000 turns ≤ 1 с |
