# SPEC — Feature 10: ACP / Zed Integration

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Agent Client Protocol (ACP) + Zed Editor Integration |
| **Description (Goal / Scope)** | Реализация серверной части ACP (Agent Client Protocol) — стандартного JSON-RPC протокола для общения IDE/editor с coding-агентом. Команда `claw acp` запускает agent в ACP-server режиме (stdin/stdout JSON-RPC), позволяя Zed (и другим ACP-совместимым редакторам) использовать `claw` как backend. По README статус "in development". Включает: handshake (initialize/capabilities), session lifecycle через ACP, передача tool_use/tool_result через ACP-message frame'ы, mapping permission-mode и встроенных tools на ACP-tool spec. Вне скоупа: client-side плагин Zed (он external), MCP-протокол (F8). |
| **Client** | Zed Editor (primary), любой IDE, реализующий ACP-client (например VS Code-плагин). |
| **Problem** | Без ACP пользователи Zed не могут использовать `claw` напрямую — приходится переключаться в терминал. Без стандартного протокола каждый редактор требует custom-интеграции. |
| **Solution** | (1) Subcommand `claw acp` запускает infinite-loop, читающий JSON-RPC с stdin, пишущий ответы на stdout; (2) Реализация спецификации ACP (initialize → session → message turn → tool calls → close); (3) Маппинг внутренних типов (turn, tool_use) на ACP-frame'ы; (4) Capability negotiation: какие tools/permissions agent поддерживает. |
| **Metrics** | (1) ACP-handshake ≤ 200 мс; (2) Latency turn message → first SSE delta ≤ 500 мс; (3) Соответствие ACP spec на 100% обязательных методов; (4) Smoke-тест с реальным Zed-плагином проходит. |

## 2. User Stories and Use Cases

### US-1: ACP server lifecycle (initialize + session)

| Field | Value |
|---|---|
| **Role** | Zed Editor |
| **User Story** | Как Zed-клиент, я хочу подключиться к `claw acp` через JSON-RPC stdio, выполнить handshake и открыть session, чтобы использовать claw как backend агента. |
| **UX Flow** | Zed запускает `claw acp` как child process → шлёт `initialize` JSON-RPC → получает capabilities → шлёт `session/new` → получает session_id → отправляет user message → получает streaming ответ. |

**UC-1.1: Initialize + capabilities.** Given Zed запустил `claw acp` → When клиент шлёт `{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"...","clientInfo":{...}}}` → Then `claw` отвечает `{"result":{"protocolVersion":"...","capabilities":{"tools":[...],"models":[...],"permissions":[...]},"serverInfo":{"name":"claw","version":"..."}}}`. После этого `notifications/initialized` от клиента переводит сервер в ready.

**FR-1:** Subcommand `claw acp` блокирует поток на stdin, парсит line-delimited JSON-RPC frames. **FR-2:** Capabilities включают: список доступных tools (Bash/Read/Write/Edit/Grep/Glob + MCP-tools), модели (aliases из F2), permission modes. **NFR-1:** Все JSON-RPC ответы содержат тот же `id`, что и запрос (для async-correlation). **NFR-2:** Stderr используется для логов (не для frames) — клиенту parsing не мешает.

**UC-1.2: Session new + message turn.** Given handshake done → When `session/new` затем `session/message {role:"user", content:[...]}` → Then `claw` создаёт session (см. F5), отправляет turn в провайдер (F2) и стримит ответ через `session/message/delta` notifications, заканчивая `session/message/end`.

**FR-3:** `session/new` возвращает session_id (ULID, см. F5); опционально принимает model/permission_mode для override. **FR-4:** Streaming через notifications `session/message/delta {sessionId, content_delta}` каждые N токенов или 50 мс. **NFR-3:** Backpressure: если клиент медленно читает — сервер не блокируется (буфер с лимитом + drop с warning).

### US-2: Tool calls через ACP

| Field | Value |
|---|---|
| **Role** | Zed (для UI tool-вывода) |
| **User Story** | Как Zed, я хочу видеть tool_use/tool_result через ACP-frame'ы и опционально перехватывать permission-prompts, чтобы рендерить их в IDE-UI вместо терминала. |

**UC-2.1: Tool execution via ACP frames.** Given session активна, модель эмитит `tool_use` → When `claw` обрабатывает → Then notification `session/tool/use {sessionId, toolUseId, name, input}` → выполнение → `session/tool/result {sessionId, toolUseId, output, isError}`.

**FR-5:** Каждое tool_use получает unique `toolUseId` для ACP-correlation; отправляется до execute. **FR-6:** Tool result-frame содержит truncated preview + полный output по запросу `session/tool/result/full {toolUseId}`. **NFR-4:** Tool execution не блокирует другие notifications (может выполняться параллельно с message stream от модели в multi-turn case).

**UC-2.2: Permission elevation через клиента.** Given permission-mode = `read-only`, модель просит write_file → When permission denied → Then notification `session/permission/request {sessionId, scope:"workspace-write", reason}` к клиенту → клиент показывает диалог → `session/permission/grant {scope, ttl}` или `deny` → `claw` повторяет tool_use или возвращает error.

**FR-7:** Permission elevation flow: `request → user response → reapply`. TTL опционально (one-shot vs session-wide). **NFR-5:** Если клиент не отвечает за timeout (default 30 с) → permission denied automatically.

### US-3: Зачем нужен `claw acp` в edited environment

| Field | Value |
|---|---|
| **Role** | Разработчик в Zed |
| **User Story** | Как разработчик, я хочу использовать `claw` через Zed без терминала, чтобы edits применялись прямо в editor с inline-diff и hover-подсказками от LSP-плагинов claw. |
| **UX Flow** | Zed UI: панель чата с claw → ответы стримятся → tool_use показываются как inline-cards с "Apply" / "Reject"; permission-prompts — как modal. |

**UC-3.1: ACP status / health.** Given Zed открыт, claw acp running → When клиент шлёт `health/check` → Then ответ с worker-state (см. F3): state, model, session_count, providers_status.

**FR-8:** `health/check` инкорпорирует данные из `worker-state.json` (F3) и `doctor`-результатов (F3). **NFR-6:** Health-response ≤ 100 мс (cached от последнего doctor-run, или быстрый refresh без network checks).

## 3. Architecture / Solution

| Area | Fill In |
|---|---|
| **Client Type** | JSON-RPC over stdin/stdout (line-delimited frames) |
| **Backend** | Модуль `acp` в `rusty-claude-cli` крейте; адаптер между ACP-spec и `runtime` API |
| **Protocol** | Agent Client Protocol — JSON-RPC 2.0 + спец-методы `initialize/session/notifications` |
| **Data Flow** | Stdin → frame parser → method dispatcher → runtime API → response → stdout. Streaming через notifications. |
| **Infra** | Stdio (никакой сети); процесс лайфтайм управляется клиентом (Zed) |

## 4. Work Plan

| UC | Task | DoD | Subtasks |
|---|---|---|---|
| UC-1.1 | T-1: ACP frame parser + initialize/capabilities | Handshake с reference Zed-клиентом проходит | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2: session/new + session/message + streaming notifications | Multi-turn session работает в reference тестах | ST-4, ST-5 |
| UC-2.1 | T-3: tool_use/tool_result frames + correlation by toolUseId | Tool выполняется, результат стримится клиенту | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4: permission elevation request/grant flow | Эскалация и timeout работают | ST-9, ST-10 |
| UC-3.1 | T-5: health/check + интеграция с F3 worker-state + smoke-тест с Zed | Health быстрый; Zed-смоук проходит | ST-11, ST-12 |

## 5. Detailed Task Breakdown

**T-1.** ST-1: Line-delimited JSON-RPC reader/writer; ST-2: dispatcher по `method` строке; ST-3: `initialize` handler с capabilities из реестров F2/F4/F8.
**T-2.** ST-4: `session/new` с переиспользованием F5 SessionManager; ST-5: streaming через notifications с throttling.
**T-3.** ST-6: маппинг runtime tool_use → `session/tool/use` notification; ST-7: dispatch tool execution; ST-8: `session/tool/result` (с preview/full split).
**T-4.** ST-9: permission elevation: queue request → wait для grant/deny → propagate; ST-10: timeout + deny default.
**T-5.** ST-11: `health/check` с cached F3 doctor results; ST-12: e2e smoke-тест против тестового ACP-клиента (mock Zed).
