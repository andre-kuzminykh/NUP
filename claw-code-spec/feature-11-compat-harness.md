# SPEC — Feature 11: Compat-Harness (Tool Manifest Extraction & Mock Parity)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Compat-Harness — извлечение tool-манифестов из исходного кода + Mock LLM Parity Harness |
| **Description (Goal / Scope)** | Крейт `compat-harness` (зависит от `commands`, `tools`, `runtime`) — внутренний тестовый каркас, обеспечивающий: (1) **извлечение tool-манифестов** (имя, JSON-Schema, описание) прямо из `tools` crate без дублирования спецификаций — single source of truth для system-prompt'а и тестов; (2) **Mock LLM Parity Harness** — детерминированный mock Anthropic API + 10 сценариев (`mock_parity_scenarios.json`) + 19 captured API requests + сравнение фактических vs ожидаемых запросов; (3) скрипт `./scripts/run_mock_parity_harness.sh` для CI. Вне скоупа: production providers (F2), сами tools (F4). |
| **Client** | CI-системы (regression-тесты), разработчики (локальный run перед PR), F8 plugin discovery (использует extracted manifests). |
| **Problem** | Без extraction tool-манифесты пришлось бы дублировать в коде и тестах — рассинхрон неизбежен. Без detereministic mock harness регрессии в API-форматировании (например, странный escape, missing field) обнаруживаются только в продакшене. |
| **Solution** | (1) Extractor использует `inventory`/`linkme`-style сбор `Tool::schema()` со всех зарегистрированных tools при компиляции; (2) Mock-сервер реагирует на запросы по hash-lookup в captured-кэше; (3) Harness: запускает 10 сценариев с тестовыми prompts, сверяет фактические HTTP-запросы с captured `expected_requests.json` через нормализованный JSON-diff. |
| **Metrics** | (1) 100% tools имеют manifest, извлекаемый автоматически; (2) Harness 10/10 сценариев зелёный за ≤ 30 секунд; (3) При расхождении — точный diff с указанием поля; (4) Mock-сервер старт ≤ 200 мс. |

## 2. User Stories and Use Cases

### US-1: Tool manifest extraction (single source of truth)

| Field | Value |
|---|---|
| **Role** | Разработчик / runtime |
| **User Story** | Как разработчик, я хочу получать tool-манифесты автоматически из исходного кода `tools` crate, чтобы не дублировать JSON-Schema в system-prompt и тестах. |

**UC-1.1: Extract all tools at compile time.** Given в `tools` crate определены 6 tools — Bash/Read/Write/Edit/Grep/Glob → When `compat-harness` собирается → Then extractor собирает все impls `Tool` через `inventory::submit!` или аналог → доступен `pub fn all_tools() -> Vec<ToolManifest>` для runtime и тестов.

**FR-1:** Каждая `impl Tool` помечается атрибутом/макросом, регистрирующим её в global registry (`inventory::collect!`). **FR-2:** ToolManifest = `{name, description, input_schema: JsonSchema, output_schema?, sensitivity?}`. **NFR-1:** Extraction zero-cost runtime (всё на этапе компиляции). **NFR-2:** Добавление нового tool без изменения compat-harness — auto-discovery.

**UC-1.2: Manifest export for system-prompt.** Given runtime готовит system-prompt → When нужен список tools для модели → Then используется `compat_harness::export_for_anthropic()` — конвертирует ToolManifest в формат Anthropic Messages API tools-array.

**FR-3:** Per-provider exporters: `export_for_anthropic`, `export_for_openai`, `export_for_dashscope` (схемы немного различаются). **FR-4:** Snapshot-тест: фиксированный набор tools → стабильный JSON-output (regression-guard).

### US-2: Mock LLM сервис (детерминированные ответы)

| Field | Value |
|---|---|
| **Role** | CI / разработчик |
| **User Story** | Как тестовая среда, я хочу in-process mock Anthropic API, который возвращает заранее записанные ответы по hash от запроса, чтобы integration-тесты были полностью offline и детерминированными. |

**UC-2.1: Mock server lookup by request hash.** Given `mock-anthropic-service` запущен на эфемерном порту → When `claw` отправляет `POST /v1/messages` с body `{...}` → Then mock хеширует normalized body → ищет в `mock_parity_scenarios.json` → возвращает captured response (включая SSE-streaming). Если hash не найден → 404 с понятной ошибкой "no captured fixture".

**FR-5:** Lookup по hash от `(model, normalized_messages, normalized_tools)` — стабилен между запусками. **FR-6:** Поддержка SSE-streaming: captured response парсится как массив events, эмитится с реалистичным timing (например 10 мс между chunks). **NFR-3:** Mock старт ≤ 200 мс; in-process (Tokio + axum/hyper). **NFR-4:** Параллельные тесты могут использовать общий mock через unique hash space (per-test session).

**UC-2.2: Add new captured fixture.** Given разработчик добавил новую функциональность → When нужен новый сценарий → Then команда `./scripts/capture_fixture.sh "test prompt"` ходит в реальный API, записывает request+response в `captured/<scenario>.json`, добавляет entry в `mock_parity_scenarios.json`.

**FR-7:** Capture-script использует переменную `ANTHROPIC_API_KEY` для real-API call, normalizes timestamps/IDs перед сохранением. **NFR-5:** Captured fixtures редактируемы вручную (JSON), git-friendly.

### US-3: Parity harness — сравнение фактических vs expected запросов

| Field | Value |
|---|---|
| **Role** | CI |
| **User Story** | Как CI, я хочу запустить полный harness одной командой, который прогонит 10 сценариев, проверит, что claw отправляет именно те HTTP-запросы, которые ожидаются, и упадёт с понятным diff при расхождении. |

**UC-3.1: Full harness run.** Given чистая среда → When запущен `./scripts/run_mock_parity_harness.sh` → Then: (1) поднимается mock-сервер; (2) запускаются 10 сценариев из `mock_parity_scenarios.json` (streaming_text, read_file_roundtrip, grep_chunk_assembly, write_file_allowed, …); (3) каждый запускает `claw` бинарь с фиксированным prompt и сверяет фактические запросы с expected; (4) выводится сводка `10/10 passed (took 24s)`; exit 0 при успехе.

**FR-8:** Каждый сценарий имеет: `prompt`, `expected_requests: Vec<RequestSnapshot>`, `expected_responses: Vec<ResponseSnapshot>`, `expected_exit_code`, `expected_stdout_contains?`. **FR-9:** Diff: при расхождении печатается unified JSON-diff с цветной разметкой полей; ключи отсортированы для стабильного сравнения. **NFR-6:** Harness занимает ≤ 30 секунд на dev-машине; параллелизация сценариев допустима (если нет shared state).

**UC-3.2: Single scenario debug mode.** Given разработчик отлаживает конкретный сценарий → When `./scripts/run_mock_parity_harness.sh --only streaming_text --verbose` → Then запускается только этот сценарий с подробным логом всех запросов/ответов.

**FR-10:** CLI флаги harness: `--only <name>`, `--verbose`, `--no-parallel`, `--update-fixtures` (опасный — обновляет captured fixtures). **NFR-7:** `--update-fixtures` требует подтверждения (либо env `CLAW_HARNESS_UPDATE=1`).

## 3. Architecture / Solution

| Area | Fill In |
|---|---|
| **Client Type** | CLI скрипт + in-process Rust-программа (test binary) |
| **Backend** | `compat-harness` crate (зависит от `commands`, `tools`, `runtime`) + `mock-anthropic-service` crate |
| **Data Flow** | Extractor: build-time scan → static registry. Harness: scenarios.json → spawn `claw` → intercept HTTP via mock URL → diff → report. |
| **Files** | `mock_parity_scenarios.json` (10 сценариев), `captured/<scenario>.json` (request/response снапшоты), `scripts/run_mock_parity_harness.sh`, `scripts/capture_fixture.sh` |
| **Infra** | Tokio runtime для mock-сервера; эфемерный порт; никакой сети наружу |

## 4. Work Plan

| UC | Task | DoD | Subtasks |
|---|---|---|---|
| UC-1.1, UC-1.2 | T-1: Tool manifest extraction (inventory-style) + per-provider exporters | Все 6 tools auto-discoverable; snapshot-тесты на export | ST-1, ST-2, ST-3 |
| UC-2.1 | T-2: Mock anthropic service (hash-lookup, SSE) | Mock старт ≤ 200 мс; lookup стабилен | ST-4, ST-5 |
| UC-2.2 | T-3: Capture script для новых fixtures | Один скрипт с `ANTHROPIC_API_KEY` записывает fixture | ST-6, ST-7, ST-8 |
| UC-3.1 | T-4: Harness runner — 10 сценариев + JSON-diff | 10/10 passed ≤ 30 с | ST-9, ST-10 |
| UC-3.2 | T-5: CLI флаги (`--only`, `--verbose`, `--update-fixtures`) | Single-scenario debug режим работает | ST-11, ST-12 |

## 5. Detailed Task Breakdown

**T-1 / Manifest extraction.** ST-1: атрибут/макрос `#[derive(Tool)]` с автo-регистрацией; ST-2: `all_tools() -> Vec<ToolManifest>`; ST-3: per-provider exporters + snapshot-тесты.
**T-2 / Mock service.** ST-4: hyper/axum сервер на эфемерном порту, JSON-lookup по hash; ST-5: SSE-replay с realistic timing.
**T-3 / Capture script.** ST-6: real API call wrapper; ST-7: normalization (strip timestamps/IDs); ST-8: append в `mock_parity_scenarios.json`.
**T-4 / Harness runner.** ST-9: scenario executor (spawn `claw` с mock URL); ST-10: JSON-diff с unified-format output.
**T-5 / CLI флаги.** ST-11: `--only <name>` и `--verbose` парсинг; ST-12: `--update-fixtures` с safe-guard (требует env confirm).
