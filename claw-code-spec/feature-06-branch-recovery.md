# SPEC — Feature 6: Branch Awareness & Auto-Recovery

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Branch Awareness & Auto-Recovery |
| **Description (Goal / Scope)** | Phase 3 ROADMAP: автоматическое обнаружение "stale" веток (отстают от main больше порога) **до** запуска тестов и широкой верификации, плюс набор автоматических recovery-recipes для типовых failure-категорий. Включает: `branch.stale_against_main` event, recovery ledger (recipe_id, attempt_count, timestamps, outcome), 6 авто-рецептов (trust gate, prompt misdelivery, stale branch, MCP failure, network blip, context-overflow), green-ness contract (4 уровня: targeted / package / workspace / merge-ready), commit provenance/worktree awareness. Вне скоупа: лояльность модели к ошибкам (модель сама), policy engine для merge (F8/Roadmap Phase 4 — отдельный кусок). |
| **Client** | Оркестраторы (clawhip), CI-системы, claws-агенты; пользователи через `claw doctor`/`status`. |
| **Problem** | Без stale-branch detection агент тратит время на тесты, которые красные не из-за его кода, а из-за устаревшего main. Без авто-recovery каждый known failure эскалируется к человеку (или другому claw'у), что дорого и медленно. Без green-ness contract "тесты прошли" — двусмысленно (target / package / workspace / merge-ready). |
| **Solution** | (1) Перед тестами — `git fetch origin` + `git merge-base` + diff-count → если stale → emit `branch.stale_against_main { commits_behind, last_main_sha }`, попытаться merge-forward (recipe); (2) `RecoveryLedger` — JSONL `.claw/recovery-ledger.jsonl` с `{ recipe_id, attempt_n, started_at, outcome }`; (3) Recipes реализованы как функции `attempt(failure) -> Result<Recovered|Escalate>`, идемпотентны, лимит 3 attempts; (4) Green-ness contract: enum `GreenScope { Targeted, Package, Workspace, MergeReady }` сопровождает test events. |
| **Metrics** | (1) ≥ 70% known-failure категорий восстанавливаются без эскалации (по recovery-ledger); (2) Stale-branch detection срабатывает за ≤ 2 секунды до запуска тестов; (3) Recovery ledger публично-проверяем (audit); (4) Каждый из 6 recipes имеет deterministic-replay тест. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Claw / агент |
| **User Story ID** | US-1 |
| **User Story** | Как агент, перед запуском "широкой" верификации (cargo test --workspace) я хочу убедиться, что моя ветка не отстаёт от main, чтобы не тратить минуты на тесты, которые красные из-за устаревшего main, а не моих изменений. |
| **UX / User Flow** | Агент собирается запустить тесты → triggers `branch.staleness_check` → fetch origin → если behind > N → emit `branch.stale_against_main` event + попытка `merge-forward` recipe → при успехе продолжает; при конфликте — эскалирует с typed-error. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Текущая ветка `feature/X` отстаёт от `origin/main` на 12 коммитов; ни одного коммита впереди по этим 12. Конфликтов нет. |
| **When** | Агент инициирует staleness check перед `cargo test --workspace`. |
| **Then** | (1) `git fetch origin main` выполняется (с timeout); (2) Расчёт `commits_behind = 12, commits_ahead = ?`; (3) Эмитится событие `branch.stale_against_main { commits_behind: 12, last_main_sha, threshold }`; (4) Recipe `merge_forward_main` запускается: `git merge --no-edit origin/main`; (5) При успехе записывается `recovery.attempt { recipe: merge_forward_main, outcome: success }`; тесты идут дальше. |
| **Input** | Текущее состояние ветки + `origin/main` |
| **Output** | События `branch.stale_against_main` и `recovery.attempt`; merge-commit в текущей ветке |
| **State** | Ветка fast-forwarded (или merged); recovery ledger обновлён |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | Staleness threshold конфигурируется (default = 5 коммитов); проверяется перед `cargo test --workspace` и `cargo build --workspace`. |
| FR-2 | `merge-forward` recipe: пытается `git merge --no-edit --no-ff origin/main`; при конфликте откатывает (`git merge --abort`) и эскалирует с typed-error `recovery.merge_conflict`. |
| FR-3 | `git fetch` имеет timeout (default 30 с); failure → emit `network.fetch_failed` и не блокирует следующие проверки. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Staleness check (включая fetch) ≤ 2 секунды на репо ≤ 100 МБ. |
| NFR-2 | Все Git-операции выполняются через библиотеку `git2` или subprocess `git` с явным `GIT_TERMINAL_PROMPT=0`, чтобы не зависнуть на интерактивном auth. |

#### Use Case BDD 2 (Edge: merge conflict — эскалация)

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Ветка `feature/X` отстаёт на 5 коммитов; при merge возникает конфликт в файле `Cargo.toml`. |
| **When** | Recipe `merge_forward_main` пытается merge. |
| **Then** | (1) Конфликт детектится; (2) `git merge --abort` восстанавливает чистое состояние; (3) Recipe возвращает `Escalate { reason: "merge_conflict", files: ["Cargo.toml"] }`; (4) Recovery ledger фиксирует attempt с outcome=`escalate`; (5) Агент получает событие `recovery.escalated { recipe, reason, files }` и решает дальше (просит человека или пробует другой подход). |
| **Input** | Конфликтная ветка |
| **Output** | Escalation event, ledger запись, чистое git-состояние (без residual merge state) |
| **State** | Ветка не модифицирована (`git merge --abort` сработал) |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | При конфликте recipe ОБЯЗАТЕЛЬНО восстанавливает clean state (`git merge --abort`) перед возвратом Escalate. |
| FR-5 | Escalation event содержит: recipe_id, attempt_n, reason, files? (для merge), errno, hint. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | После escalation worker не пытается тот же recipe повторно в этой сессии (deduplication по recipe_id + failure_signature). |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Оркестратор / агент |
| **User Story ID** | US-2 |
| **User Story** | Как оркестратор, я хочу видеть аудит всех recovery-attempts в `recovery-ledger.jsonl` с лимитом попыток на recipe, чтобы понимать паттерны failure'ов и не позволять бесконечный retry-loop. |
| **UX / User Flow** | После каждого attempt — append в `.claw/recovery-ledger.jsonl`. Если recipe попробован уже N раз для той же failure-signature → не запускается, эскалация. Оркестратор может прочитать ledger и построить отчёт "топ-10 recipes по успешности". |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Recipe `trust_gate_resolve` уже попробован 3 раза для текущего worker'а с failure_signature = `trust_required:repo_path_X`; default лимит 3. |
| **When** | Снова возникает та же failure, агент пытается тот же recipe. |
| **Then** | (1) `RecoveryLedger.lookup(recipe_id, signature)` возвращает count = 3; (2) Recipe НЕ запускается; (3) Эмитится `recovery.exhausted { recipe, signature, attempt_history }`; (4) Failure эскалируется. |
| **Input** | Failure event с signature (computed) |
| **Output** | Exhaustion event + escalation; ledger без новой записи (поскольку attempt не делался) |
| **State** | Ledger без изменений; worker помечает failure как requiring human |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | `RecoveryLedger` — append-only JSONL с записями `{ ts, recipe_id, signature, attempt_n, outcome, duration_ms, evidence? }`. |
| FR-7 | Failure-signature вычисляется как hash от `(failure_category, target, errno)` — стабильна между запусками для одинаковых failure'ов. |
| FR-8 | Лимит attempts per (recipe, signature) — конфигурируем, default 3. Превышение → `recovery.exhausted` без attempt'а. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-4 | Lookup в ledger O(log N) через индекс in-memory (подгружается при старте; rebuild при corruption). |
| NFR-5 | Ledger ротируется (например при размере > 10 МБ — архив в `.claw/recovery-ledger.archive/<date>.jsonl`). |

#### Use Case BDD 2 (Recipe coverage)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | В системе зарегистрированы 6 recipes: `trust_gate_resolve`, `prompt_redeliver`, `merge_forward_main`, `mcp_reconnect`, `network_retry_with_backoff`, `context_window_compact`. |
| **When** | Возникает failure из 6 категорий (по одной на каждый recipe). |
| **Then** | (1) Failure classifier (F3) определяет категорию; (2) Реестр recipes находит подходящий по `applicable_to: Vec<FailureCategory>`; (3) Recipe выполняется; outcome → ledger; (4) При success → resume исходной операции; при escalation → typed-error к оркестратору. |
| **Input** | Failure event любой из 6 категорий |
| **Output** | Recovered либо escalated; ledger entry |
| **State** | Если recovered — состояние fixed; если escalated — без изменений |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | Реестр recipes: `register(recipe_id, applicable_to, fn attempt)`. Lookup по failure_category возвращает упорядоченный список recipes. |
| FR-10 | Каждый recipe реализован как pure-function `attempt(failure_evidence) -> Result<RecoveredEvidence, EscalationReason>`; идемпотентен. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-6 | Каждый recipe имеет deterministic-replay тест (записан failure → recipe запускается → ожидаемый outcome). |
| NFR-7 | Время выполнения recipe ≤ 30 секунд (включая I/O); превышение → timeout с outcome=`timeout`. |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Агент / оркестратор |
| **User Story ID** | US-3 |
| **User Story** | Как агент, я хочу различать уровни "зелёности" тестов (targeted vs package vs workspace vs merge-ready) и фиксировать commit provenance/worktree-awareness в каждом ship-событии, чтобы оркестратор знал, действительно ли изменения готовы к merge. |
| **UX / User Flow** | (a) Агент запустил `cargo test -p mycrate` — emit `tests.green { scope: "package", target: "mycrate" }`. (b) После `cargo test --workspace` — `tests.green { scope: "workspace" }`. (c) Перед merge — `tests.green { scope: "merge_ready", evidence: { workspace_clean, no_warn, no_merge_conflict } }`. Каждый commit — `commit.created { sha, source_branch, worktree_path, merge_method }`. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Агент завершил работу: cargo test --workspace зелёный, ветка не stale, нет uncommitted changes. |
| **When** | Агент готов к финальному ship-event. |
| **Then** | (1) Эмитится `commit.created { sha, source_branch, worktree_path, merge_method, commit_range }`; (2) Эмитится `tests.green { scope: "merge_ready", evidence: { workspace_clean: true, branch_fresh: true, no_warnings: true } }`; (3) Оркестратор может смело merge. |
| **Input** | Финальное состояние ветки и теста |
| **Output** | События commit.created + tests.green с merge_ready scope |
| **State** | Branch с фиксированным sha, готов к merge |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | Enum `GreenScope { Targeted, Package, Workspace, MergeReady }`. Каждое test-success event обязан указать scope. |
| FR-12 | `commit.created` содержит: `sha, source_branch, worktree_path, merge_method (squash|rebase|merge), commit_range (base..head)` (US-014 PRD). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-8 | `merge_ready` scope требует выполнения всех evidence-полей; отсутствие любого → автоматический downgrade до `workspace` или `package` с warning. |
| NFR-9 | Все ship-events версионируются schema-version, чтобы потребители могли мигрировать. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Внутренний слой `runtime` + интеграция с git (через `git2` или subprocess) |
| **User Entry Points** | Не имеет прямого UI; интеграция через runtime + telemetry events |
| **Main Screens / Commands** | Просмотр через `claw status` (расширенная) и `claw doctor`; ledger в `.claw/recovery-ledger.jsonl` |
| **Input / Output Format** | Internal API + JSONL events |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `runtime::recovery` (модуль в `runtime` крейте) |
| **Responsibility** | (1) StalenessChecker; (2) RecoveryLedger CRUD + lookup; (3) Реестр recipes + dispatch; (4) Green-ness scope tracker; (5) Commit provenance emitter |
| **Business Logic** | На failure: `classifier(F3) → category → ledger.lookup → if attempts < limit → recipe.attempt → outcome → ledger.append → emit event`. На staleness: `git fetch → diff → if stale → recipe → continue`. |
| **API / Contract** | `pub fn check_staleness() -> StalenessReport`; `pub fn try_recover(failure) -> RecoveryOutcome`; `pub fn record_attempt(...)`; `pub fn emit_commit_created(...)` |
| **Request Schema** | `Failure { category, target, errno, evidence }`; `StalenessReport { commits_behind, last_main_sha, threshold }` |
| **Response Schema** | `RecoveryOutcome { recipe_id, status: recovered/escalate/exhausted, evidence, duration_ms }` |
| **Error Handling** | Recipe failure ≠ паника; всегда возвращается `EscalationReason`. Git operations с timeout, при неудаче emit `network.fetch_failed`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Recipe`, `RecoveryAttempt`, `Failure`, `FailureSignature`, `StalenessReport`, `GreenScope`, `CommitProvenance` |
| **Relationships (ER)** | `Failure` 1—1 `FailureSignature`; `Recipe` N—M `FailureCategory` (applicable_to); `RecoveryAttempt` 1—1 `Recipe`; `CommitProvenance` 1—1 `commit.created event` |
| **Data Flow (DFD)** | `runtime` пытается op → exception → `classifier(F3)` → `recovery.try_recover()` → recipe → outcome → ledger.append → telemetry.emit. Перед тестами: `staleness.check() → if stale → recipe.merge_forward → telemetry.emit`. |
| **Input Sources** | Failure events from runtime; git state (origin/main, HEAD); config (`recovery.attempt_limit`, `staleness.threshold`) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Git ≥ 2.30 (или библиотека `git2`); доступ к remote `origin/main` через SSH или HTTPS |
| Файловая система: место под `.claw/recovery-ledger.jsonl` (append-only, ротация) |
| Сеть для git-fetch с timeout |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | StalenessChecker (git fetch + diff) + recipe `merge_forward_main` | F3 (events), F7 (telemetry) | Staleness check ≤ 2 с; merge-forward recipe работает на чистом fast-forward | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Conflict-handling в merge-forward + escalation event | T-1 | Конфликт корректно abort'ится; escalation event эмитится | ST-4, ST-5 |
| UC-2.1 | T-3 | RecoveryLedger (JSONL append-only + index + ротация + лимит attempts) | F3 | Lookup O(log N); attempt_limit срабатывает; ротация не теряет данные | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Реестр recipes + 6 базовых recipes + integration с classifier (F3) | T-3, F3 | Все 6 recipes имеют replay-тесты; lookup по category работает | ST-9, ST-10 |
| UC-3.1 | T-5 | GreenScope tracker + commit provenance emitter + расширение ship-events | F7 (events) | Schema events содержит scope/provenance; merge_ready валидируется | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | StalenessChecker: интеграция с git (через `git2` или subprocess `git`), `fetch origin main` с timeout, расчёт `commits_behind/ahead`, эмиссия `branch.stale_against_main` event при превышении threshold. Recipe `merge_forward_main` для clean fast-forward. |
| **Dependencies** | F3 (worker-state, events), F7 (telemetry) |
| **DoD** | Staleness check ≤ 2 с; интеграционный тест: имитация stale ветки → emit event → recipe → success. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | StalenessChecker с git fetch (timeout 30 с, GIT_TERMINAL_PROMPT=0) | — | Тест с fixture-репо: 3 коммита behind → emit event с commits_behind=3 |
| ST-2 | Расчёт commits_behind/ahead через `git rev-list --count` или `git2::Repository::merge_base` | ST-1 | Тест на коммиты вперёд+назад одновременно |
| ST-3 | Recipe `merge_forward_main` (clean fast-forward path) + эмиссия recovery event | ST-1, ST-2 | Тест: stale ветка с FF-only → recipe → ветка fast-forwarded |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Расширение `merge_forward_main`: handling merge-конфликтов, корректный `git merge --abort`, escalation event с files. |
| **Dependencies** | T-1 |
| **DoD** | Тест с заведомо конфликтным репо: recipe → conflict → abort → escalation event с файлами; ветка clean. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Conflict detection (через `git status --porcelain` после merge) + `git merge --abort` | T-1 | Тест: после abort `git status` чистый |
| ST-5 | Escalation event со списком конфликтных файлов и hint "manual merge required" | T-1 | Schema event содержит `files: Vec<PathBuf>`; integration-тест |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | `RecoveryLedger` — append-only JSONL `.claw/recovery-ledger.jsonl`, in-memory индекс по (recipe_id, signature) → attempt_count, ротация при размере > 10 МБ, attempt_limit (default 3). |
| **Dependencies** | F3 |
| **DoD** | Lookup O(log N) на 100K записей; ротация без потери; corruption recovery (skip invalid line). |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Append-only writer + потоковый parser | — | Crash-тест: kill в момент append → restart парсит все валидные строки |
| ST-7 | In-memory индекс (BTreeMap<(recipe_id, signature), Vec<AttemptRecord>>) + lookup | ST-6 | Lookup в 100K записей ≤ 10 мс |
| ST-8 | Ротация при > 10 МБ (move в `.claw/recovery-ledger.archive/<date>.jsonl`) + конфигурация attempt_limit | ST-6 | Тест: > 10 МБ → создан архив + новый ledger |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Реестр recipes + реализация 6 базовых: `trust_gate_resolve`, `prompt_redeliver`, `merge_forward_main` (из T-1/T-2), `mcp_reconnect`, `network_retry_with_backoff`, `context_window_compact`. Интеграция с failure classifier (F3). |
| **Dependencies** | T-3, F3 |
| **DoD** | Каждый recipe имеет deterministic-replay test (записанный failure → ожидаемый outcome). 70%+ покрытие categories. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Trait `Recipe` + реестр + dispatcher по failure_category | T-3, F3 | Lookup возвращает корректный recipe; missing → escalation |
| ST-10 | Реализация 5 рецептов (без merge_forward — он в T-1/T-2): trust_gate, prompt_redeliver, mcp_reconnect, network_retry, context_window_compact | T-3 | Каждый recipe имеет replay-тест с captured failure |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Enum `GreenScope` (Targeted/Package/Workspace/MergeReady) — обязательное поле test-success events. CommitProvenance emitter — поля `sha/source_branch/worktree_path/merge_method/commit_range` (US-014 PRD). |
| **Dependencies** | F7 (event schema) |
| **DoD** | Schema events версионирована; `merge_ready` требует evidence-полей и валидируется. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | GreenScope enum + интеграция в test-success events; downgrade при отсутствии evidence | F7 | Тест: emit с merge_ready без evidence → downgrade до workspace + warning |
| ST-12 | CommitProvenance: получение sha/source_branch/worktree_path/merge_method из git; emit event | F7, T-1 | Snapshot-тест: после commit emit содержит все поля |
