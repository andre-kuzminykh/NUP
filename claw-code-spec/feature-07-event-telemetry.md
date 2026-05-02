# SPEC — Feature 7: Event Schema & Telemetry (Clawhip Integration)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Event Schema & Telemetry (Clawhip Integration) |
| **Description (Goal / Scope)** | Phase 2 ROADMAP: каноническая типизированная схема lane-событий (started/ready/blocked/green/commit.created/…) для clawhip-оркестратора, заменяющая парсинг log-prose. Включает: monotonic ordering с causal metadata, event provenance (live_lane/test/replay/transport), session identity (stable title/workspace/purpose), deduplication через fingerprints, schema versioning, consumer capability negotiation, projection/redaction по sensitivity labels, audience-specific report views (clawhip / Jobdori / humans). Вне скоупа: бизнес-логика recovery (F6), MCP плагины (F8). |
| **Client** | clawhip оркестратор (consumes events для роутинга), Jobdori (HR/business-side dashboards), human reviewers; внутренние слои — telemetry crate. |
| **Problem** | Парсинг prose из логов хрупок: добавление нового warning в формате модели ломает парсер. Без monotonic ordering клиенты не понимают, какое событие "последнее". Без provenance трудно отличить, что live от теста — это приводит к ложным алертам. Без аудиенс-views один и тот же event либо перегружает humans технической детализацией, либо лишает clawhip нужных машинных полей. |
| **Solution** | (1) Каноническая JSON-Schema всех lane-событий с обязательным `schema_version`, `lane_id`, `seq` (monotonic), `caused_by?` (causal); (2) `provenance: { source: live_lane|test|replay|transport, environment }`; (3) Session identity с обязательным title/workspace/purpose в каждом event; (4) Deduplication: при повторном emit с тем же fingerprint и terminal-state — подавление; (5) Capability negotiation: consumer объявляет supported_versions, producer выбирает overlap; (6) Sensitivity labels: `public/internal/secret`; redactor применяет правила перед outbound emission per-audience; (7) Multi-message report atomicity (несколько events рассматриваются как одна транзакция). |
| **Metrics** | (1) 0 событий с пропущенным `seq` или `lane_id` (assertion в emit); (2) Schema-version mismatch обрабатывается с graceful degradation; (3) Deduplication подавляет ≥ 100% повторных terminal events; (4) Latency emit → consumer ≤ 100 мс; (5) ≥ 3 audience-views (clawhip, jobdori, humans) с разной project'ией. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Clawhip-оркестратор |
| **User Story ID** | US-1 |
| **User Story** | Как оркестратор, я хочу получать lane-события по типизированной схеме с monotonic seq и causal links, чтобы строить надёжный state-machine для каждой lane без парсинга prose. |
| **UX / User Flow** | Worker эмитит event → telemetry-crate сериализует под канонической схемой → транспорт (file/socket/HTTP) → clawhip получает stream events → строит state per lane_id, упорядочивая по seq. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Clawhip-оркестратор подписан на lane `lane-42`. Worker запускается и проходит lifecycle. |
| **When** | Worker эмитит серию events: `lane.started → lane.ready → lane.commit.created → lane.green (scope=workspace) → lane.finished`. |
| **Then** | (1) Каждое событие имеет `lane_id="lane-42"`, монотонный `seq` (1,2,3,4,5), `schema_version`, `provenance.source="live_lane"`; (2) `caused_by` опционально ссылается на seq предыдущего события (для causal chains); (3) Clawhip получает события в порядке seq (если транспорт upset порядок — клиент сортирует по seq); (4) После `lane.finished` event с `terminal=true` — последующие emits с тем же lane_id игнорируются (deduplication). |
| **Input** | Серия emit-вызовов в worker'е |
| **Output** | Stream events с обязательными полями; deduplicated terminal-events |
| **State** | Clawhip lane state = `finished`; revision строго возрастает |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | Каждое event обязано иметь: `schema_version (semver), event_type, lane_id, seq (u64 monotonic per lane), ts (RFC3339), provenance, identity, payload`. |
| FR-2 | `seq` генерируется атомарно (per-lane counter); revision и persists между процессами через `.claw/lanes/<lane_id>/seq` файл. |
| FR-3 | События с `terminal=true` (например `lane.finished`, `lane.failed`) триггерят deduplication: повторные emits с тем же `event_type` и тем же `terminal_signature` подавляются с warning (US-019 PRD). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Latency emit → consumer (in-process subscriber) ≤ 100 мс при нагрузке ≤ 1000 events/sec. |
| NFR-2 | Outbound transport — pluggable (default = JSONL файл, опционально HTTP webhook); сбой транспорта не должен ронять worker. |

#### Use Case BDD 2 (Causal links + multi-message atomicity)

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Worker готов отчитаться по комплексному report'у: `task.completed` → triggers `tests.green` + `commit.created` + `lane.finished` (3 связанных события). |
| **When** | Worker вызывает `report.atomic([ev1, ev2, ev3])`. |
| **Then** | (1) Все 3 events эмитятся как одна транзакция (US-015 PRD multi-message atomicity); (2) Каждый имеет `caused_by: <task.completed seq>`; (3) Если транспорт частично fails — повторная попытка отправляет всю transaction (idempotency через transaction_id); (4) Consumer гарантированно видит все 3 или ни одного. |
| **Input** | `report.atomic(events)` |
| **Output** | Атомарная отправка/повторная отправка |
| **State** | Consumer не видит частичный set events |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | API `report.atomic(transaction_id, events: Vec<Event>)` — атомарная отправка через write-ahead log; до полного ack транспорта не помечается finalized. |
| FR-5 | Causal chain: `caused_by: { event_type, seq }` опциональный — позволяет восстановить DAG триггеров. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | Atomic transactions размером ≤ 50 events; превышение → ошибка `report.too_large`. |
| NFR-4 | Write-ahead log (WAL) ротируется по размеру (10 МБ); восстановление при рестарте дочитывает unfinalized transactions и повторно отправляет. |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Клиент-консьюмер (clawhip / Jobdori / human dashboard) |
| **User Story ID** | US-2 |
| **User Story** | Как консьюмер событий, я хочу объявить свой supported schema_version и audience-tag, чтобы получать только релевантные поля и предотвращать "unknown field" ошибки при schema-evolution. |
| **UX / User Flow** | Consumer при handshake: `subscribe(audience, supported_schema_versions: ["1.x", "2.x"])` → producer выбирает overlap → projects events под нужный audience (например humans видят human-readable summary, clawhip видит machine fields, Jobdori — только бизнес-метрики). |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Producer support schema 2.1; consumer A объявляет `["1.x"]`, consumer B — `["2.x"]`. |
| **When** | Worker эмитит event 2.1. |
| **Then** | (1) Для consumer A: producer downgrade event до 1.x (drop неизвестных полей, конвертация известных); (2) Для consumer B: event 2.1 без изменений; (3) Если negotiation невозможен (нет overlap) — consumer получает `subscription.incompatible_schema` и не подписан. |
| **Input** | Event 2.1, два consumer'а с разными версиями |
| **Output** | Versioned events per consumer |
| **State** | Capability negotiation cached на subscription |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | Capability handshake API: `subscribe(audience, supported_versions, sensitivity_max) -> SubscriptionToken`. |
| FR-7 | Schema-versioning через semver; downgrade-функции реализованы для смежных major (2.x → 1.x); невозможный downgrade → событие НЕ доставляется этому consumer'у с warning. |
| FR-8 | Если у consumer нет overlap — explicit error `subscription.incompatible_schema` с hint о supported versions. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-5 | Downgrade per-event ≤ 1 мс (lookup в map конвертеров). |
| NFR-6 | Schema evolution: removing fields в next major запрещено (только добавление nullable полей в minor). |

#### Use Case BDD 2 (Sensitivity-based redaction)

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Event содержит поле `error.evidence.api_key_hint` с sensitivity=`secret`. Consumer humans подписан с `sensitivity_max=internal`. |
| **When** | Producer проектирует event для humans audience. |
| **Then** | (1) Поля с sensitivity > sensitivity_max редактируются (replaced с `<redacted>` + label); (2) Структура event сохраняется; (3) Для clawhip с sensitivity_max=secret — поле передаётся as-is (если есть legitimate need); (4) Redaction логируется в audit-log. |
| **Input** | Event с mixed sensitivity, два consumer'а |
| **Output** | Per-audience version event; audit-log redaction |
| **State** | Audit-log обновлён |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | Каждое поле события размечается `sensitivity: public|internal|secret`; redactor применяет правила перед emission. |
| FR-10 | Audit-log redaction events: `{ ts, audience, redacted_paths: Vec<JsonPointer>, reason }`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-7 | Redaction policy конфигурируется в `~/.claw/telemetry-policy.json`; default: humans=internal, clawhip=secret, jobdori=public. |
| NFR-8 | Redaction не должен изменять JSON-схему event (поля присутствуют, значения заменены) — это предотвращает downstream parsing-ошибки. |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | DevOps / разработчик |
| **User Story ID** | US-3 |
| **User Story** | Как DevOps, я хочу различать события из live-окружения, тестов и replay-runs через `provenance` поле, чтобы не путать алертинг и не загрязнять production-метрики тестовыми event'ами. |
| **UX / User Flow** | Каждое event имеет `provenance: { source: live_lane|test|replay|transport, environment: "prod"|"staging"|"dev"|"ci" }`. Алерт-rules фильтруют по `source=live_lane && environment=prod`. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Запускается harness тестов: `./scripts/run_mock_parity_harness.sh` в CI. Также параллельно работает live-worker в production. |
| **When** | Оба эмитят `lane.green` events. |
| **Then** | (1) Live: `provenance: { source: "live_lane", environment: "prod" }`; (2) Test: `provenance: { source: "test", environment: "ci", test_run_id: "..." }`; (3) Алертинг dashboard фильтрует на `source=live_lane && environment=prod` — видит только live; (4) Replay (`./scripts/replay_session.sh <id>`): `provenance.source=replay` — отдельный канал. |
| **Input** | События из разных контекстов |
| **Output** | Differentiated streams |
| **State** | Метрики/алерты разделены |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | `provenance.source` — обязательный enum: `live_lane`, `test`, `replay`, `transport`. `environment` опциональный string. |
| FR-12 | Test-run автоматически устанавливает `provenance` через env-var или флаг `--provenance test`; без явного override — `live_lane`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-9 | `provenance` нельзя подменить из payload event'а — устанавливается telemetry-слоем централизованно. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Pluggable transport — JSONL файл (default), HTTP webhook, custom; consumer-side: clawhip, Jobdori, humans dashboard |
| **User Entry Points** | Не имеет direct UI; настройка через `~/.claw/telemetry-policy.json` и `--telemetry-transport <url>` flag |
| **Main Screens / Commands** | `claw status` показывает recent events (опционально), `.claw/telemetry/events.jsonl` |
| **Input / Output Format** | JSONL events под schema-version |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `telemetry` crate |
| **Responsibility** | (1) Реестр event-types + schema; (2) Emission API с monotonic seq; (3) WAL для atomic transactions; (4) Capability negotiation; (5) Redactor; (6) Pluggable transports; (7) Subscription management (in-process + remote) |
| **Business Logic** | На emit: assign seq, fill identity/provenance, validate schema → WAL append → transports.dispatch(per-subscription) → on ack, finalize WAL entry. |
| **API / Contract** | `pub fn emit(event)`; `pub fn report.atomic(tx_id, events)`; `pub fn subscribe(audience, versions, sensitivity_max) -> Token`; `pub fn unsubscribe(token)` |
| **Request Schema** | `Event { schema_version, event_type, lane_id, seq, ts, provenance, identity, payload, sensitivity_map?, terminal? }` |
| **Response Schema** | Subscription stream events (per audience/version) |
| **Error Handling** | Schema validation errors — паника в debug, log+drop в release. Transport failure — retry с backoff, persist в WAL. Subscription incompatible — typed error. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Event`, `EventType`, `LaneId`, `Provenance`, `SessionIdentity`, `Subscription`, `Audience`, `SensitivityLabel`, `WALEntry`, `Transport` |
| **Relationships (ER)** | `Lane` 1—N `Event`; `Event` 1—1 `Provenance`; `Event` 1—1 `SessionIdentity`; `Event` 0—1 `caused_by Event`; `Subscription` 1—1 `Audience`; `Subscription` 1—N `Event` |
| **Data Flow (DFD)** | `runtime.emit()` → `telemetry.assign_seq+enrich` → `validate_schema` → `WAL.append` → `dispatch_to_subscriptions` (per-audience project + redact + downgrade) → `transport.send` → `WAL.finalize` |
| **Input Sources** | События от runtime/tools/recovery (F4/F6), session identity (F5), worker state (F3) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Файловая система с поддержкой O_APPEND для WAL и events.jsonl (≤ 10 МБ ротируемый файл) |
| Опционально: HTTP-эндпоинт для outgoing webhook (clawhip server) |
| Опционально: Unix socket для local subscriber'ов |
| RAM: ≤ 50 МБ под буферы и индексы subscriptions |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Каноническая schema events + monotonic seq + dedup terminal events | crate `telemetry` | Schema-валидация, seq монотонна, dedup работает | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Multi-message report atomicity (WAL + idempotent retry) | T-1 | Atomic transaction либо доходит вся, либо никогда | ST-4, ST-5 |
| UC-2.1 | T-3 | Capability negotiation + version downgrade map | T-1 | Subscription handshake + downgrade unit-tested | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Sensitivity labels + redactor + audit-log | T-1 | Redaction по sensitivity_max работает, audit пишется | ST-9, ST-10 |
| UC-3.1 | T-5 | Provenance enforcement + pluggable transports + audience-views | T-1 | Provenance нельзя подменить; 3+ audience с разными views | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Дизайн каноническая JSON-Schema events; реализация emission API с monotonic seq (per-lane, persisted в `.claw/lanes/<id>/seq`); deduplication terminal events; valid required fields. |
| **Dependencies** | crate `telemetry` |
| **DoD** | Schema валидируется; seq монотонна и persists между процессами; dedup terminal-events не теряет non-terminal. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | JSON-Schema events + Rust-структуры + serde-derive | — | Все обязательные fields validated; round-trip JSON; snapshot-тесты |
| ST-2 | Monotonic seq generator (per-lane, persistent file lock) | ST-1 | Concurrent emit'ы не дают пропусков и дубликатов; restart продолжает с последнего seq+1 |
| ST-3 | Dedup terminal events (через signature hash) | ST-1, ST-2 | Repeat emit terminal event → suppressed + warning, non-terminal — passes |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | `report.atomic(transaction_id, events)` API; WAL `.claw/telemetry/wal.jsonl`; idempotent retry при transport failure; finalize только после ack. |
| **Dependencies** | T-1 |
| **DoD** | Crash-тест: kill в момент send → restart дочитывает WAL и повторно отправляет; consumer не видит частично; idempotency через transaction_id. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | WAL writer/reader; recovery on startup | T-1 | Recovery dochnoavnaet unfinalized → re-dispatch |
| ST-5 | Atomic API + idempotency через transaction_id (consumer dedup) | ST-4 | Тест: повторная доставка той же transaction → consumer видит один раз |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Capability handshake API; реестр downgrade-функций между schema versions; ошибка при no-overlap. |
| **Dependencies** | T-1 |
| **DoD** | Subscription с supported_versions работает; downgrade покрыт unit-тестами; incompatibility → typed-error. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | API `subscribe(audience, supported_versions, sensitivity_max) -> Token` | T-1 | Token unique; unsubscribe чистит ресурсы |
| ST-7 | Реестр downgrade-функций (semver-based lookup) | T-1 | Lookup за O(log N); downgrade-функция round-trip-stable |
| ST-8 | Negotiation logic + error reporting на no-overlap | ST-6, ST-7 | Тест: subscriber 1.x + producer 3.x → typed-error |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | `sensitivity` поле per-event-field (через JSON-pointer map); redactor применяется при dispatch per-subscription; audit-log в `.claw/telemetry/redactions.jsonl`. |
| **Dependencies** | T-1, T-3 |
| **DoD** | Redaction корректна; audit-log пишется; structure event сохраняется. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Sensitivity map + redactor (replace value, keep key) | T-1 | Redacted поле имеет `<redacted>` placeholder + sensitivity-tag |
| ST-10 | Audit-log writer + конфигурация policy в `~/.claw/telemetry-policy.json` | T-3, ST-9 | Snapshot-тест: humans видит redacted, clawhip — full |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Provenance enforcement (нельзя установить через payload, только telemetry); pluggable transports (JSONL/HTTP/Unix-socket); 3 audience-views (clawhip, jobdori, humans) с разными projection-функциями. |
| **Dependencies** | T-1, T-3, T-4 |
| **DoD** | Provenance защищён; transports переключаемы; каждая audience имеет documented projection. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Provenance enforcement (private setter в telemetry, не в payload struct) | T-1 | Попытка set provenance из payload → compile-error/паника |
| ST-12 | Pluggable transports + 3 audience projection functions | T-3, T-4 | Smoke-тест: один event эмитится, 3 audience получают разные shape; HTTP + JSONL transport работают |
