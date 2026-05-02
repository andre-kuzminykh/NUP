# SPEC — Feature 2: Multi-Provider AI Integration

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Multi-Provider AI Integration & Routing |
| **Description (Goal / Scope)** | Унифицированный API-слой (`api` crate) для общения с несколькими LLM-провайдерами: Anthropic (direct), xAI (Grok), OpenAI-compatible (OpenRouter, Ollama, локальные сервисы), DashScope/Alibaba (Qwen, Kimi). Включает: SSE-стриминг, аутентификацию через несколько схем, маршрутизацию по префиксам моделей, model aliases, model-specific quirks (kimi-k2.5 без `is_error`, лимиты токенов), proxy-конфигурация, mock-сервис для тестов. Вне скоупа: реализация tools (F4), сессионная логика (F5). |
| **Client** | `runtime` crate (отправляет turns через `api`); тесты parity (`compat-harness`); пользователи через slash-команду `/model`. |
| **Problem** | В реальной разработке требуются разные модели (по цене, скорости, контексту, юрисдикции). Каждый провайдер имеет уникальный auth-формат, request/response schema, лимиты, провижн-quirks. Без унифицированного слоя пользователь должен переписывать клиент. |
| **Solution** | (1) Trait `Provider` с методами `send`, `stream`, `count_tokens`; (2) Конкретные имплементации: `AnthropicProvider`, `XaiProvider`, `OpenAiCompatProvider`, `DashScopeProvider`; (3) Router выбирает provider по префиксу model id (`openai/`, `gpt-`, `qwen/`, `qwen-`, `kimi-`, `grok`, `claude-`); (4) Реестр aliases (`opus`, `sonnet`, `haiku`, `grok`, …) → конкретные model id; (5) Таблица quirks (kimi-k2.5: исключить `is_error`, max body 6 MB, 256K context / 16K out); (6) `mock-anthropic-service` крейт — детерминистический local mock для оффлайн тестов. |
| **Metrics** | (1) Все 4 провайдера покрыты integration-тестами с записанными HTTP-запросами; (2) Маршрутизация по префиксу: 100% корректность на тестовом наборе из ≥ 20 model id; (3) Mock-harness: 19 captured API requests, 10 сценариев — все зелёные; (4) Latency overhead routing-слоя ≤ 5 мс на запрос. |

---

## 2. User Stories and Use Cases

### User Story 1

| Field | Value |
|---|---|
| **Role** | Разработчик |
| **User Story ID** | US-1 |
| **User Story** | Как пользователь Claw, я хочу выбирать провайдера через короткий alias или префикс модели, чтобы не запоминать длинные model id и не настраивать клиент вручную. |
| **UX / User Flow** | (a) `claw --model sonnet "..."` → resolved в `claude-sonnet-4-6` → AnthropicProvider; (b) `claw --model grok "..."` → XaiProvider; (c) `claw --model openai/gpt-4o "..."` → OpenAiCompatProvider; (d) `claw --model kimi-k2.5-instruct "..."` → DashScopeProvider. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Пользователь установил `ANTHROPIC_API_KEY`. Список aliases по умолчанию: `opus → claude-opus-4-6`, `sonnet → claude-sonnet-4-6`, `haiku → claude-haiku-4-5-20251213`. |
| **When** | Пользователь запускает `claw --model sonnet "summarize repo"`. |
| **Then** | (1) Резолвер aliases возвращает `claude-sonnet-4-6`; (2) Router определяет provider Anthropic по префиксу `claude-`; (3) Запрос отправляется через `AnthropicProvider` с заголовком `x-api-key`; (4) SSE-стрим возвращает токены; (5) Telemetry фиксирует `provider=anthropic, model=claude-sonnet-4-6`. |
| **Input** | `--model sonnet`, env `ANTHROPIC_API_KEY=sk-ant-...` |
| **Output** | SSE-stream → текст ответа; usage event `{input_tokens, output_tokens, cached_tokens}` |
| **State** | Сессия содержит turn с `model=claude-sonnet-4-6, provider=anthropic` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-1 | Резолвер aliases читает встроенный default-mapping и накладывает overrides из `~/.claw/settings.json` или `<repo>/.claw/settings.json` (подключается к иерархии конфигов). |
| FR-2 | Router работает по списку префиксов с приоритетом: явный prefix (`openai/`) > model name prefix (`gpt-`, `qwen-`, `kimi-`, `grok`) > fallback Anthropic. |
| FR-3 | Префикс-маршрутизация имеет приоритет над переменными окружения (US-021/024 PRD). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-1 | Резолвер aliases выполняет lookup за O(1); routing — за O(K), где K = число префиксов (≤ 20). |
| NFR-2 | Все провайдеры используют один общий retry-policy (exponential backoff, max 5 retries, base 500 мс) при `429`/`5xx`. |

#### Use Case BDD 2

| Field | Value |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Пользователь определил кастомный alias `my-fast: openai/gpt-4o-mini` в `.claw/settings.json`. |
| **When** | Пользователь запускает `claw --model my-fast "ping"`. |
| **Then** | (1) Резолвер возвращает `openai/gpt-4o-mini`; (2) Router определяет провайдера по префиксу `openai/` → OpenAiCompatProvider; (3) Используется `OPENAI_API_KEY` + `OPENAI_BASE_URL` (или дефолтный OpenRouter URL); (4) Запрос идёт с заголовком `Authorization: Bearer <token>`. |
| **Input** | `--model my-fast`, env `OPENAI_API_KEY=sk-…`, `OPENAI_BASE_URL=https://openrouter.ai/api/v1` |
| **Output** | Стрим ответа от OpenRouter; usage events с конвертацией формата в общий envelope |
| **State** | Telemetry: `provider=openai_compat, model=openai/gpt-4o-mini, base_url=...` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-4 | OpenAI-compat провайдер конвертирует Anthropic-style requests/responses ↔ OpenAI Chat Completions API; tool-call schemas мапятся 1:1. |
| FR-5 | `OPENAI_BASE_URL` переопределяет дефолтный URL; при отсутствии — используется встроенный default (например `https://openrouter.ai/api/v1`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-3 | OpenAI-compat провайдер должен корректно работать с локальным Ollama (`base_url=http://localhost:11434/v1`) без сетевого хост-доступа. |
| NFR-4 | Конвертация формата не должна терять метаданные (`stop_reason`, `usage`, `tool_use_id`). |

---

### User Story 2

| Field | Value |
|---|---|
| **Role** | Разработчик / интегратор |
| **User Story ID** | US-2 |
| **User Story** | Как пользователь, я хочу аутентифицироваться у разных провайдеров через стандартные env vars и опционально OAuth-токен, чтобы не вшивать секреты в код. |
| **UX / User Flow** | Перед запуском `claw` пользователь экспортирует `ANTHROPIC_API_KEY` или `ANTHROPIC_AUTH_TOKEN` (OAuth) или один из `OPENAI_API_KEY`/`XAI_API_KEY`/`DASHSCOPE_API_KEY`. Опционально `ANTHROPIC_BASE_URL`/`HTTPS_PROXY` для прокси. `claw doctor` валидирует их. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | У пользователя есть OAuth-токен (полученный через oauth-flow вне скоупа) в `ANTHROPIC_AUTH_TOKEN`. `ANTHROPIC_API_KEY` не установлен. |
| **When** | Пользователь запускает `claw "test"` с моделью по умолчанию `sonnet`. |
| **Then** | (1) Auth-резолвер обнаруживает `ANTHROPIC_AUTH_TOKEN`, выбирает заголовок `Authorization: Bearer <token>`; (2) Запрос идёт без `x-api-key`; (3) Telemetry фиксирует `auth=oauth`. |
| **Input** | env `ANTHROPIC_AUTH_TOKEN=oat_...` |
| **Output** | Успешный ответ модели |
| **State** | `runtime.auth_mode = OAuth` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-6 | Приоритет credentials для Anthropic: `ANTHROPIC_API_KEY` > `ANTHROPIC_AUTH_TOKEN`; при наличии обоих печатается warning. |
| FR-7 | Каждый провайдер имеет собственный auth-резолвер: Anthropic → `x-api-key`/`Bearer`; xAI → `Bearer XAI_API_KEY`; OpenAI-compat → `Bearer OPENAI_API_KEY`; DashScope → `Bearer DASHSCOPE_API_KEY`. |
| FR-8 | Отсутствие необходимых credentials → typed-error `auth.missing_credentials` с hint, какую env var нужно установить (P1 ROADMAP). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-5 | Секреты никогда не попадают в логи telemetry или session-файлы (redaction слой). |
| NFR-6 | OAuth-токен и API-key хранятся в памяти как `secrecy::Secret<String>` для предотвращения случайного `Debug`-вывода. |

#### Use Case BDD 2

| Field | Value |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Пользователь работает в корпоративной сети с обязательным HTTPS-прокси `http://proxy.corp.example:3128`. |
| **When** | Пользователь экспортирует `HTTPS_PROXY="http://proxy.corp.example:3128"` и `NO_PROXY="localhost,127.0.0.1"`, запускает `claw "..."`. |
| **Then** | (1) HTTP-клиент учитывает `HTTPS_PROXY` для всех outbound-запросов; (2) Запросы к localhost обходят прокси; (3) При программной конфигурации `ProxyConfig { proxy_url, no_proxy }` имеет приоритет над env vars. |
| **Input** | env `HTTPS_PROXY=...`, `NO_PROXY=...`, или `runtime.config.proxy.proxy_url=...` |
| **Output** | Успешный запрос через прокси |
| **State** | HTTP-клиент инстанцирован с настроенным proxy |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-9 | Поддержка `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY` (case-insensitive) и программной `ProxyConfig` структуры. |
| FR-10 | При сбое подключения через прокси возвращается typed-error `network.proxy_unreachable` с информацией об URL прокси. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-7 | Прокси-конфигурация не должна добавлять > 50 мс к латентности первого запроса. |
| NFR-8 | TLS-валидация остаётся включённой при работе через прокси (никаких `dangerous_accept_invalid_certs` по умолчанию). |

---

### User Story 3

| Field | Value |
|---|---|
| **Role** | Тестировщик / разработчик parity-тестов |
| **User Story ID** | US-3 |
| **User Story** | Как разработчик, я хочу запускать тесты против детерминированного mock-сервиса и иметь корректные quirks для конкретных моделей (kimi-k2.5, DashScope), чтобы покрытие было воспроизводимым и без ложных срабатываний на model-specific багах. |
| **UX / User Flow** | (1) `cargo test` поднимает локальный `mock-anthropic-service`, запросы перехватываются; (2) `./scripts/run_mock_parity_harness.sh` гоняет 10 сценариев из `mock_parity_scenarios.json`; (3) При отправке kimi-* модели поле `is_error` исключается; превышение 6 MB body → preflight reject. |

#### Use Case BDD 1

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | В `rust/` запускается `./scripts/run_mock_parity_harness.sh`. Мок-сервис слушает на эфемерном порту, `ANTHROPIC_BASE_URL` указывает на него. |
| **When** | Harness прогоняет 10 сценариев (10 prompts → 19 ожидаемых API requests). |
| **Then** | (1) Каждый запрос полностью совпадает с captured request (включая headers, body, tool definitions); (2) Все ответы детерминированы; (3) При несовпадении выводится diff. Финальный exit code `0`. |
| **Input** | Сценарии из `mock_parity_scenarios.json` |
| **Output** | Лог `[OK] scenario_01 (3 requests matched)`, …, summary `10/10 passed` |
| **State** | Кеш captured-requests не модифицируется (read-only); тестовый отчёт пишется в `target/parity-report.json` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-11 | `mock-anthropic-service` крейт поддерживает Anthropic Messages API (POST /v1/messages, SSE-streaming) и возвращает заранее записанные ответы по hash от запроса. |
| FR-12 | Harness сравнивает фактический и ожидаемый запросы по нормализованному JSON (порядок ключей не важен) и печатает unified diff при несовпадении. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-9 | Mock-сервис стартует за ≤ 200 мс и не зависит от внешних ресурсов (всё in-process). |
| NFR-10 | Прогон harness занимает ≤ 30 секунд на dev-машине. |

#### Use Case BDD 2 (Edge: model-specific quirks)

| Field | Value |
|---|---|
| **Use Case ID** | UC-3.2 |
| **Given** | Пользователь использует модель `kimi-k2.5-instruct` через DashScope. |
| **When** | Runtime отправляет tool-result с полем `is_error: true` и большим payload. |
| **Then** | (1) Quirks-слой удаляет поле `is_error` из tool_result перед отправкой (kimi-k2.5 его не поддерживает, US-008 PRD); (2) Запрос маршрутизируется на DashScope endpoint; (3) Если body > 6 MB → preflight reject с typed-error `dashscope.body_too_large` (US-022 PRD); (4) Лимиты применяются: 256K контекст, 16K max output. |
| **Input** | `model=kimi-k2.5-instruct`, request с `is_error=true` |
| **Output** | Очищенный request, отправленный на DashScope, либо preflight error |
| **State** | Telemetry: событие `quirk.applied {model, quirk_name}` |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| FR-13 | Таблица quirks: `kimi-*` → strip `is_error`; max_tokens floor; routing override на DashScope даже при наличии `OPENAI_API_KEY`. |
| FR-14 | Body-size preflight: при превышении лимита провайдера (DashScope = 6 MB) возвращается typed-error без отправки запроса. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| NFR-11 | Применение quirks логируется в telemetry для последующего аудита (без секретов). |
| NFR-12 | Отдельные unit-тесты на каждый quirk; покрытие edge-cases: `is_error: false`, отсутствие поля, вложенные tool_results. |

---

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Внутренний слой Rust crate `api`, потребляемый `runtime` |
| **User Entry Points** | `--model <alias|id>`, env vars `*_API_KEY`/`*_AUTH_TOKEN`/`*_BASE_URL`, `HTTPS_PROXY`/`NO_PROXY`, slash `/model` |
| **Main Screens / Commands** | Не имеет UI; диагностика — через `claw doctor` (F3) |
| **Input / Output Format** | Internal Rust API: `Provider::send(request) -> Response`; `Provider::stream(request) -> impl Stream<Item=Event>` |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `api` crate |
| **Responsibility** | Унифицированный transport-слой: routing, auth, серилизация, SSE-парсинг, ретраи, quirks |
| **Business Logic** | (1) `resolve_alias(alias) -> model_id`; (2) `route(model_id) -> Box<dyn Provider>`; (3) `apply_quirks(request, model_id) -> Request`; (4) `provider.send_or_stream(request)` с retry/backoff |
| **API / Contract** | `trait Provider { fn send(&self, req) -> Result<Response>; fn stream(&self, req) -> Result<impl Stream>; fn count_tokens(&self, req) -> Result<usize>; }` |
| **Request Schema** | `Request { model, messages: Vec<Message>, system, tools: Vec<Tool>, max_tokens, temperature, stream, metadata }` |
| **Response Schema** | `Response { id, model, content: Vec<ContentBlock>, stop_reason, usage: Usage }`. SSE events: `message_start, content_block_start, content_block_delta, content_block_stop, message_delta, message_stop`. |
| **Error Handling** | Typed envelope `{ operation, target, errno, hint, retryable }`. HTTP 429/5xx → retry. 4xx (валидация) → user-facing error. Provider quirks errors (`dashscope.body_too_large`) — не ретраятся. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Provider` (Anthropic/Xai/OpenAiCompat/DashScope), `ModelAlias`, `RoutingRule`, `Quirk`, `Credentials`, `ProxyConfig`, `Request`, `Response`, `UsageEvent` |
| **Relationships (ER)** | `ModelAlias` 1—1 `model_id`; `model_id` 1—1 `Provider` через `RoutingRule`; `Provider` 1—N `Quirk`; `Provider` 1—1 `Credentials`; `Request` 1—1 `Response` |
| **Data Flow (DFD)** | `Runtime.send(turn)` → `resolve_alias()` → `route()` → `apply_quirks()` → `provider.serialize()` → `http.send()` → SSE-parser → `Response` → `runtime` + `telemetry.record(usage)` |
| **Input Sources** | Конфиг-файлы (aliases, providers), env vars (credentials, proxy), runtime model override (`/model`), API responses (SSE) |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Исходящий HTTPS к: `api.anthropic.com`, `api.x.ai`, `api.openai.com` (или OpenRouter / Ollama / собственный URL), `dashscope.aliyuncs.com` |
| TLS 1.2+, поддержка ALPN HTTP/2 |
| Опционально: HTTPS-прокси (corporate); локальный Ollama на `:11434`; mock-сервис на эфемерном порту для тестов |
| RAM: ≤ 50 МБ дополнительно для буферов SSE и retry-state |

---

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Реализация резолвера aliases + routing с префиксами + AnthropicProvider | — | Любой alias/префикс корректно маршрутизируется; интеграционные тесты | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Реализация OpenAiCompat / xAI / DashScope провайдеров с конвертацией форматов | T-1 | Все 4 провайдера проходят integration-тесты | ST-4, ST-5 |
| UC-2.1 | T-3 | Auth-слой: env vars, OAuth, приоритеты, redaction секретов | T-1 | Auth-резолвер покрыт unit/integration тестами | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Прокси-слой: env vars + ProxyConfig + интеграция в HTTP-клиент | T-1 | Запросы через mock-прокси работают; TLS-валидация сохраняется | ST-9, ST-10 |
| UC-3.1, UC-3.2 | T-5 | Mock-anthropic-service + parity-harness + quirks-слой (kimi, dashscope) | T-1, T-2 | Harness 10/10 зелёный; все quirks с unit-тестами | ST-11, ST-12 |

---

## 5. Detailed Task Breakdown

### Task 1

| Field | Value |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Trait `Provider`, AnthropicProvider, резолвер aliases (default + override), router по префиксам с приоритетом prefix > env-var. |
| **Dependencies** | — |
| **DoD** | (1) Unit-тесты на резолвер (≥ 20 тест-кейсов); (2) AnthropicProvider посылает запрос и парсит SSE; (3) Все aliases (`opus`, `sonnet`, `haiku`) корректно резолвятся. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | `trait Provider` + типы `Request`/`Response`/`UsageEvent` | — | Trait компилируется, mockable; типы сериализуются в JSON |
| ST-2 | AnthropicProvider: HTTP-запросы (POST /v1/messages), SSE-парсер, конвертация в общий envelope | ST-1 | Тестовый запрос к mock-сервису возвращает корректный Response |
| ST-3 | Резолвер aliases + router: default-mapping + overrides + prefix-routing | ST-1 | 100% корректность routing на наборе из ≥ 20 model id |

### Task 2

| Field | Value |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализация OpenAiCompatProvider, XaiProvider, DashScopeProvider с конвертацией форматов между Anthropic-style envelope и OpenAI Chat Completions / xAI / DashScope. |
| **Dependencies** | T-1 |
| **DoD** | (1) Каждый провайдер проходит integration-тест с mock-сервисом своего вкуса; (2) Конвертация tool_use ↔ tool_calls работает в обе стороны без потерь. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | OpenAiCompatProvider: конвертация Request/Response, поддержка `OPENAI_BASE_URL`, default OpenRouter URL | T-1 | Тест с локальным mock OpenAI API проходит; tool_calls маппятся 1:1 |
| ST-5 | XaiProvider + DashScopeProvider: специфичная сериализация, корректные endpoints | T-1 | Каждый провайдер имеет ≥ 3 integration-теста; usage events нормализованы |

### Task 3

| Field | Value |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Auth-слой: распознавание `*_API_KEY`/`*_AUTH_TOKEN`/`OPENAI_BASE_URL`/`ANTHROPIC_BASE_URL`; приоритет API_KEY > AUTH_TOKEN; redaction секретов в логах. |
| **Dependencies** | T-1 |
| **DoD** | (1) Auth-резолвер unit-tested; (2) Грязные логи не содержат секретов (regex-проверка); (3) `claw doctor` (F3) валидирует все credentials. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Резолвер credentials per-provider с приоритетами и warnings | T-1 | Unit-тесты покрывают все провайдеры; warning при двойных credentials |
| ST-7 | Хранение секретов как `Secret<String>`, маскирование в `Debug`/`Display` | — | Секрет не выводится `{:?}` или `format!("{}", …)`; integration-тест проверяет |
| ST-8 | Redaction секретов в telemetry/log/session-файлах | F7 (telemetry) | Регрессионный тест: запись сессии не содержит ключа |

### Task 4

| Field | Value |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Прокси-слой: чтение `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` (case-insensitive); поддержка программной `ProxyConfig`; приоритет программной над env. |
| **Dependencies** | T-1 |
| **DoD** | (1) Запросы через тестовый mitm-прокси работают; (2) NO_PROXY корректно исключает локальные хосты; (3) TLS-валидация остаётся on по умолчанию. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Чтение env vars + парсинг URL прокси и `NO_PROXY` | — | Unit-тесты на разные форматы; case-insensitive |
| ST-10 | Интеграция с HTTP-клиентом (reqwest или эквивалент); ProxyConfig structure | ST-9 | Integration-тест с локальным mitm-прокси проходит; latency overhead ≤ 50 мс |

### Task 5

| Field | Value |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1, UC-3.2 |
| **Task Description** | (1) `mock-anthropic-service` крейт + scenarios JSON + harness script; (2) Quirks-слой: kimi-strip-is_error, body-size preflight, kimi/dashscope routing override, лимиты токенов. |
| **Dependencies** | T-1, T-2 |
| **DoD** | (1) `./scripts/run_mock_parity_harness.sh` → 10/10 passed за ≤ 30 с; (2) Все quirks unit-tested; (3) Регрессионный тест на kimi-k2.5 не падает. |

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `mock-anthropic-service` (крейт): in-process сервер, lookup ответов по hash запроса, SSE-streaming | T-1 | Старт ≤ 200 мс; детерминированный |
| ST-12 | Quirks-таблица: kimi → strip is_error, dashscope body 6 MB preflight, лимиты 256K/16K, prefix-route override env (US-024 PRD) | T-2 | Unit-тесты на каждый quirk; integration-сценарий с kimi-k2.5 |
