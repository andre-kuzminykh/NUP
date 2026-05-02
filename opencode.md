# OpenCode — Спецификация (SPEC)

> Источник: репозиторий [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode) — open source AI coding agent.
>
> Данная спецификация построена по шаблону SPEC Template и описывает каждую крупную фичу проекта OpenCode пошагово: контекст → пользовательские истории + use case'ы (BDD) с функциональными и нефункциональными требованиями → архитектура → план работ → детальная декомпозиция задач.

---

## Оглавление

1. [Feature 1 — Interactive Terminal Coding Agent (TUI)](#feature-1--interactive-terminal-coding-agent-tui)
2. [Feature 2 — Multi-Agent System (Build / Plan / Subagents / Custom)](#feature-2--multi-agent-system-build--plan--subagents--custom)
3. [Feature 3 — Multi-Provider LLM Integration](#feature-3--multi-provider-llm-integration)
4. [Feature 4 — Built-in Tools & MCP Integration](#feature-4--built-in-tools--mcp-integration)
5. [Feature 5 — Sessions, Multi-Project, Worktrees & Sharing](#feature-5--sessions-multi-project-worktrees--sharing)
6. [Feature 6 — Permissions System](#feature-6--permissions-system)
7. [Feature 7 — Plugins & Skills System](#feature-7--plugins--skills-system)
8. [Feature 8 — GitHub Integration (Issues / PRs / Actions)](#feature-8--github-integration-issues--prs--actions)
9. [Feature 9 — IDE Integrations (VS Code / Zed)](#feature-9--ide-integrations-vs-code--zed)
10. [Feature 10 — Headless Server & Client/Server Architecture](#feature-10--headless-server--clientserver-architecture)
11. [Feature 11 — Desktop App (macOS / Windows / Linux)](#feature-11--desktop-app-macos--windows--linux)

---

# Feature 1 — Interactive Terminal Coding Agent (TUI)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Interactive Terminal Coding Agent (TUI) |
| **Description (Goal / Scope)** | Полноценное интерактивное TUI-приложение, запускаемое командой `opencode` в терминале. Цель — дать разработчику AI-агента прямо в терминале: чат-интерфейс с историей сообщений, мультистрочный ввод с привязкой клавиш, отображение хода работы инструментов (read/write/bash/edit), переключение агентов по `Tab`, выбор моделей и провайдеров через диалоги, прикрепление файлов, шаринг сессии. Scope: рендер UI на базе React-подобных компонентов в терминале, обработка ввода, рендер сообщений и tool calls, управление состоянием через client/server модель. |
| **Client** | Разработчики ПО, использующие современный терминал (WezTerm, Alacritty, Ghostty, Kitty); пользователи neovim-like окружений; команды, которым нужен AI-агент без выхода из терминала. |
| **Problem** | Существующие AI-инструменты (Cursor, Copilot Chat) живут в IDE/Web, требуют GUI. Пользователи терминала вынуждены либо переключаться, либо использовать проприетарные TUI с vendor lock-in. Нужен мощный, быстрый, расширяемый агент в терминале без зависимости от одного провайдера. |
| **Solution** | Кросс-платформенный TUI-клиент на TypeScript/React (`packages/console/app`), стартующий локальный HTTP-сервер (`opencode serve`) и управляющий им. Поддержка любых LLM-провайдеров, диалоги выбора модели/агента/MCP, рендер tool-events в realtime, Tab-переключение агентов, vim-подобные хоткеи. |
| **Metrics** | • Time-to-first-token < 2 сек после `Enter`<br>• UI render latency < 16 ms (60 fps в терминале)<br>• Поддержка терминалов: WezTerm/Alacritty/Ghostty/Kitty/iTerm2/Windows Terminal<br>• ≥ 95 % сессий завершаются без падения TUI<br>• Среднее число сообщений на сессию ≥ 5<br>• % сессий с переключением агента (`Tab`) ≥ 20 % |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Разработчик-пользователь терминала |
| **User Story ID** | US-1 |
| **User Story** | As a разработчик, I want запустить `opencode` в любой папке проекта и сразу получить интерактивный AI-чат, so that я могу задавать вопросы по коду и получать изменения файлов, не покидая терминал. |
| **UX / User Flow** | 1. Открыть терминал → `cd <project>` → `opencode`. 2. Увидеть splash-экран и логотип, затем основной layout: история сообщений сверху, поле ввода снизу, статус-бар (агент, модель, токены). 3. Ввести сообщение → `Enter`. 4. Видеть стрим ответа модели и поэтапные tool calls (Read/Write/Edit/Bash). 5. При необходимости — `Esc` для отмены, `Ctrl+C` дважды для выхода. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Установлен `opencode-ai`, есть валидный API-ключ хотя бы одного провайдера (`opencode auth login`), пользователь находится в директории git-проекта. |
| **When** | Пользователь выполняет `opencode` в терминале. |
| **Then** | Стартует локальный HTTP-сервер на свободном порту, открывается TUI с пустой сессией, статус-бар показывает текущего агента (`build`) и модель по умолчанию, доступен ввод. |
| **Input** | CLI: `opencode` (опц. `--port`, `--agent`, `--model`, `--dir`). |
| **Output** | Полностью отрисованный экран TUI; в фоне — процесс сервера с журналом в `~/.local/share/opencode/log`. |
| **State** | Сессия не сохранена в БД до первого сообщения. Открыта websocket-подобная подписка на `bus`-события сервера. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | TUI должен запускать локальный сервер (`Server.listen`) на свободном порту, если не указан `--attach`. |
| **FR-2** | TUI должен отображать активного агента и активную модель в статус-баре. |
| **FR-3** | TUI должен подписываться на server-sent events (`bus`) и рендерить сообщения и parts в реальном времени. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Холодный старт TUI ≤ 1.5 сек на машинах от 8 ГБ RAM. |
| **NFR-2** | Потребление CPU в idle ≤ 1 % на одно ядро. |
| **NFR-3** | Поддержка SIGINT/SIGTERM с корректным выключением сервера и сохранением сессии. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | TUI запущен, пользователь ввёл сообщение в input-area. |
| **When** | Пользователь нажимает `Enter` (без Shift). |
| **Then** | Сообщение отправляется в `POST /project/:projectID/session/:sessionID/message`, на экране появляется user-bubble, ниже — стрим ассистент-сообщения с tool calls и токен-счётчиком. |
| **Input** | Текст сообщения; опционально — прикреплённые файлы (`@filename` autocompletion или `--file`). |
| **Output** | Стрим parts (`text`, `tool`, `reasoning`) в UI; финальное сохранённое сообщение в SQLite. |
| **State** | Session перешла в статус `running` → по завершении в `idle`. История синхронизирована с БД. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | TUI должен поддерживать multi-line input (`Shift+Enter` — новая строка, `Enter` — отправка). |
| **FR-5** | TUI должен корректно прерывать инференс при `Esc` (POST `/session/:id/abort`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Латентность отображения нового стрим-токена ≤ 50 мс с момента получения от провайдера. |
| **NFR-5** | UI устойчив к разрыву соединения с сервером — повтор подписки с backoff 2/4/8 сек. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Разработчик, исследующий незнакомый код |
| **User Story ID** | US-2 |
| **User Story** | As a разработчик, I want переключаться между primary-агентами одной клавишей, so that могу быстро уйти из режима write-safe `plan` в `build` и обратно без перезапуска. |
| **UX / User Flow** | 1. В TUI-сессии нажать `Tab` — индикатор агента в status-bar моментально меняется. 2. Для выбора неосновных агентов — нажать сконфигурированную клавишу или открыть диалог `dialog-agent.tsx`. 3. Активный агент применяется к следующему запросу. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Открыт TUI с дефолтным агентом `build`. |
| **When** | Пользователь нажимает `Tab` (или сконфигурированный `switch_agent` keybind). |
| **Then** | Active agent меняется на `plan`, статус-бар обновляется, цвет/иконка меняются, новые сообщения отправляются с `agent=plan`. |
| **Input** | Keypress `Tab`. |
| **Output** | Обновлённый UI, событие `session.agent.switched`. |
| **State** | `session.agent = "plan"` сохранено в state runtime; permission-rules из `plan` теперь применяются. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | `Tab` должен циклически переключать только primary-агентов (mode `primary` или `all`). |
| **FR-7** | После переключения должны применяться правила permission текущего агента. |
| **FR-8** | TUI должен открывать `dialog-agent.tsx` по `Ctrl+A` (или сконфигурированной клавише) для выбора любого агента включая subagent-ов. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Переключение должно происходить ≤ 50 мс. |
| **NFR-7** | Переключение в середине стрима блокируется и показывает понятное предупреждение, не ломая UI. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Активна сессия в `plan`-агенте, пользователь попросил «исправь баг в `src/foo.ts`». |
| **When** | Модель вызывает инструмент `edit`, у которого в `plan` permission = `ask`. |
| **Then** | TUI показывает permission-prompt с предпросмотром diff и опциями `Allow once / Always / Reject`. |
| **Input** | Tool call от модели; пользовательский выбор. |
| **Output** | Применённый или отклонённый edit; если `Always` — добавляется правило в session permission-set. |
| **State** | Сохраняется `Permission.Reply` и опционально новое `Rule`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Permission-prompt должен показывать summary action'а и input/parameters инструмента. |
| **FR-10** | Реакция пользователя должна быть передана в сервер через `POST /project/:projectID/session/:sessionID/permission/:permissionID`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Prompt не должен блокировать UI рендер других частей. |
| **NFR-9** | Пользователь может отменить ожидание prompt'а (`Esc`) — это эквивалентно `reject`. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want прикрепить файлы и изображения к сообщению, so that могу попросить агент проанализировать конкретные файлы или скриншот. |
| **UX / User Flow** | 1. В input-area набрать `@` — открывается fuzzy-поиск файлов. 2. Выбрать файл → он добавляется как chip над input. 3. Опционально — drag&drop изображения (если поддерживается терминалом) или `--file path/to/img.png` в `opencode run`. 4. Отправить сообщение. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | TUI открыт, индекс файлов проекта построен (через `find/file` API). |
| **When** | Пользователь набирает `@src/utils/` → показывается fuzzy-список → выбирает `parser.ts`. |
| **Then** | Файл добавляется как `attachment-part` к следующему сообщению; в payload — `{type:"file", url:"file://...", filename, mime}`. |
| **Input** | Префикс `@` + текст-фильтр; choice клавишами. |
| **Output** | Видимый chip; payload отправлен с сообщением; модель видит контент файла как часть user message. |
| **State** | Attachments хранятся в `Part[]` сообщения. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Fuzzy-поиск должен использовать `GET /project/:projectID/find/file?directory=...` (ripgrep под капотом). |
| **FR-12** | TUI должен поддерживать как текстовые, так и бинарные файлы (изображения) с корректным `mime` и base64/url. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Fuzzy-выдача ≤ 100 мс для проектов до 50 000 файлов. |
| **NFR-11** | Файлы > 5 MB приводят к предупреждению и предлагают подтверждение прикрепления. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Native TUI (React-like, рендер в терминал) — `packages/console/app`. Альтернативно: Desktop App, IDE-расширения, headless server. |
| **User Entry Points** | `opencode` (стартует TUI + сервер); `opencode --attach <url>` (только клиент); `opencode tui thread` (open thread directly). |
| **Main Screens / Commands** | Главный chat-layout (история + input + статус-бар); диалоги: `dialog-agent`, `dialog-model`, `dialog-provider`, `dialog-mcp`, `dialog-skill`, `dialog-session-list`, `dialog-session-rename`, `dialog-stash`, `dialog-status`, `dialog-tag`, `dialog-theme-list`, `dialog-variant`, `dialog-workspace-create`. |
| **Input / Output Format** | **Input:** plain text + attachments (`Part[]`). **Output:** stream of `Part`s (`text`, `tool`, `reasoning`, `file`). |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `opencode server` (`packages/opencode/src/server`) на базе adapter Bun/Node. |
| **Responsibility** | HTTP API + bus events + lifecycle сессий, проекты, агенты, провайдеры, инструменты. |
| **Business Logic** | Bootstrap → project resolve → session create/get → message append → call provider stream → execute tools (с permission-проверками) → persist в SQLite. |
| **API / Contract** | OpenAPI 3.1 (см. `specs/project.md`): `GET /project`, `POST /project/init`, CRUD `/session`, `/message`, `/share`, `/abort`, `/compact`, `/revert`, `/permission/:id`, `/find/file`, `/file`, `/file/status`, `/log`, `/provider`, `/config`, `/agent`. |
| **Request Schema** | `POST /project/:projectID/session/:sessionID/message` body: `{ parts: Part[], agent?: string, model?: { providerID, modelID }, variant?: string }`. |
| **Response Schema** | SSE stream of `BusEvent`-ов; финальное `{ info: Message, parts: Part[] }`. |
| **Error Handling** | Структурированные ошибки `NamedError` (provider/auth/permission/tool/network); HTTP 4xx/5xx с JSON body `{ name, message, data }`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Project`, `Session`, `Message`, `Part`, `Tool` invocation, `PermissionRequest`, `Agent`, `Provider`, `Model`. |
| **Relationships (ER)** | Project 1—N Session; Session 1—N Message (parent-child через `parentID` для fork/branch); Message 1—N Part; Session 1—N PermissionRequest. |
| **Data Flow (DFD)** | TUI → HTTP/SSE → Server → ProviderAdapter (Anthropic/OpenAI/...) → ToolRegistry → Filesystem/Bash/LSP → SQLite (Drizzle) → bus → SSE → TUI. |
| **Input Sources** | Пользовательский ввод; файлы рабочей директории; ripgrep-индекс; LSP-серверы; MCP-серверы; provider-API. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| **Локально:** ≥ 8 GB RAM, любой современный CPU (x86-64 или arm64), ≥ 200 MB свободного диска (в т.ч. `~/.local/share/opencode` под историю). |
| **Бинарники:** Node 20+ или Bun 1.x; SQLite встроена; `ripgrep` и `fd` — опционально (есть бандленные fallback'и). |
| **Сетевые требования:** outbound HTTPS до выбранных провайдеров (Anthropic api.anthropic.com, OpenAI api.openai.com, Google и т. д.). |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Стартовый экран TUI + bootstrap локального сервера | — | TUI стартует за < 1.5 с, статус-бар отображает агента/модель | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Отправка сообщения и стрим ответа в UI | T-1 | Сообщение отправляется, ответ стримится, токены/стоимость показываются | ST-4, ST-5 |
| UC-2.1 | T-3 | Tab-переключение primary-агентов | T-1 | `Tab` циклит, цвет/иконка/permission меняются | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Permission-prompt overlay в TUI | T-2, T-3 | Prompt с diff/preview, ответ доходит до сервера | ST-9, ST-10 |
| UC-3.1 | T-5 | Прикрепление файлов через `@`-mention | T-2 | Файл успешно прикреплён и виден модели | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать запуск TUI: bootstrap (`packages/opencode/src/cli/bootstrap.ts`), spawn локального `Server.listen`, инициализация runtime, отрисовка `app.tsx` и стартового loading-экрана. |
| **Dependencies** | Server-package готов, react-tui фреймворк выбран. |
| **DoD** | Запуск `opencode` в пустом git-проекте → отображается layout, статус-бар, пустой input; нет ошибок в логах. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Реализовать bootstrap: загрузка config, инициализация AppRuntime, выбор порта | — | `opencode` работает с дефолтным конфигом |
| ST-2 | Реализовать `startup-loading.tsx` + `logo.tsx` | ST-1 | Splash виден ≤ 500 мс |
| ST-3 | Реализовать main layout (история / input / status-bar) | ST-1 | UI рендерится без артефактов |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализовать input → POST message → SSE-подписку на parts → инкрементальный рендер в UI. |
| **Dependencies** | T-1 |
| **DoD** | Сообщение пользователя видно в истории, ассистент-ответ появляется по токенам, tool calls отрисовываются по мере выполнения. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Реализовать `textarea-keybindings.ts` (Enter/Shift+Enter/Esc/Up/Down) | T-1 | Все хоткеи работают |
| ST-5 | Реализовать SSE-подписку на bus events и инкрементальный апдейт parts | T-1 | Стрим виден без задержек > 50 мс |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Циклическое переключение primary-агентов и обновление UI/permission-set. |
| **Dependencies** | T-1 |
| **DoD** | `Tab` переключает агента, статус и цветовая схема меняется, permission-набор применяется к следующему запросу. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Чтение списка агентов через `GET /project/:projectID/agent` | T-1 | Список агентов корректен |
| ST-7 | Подключение `Tab` keybind в layer-е `feature-plugins` | T-1 | Переключение моментальное |
| ST-8 | `dialog-agent.tsx` для выбора любого агента | ST-6 | Диалог фильтрует по mode |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Permission-prompt overlay: рендер запроса от сервера, отображение diff/команды, ответ пользователя. |
| **Dependencies** | T-2, T-3 |
| **DoD** | При permission-event tool блокируется до ответа; ответ доходит до сервера; tool продолжается или отменяется. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Подписка на `permission.requested` события | T-2 | Prompt появляется на каждом event |
| ST-10 | UI overlay с кнопками `Allow once / Always / Reject` + diff preview | ST-9 | Ответ доходит за ≤ 200 мс |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | `@`-mention автокомплит файлов и прикрепление к сообщению как `Part`. |
| **Dependencies** | T-2 |
| **DoD** | Файл/изображение успешно отправлено, модель видит содержимое. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Запрос к `/find/file` и fuzzy-фильтрация в UI | T-2 | Выдача ≤ 100 мс на 50k файлов |
| ST-12 | Конвертация выбранного файла в `Part` с правильным `mime` | ST-11 | Картинки и текст работают |

---

# Feature 2 — Multi-Agent System (Build / Plan / Subagents / Custom)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Multi-Agent System (Build / Plan / Subagents / Custom Agents) |
| **Description (Goal / Scope)** | Архитектура нескольких специализированных AI-агентов, между которыми пользователь может переключаться или которых может вызывать через `@mention`. Включает 2 встроенных primary-агента (`build`, `plan`), 2 встроенных subagent (`general`, `explore`), и возможность создавать пользовательских агентов через CLI или markdown-файлы. Каждый агент имеет свой prompt, model override, набор разрешений, температуру, top-p, шаги, цвет, набор tools. Scope: схема Agent.Info, реестр агентов, генерация агентов LLM-ом, frontmatter-конфиг, Tab-cycle, `@mention`-инвокация, встроенные системные промты. |
| **Client** | Разработчики, желающие иметь специализированных агентов под разные задачи (анализ кода, рефакторинг, написание тестов, ревью, исследование), а также команды, выстраивающие свои workflow с разделением ответственности. |
| **Problem** | Один универсальный агент с full-access ведёт к нежелательным изменениям при «обзорных» задачах. Невозможно надёжно разделить «исследование» и «изменение», нет способа дать модели разные системные промты под разные стадии работы. |
| **Solution** | Система Agent с двумя осями: (1) `mode` — `primary` (для прямой интеракции, циклится `Tab`) или `subagent` (вызывается через `Task`-tool / `@mention`); (2) `permission` — индивидуальный ruleset на каждый агент. Встроенные `build`/`plan` дают разный default-permission. Custom agents через `~/.config/opencode/agents/<name>.md` с YAML-frontmatter. Команда `opencode agent create` использует LLM (`generate.txt`) для генерации описания и системного промпта. |
| **Metrics** | • % сессий с использованием `plan` ≥ 30 %<br>• % пользователей с ≥ 1 custom-агентом ≥ 15 %<br>• Среднее число агентов на пользователя ≥ 3<br>• Доля subagent-вызовов через `Task` ≥ 10 % всех tool-calls<br>• Время загрузки реестра агентов ≤ 200 мс |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Разработчик, исследующий кодовую базу |
| **User Story ID** | US-1 |
| **User Story** | As a разработчик, I want использовать `plan`-агент в read-only режиме, so that исследовать незнакомый репозиторий без риска случайно изменить файлы или запустить деструктивные команды. |
| **UX / User Flow** | 1. Открыть TUI → нажать `Tab` → активен `plan`. 2. Задать вопрос «как работает аутентификация в этом репозитории». 3. Агент использует `read`/`grep`/`glob`/`webfetch`, но для `edit`/`bash` — спрашивает разрешение. 4. По окончании — выдаёт план изменений, не применяя их. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Пользователь активировал агент `plan` (mode=primary, permission `edit`/`bash`/`apply_patch` по умолчанию = `ask`). |
| **When** | Модель в ходе выполнения вызывает `edit`-tool на файле. |
| **Then** | Сервер инициирует `permission.requested` событие, tool ставится на паузу до ответа пользователя; в TUI рендерится prompt с diff. |
| **Input** | Tool call (provider response) → trigger evaluation в `Permission.Service`. |
| **Output** | Пауза tool execution; `Permission.Request` объект в БД; bus-event. |
| **State** | `session.run_state = "awaiting_permission"`; `permissionID` на `session`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Permission.fromConfig для `plan` должен ставить `edit`/`bash`/`apply_patch` в `ask` по умолчанию. |
| **FR-2** | Subagent-режим должен подавлять `todowrite` tool. |
| **FR-3** | Plan-агент при попытке выйти из плана должен использовать `plan_exit`-tool, который deny по умолчанию вне `plan`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Permission resolution ≤ 5 мс на запрос. |
| **NFR-2** | Не должно происходить утечек action'ов между агентами в одной сессии. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Пользователь в режиме `plan`, агент сделал `edit` request, пользователь нажал `Always`. |
| **When** | Сервер сохраняет правило в session-level permission set и продолжает tool. |
| **Then** | Все последующие `edit`-вызовы в текущей сессии выполняются без prompt'а. |
| **Input** | `Permission.Reply = "always"`. |
| **Output** | `session.permission` обновлён; tool продолжается; bus-event `permission.replied`. |
| **State** | Правило живёт до закрытия сессии (не персистится в `agent`-config). |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | `Always`-ответ должен расширять только текущую сессию, не глобальный config. |
| **FR-5** | Должна быть возможность сбросить session-permissions через `/permission reset`-команду. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Запись правила должна быть транзакционной (drizzle/SQLite). |
| **NFR-5** | Логирование permission decisions с уровнем `INFO` по умолчанию. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Опытный пользователь / DevOps |
| **User Story ID** | US-2 |
| **User Story** | As a опытный пользователь, I want создать свой кастомный агент с промтом «code-reviewer», so that получить специализированного агента под мои стандарты ревью. |
| **UX / User Flow** | 1. `opencode agent create` → выбрать `--path` (project / global) → ввести `--description "review TS code for SOLID and security"`. 2. LLM генерирует identifier + whenToUse + systemPrompt. 3. Файл `code-reviewer.md` сохраняется с YAML frontmatter. 4. В TUI агент появляется в `dialog-agent` и доступен как `@code-reviewer`. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Установлен и сконфигурирован `opencode`, есть провайдер. |
| **When** | Пользователь вызывает `opencode agent create --description "..." --mode subagent`. |
| **Then** | Запускается `Agent.generate`, который зовёт `generateObject` (Anthropic/OpenAI) и пишет markdown с frontmatter `name`, `description`, `mode`, `permission`, `model?`, `prompt`. |
| **Input** | `description`, опционально `path`, `mode`, `model`. |
| **Output** | Файл `<name>.md` в `~/.config/opencode/agents/` или `.opencode/agents/`. |
| **State** | Реестр агентов обновляется в hot-reload-режиме. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | `Agent.generate` должен возвращать строго типизированный объект `{ identifier, whenToUse, systemPrompt }`. |
| **FR-7** | Identifier должен быть kebab-case 2-4 слова, валидируется regex. |
| **FR-8** | Должны мерджиться permission-defaults `Permission.fromConfig` с user-config. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Генерация агента ≤ 30 сек на стандартной модели. |
| **NFR-7** | Не должно создаваться файлов с пустым `name`. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Custom-agent `code-reviewer.md` существует в `.opencode/agents/`. |
| **When** | В чате пользователь пишет `@code-reviewer review src/auth.ts`. |
| **Then** | Primary-агент инициирует `task`-tool с `subagent_type=code-reviewer`, тот загружает свой prompt и работает в изолированном контексте. |
| **Input** | Mention text, optional `--model`, `--variant`. |
| **Output** | Результат subagent-сессии, добавленный как `tool`-part в основное сообщение. |
| **State** | Создаётся child-сессия с `parentID = main session`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | `@mention`-парсер должен искать агентов с `mode in ['subagent','all']`. |
| **FR-10** | Subagent должен иметь свой собственный набор tools, недоступных в текущем primary-агенте. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Subagent task должен быть отменяемым (abort propagation). |
| **NFR-9** | Контекст subagent-а изолирован — нет утечки истории родителя кроме переданной в task. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want чтобы primary-агент автоматически делегировал сложные исследовательские задачи `general`-subagent, so that не тратить токены основной сессии и работать параллельно. |
| **UX / User Flow** | 1. Пользователь спрашивает «найди все места где регистрируются роуты и составь карту». 2. Primary вызывает `task` → `general`. 3. `general` параллельно вызывает grep/glob/read и возвращает компактный результат. 4. Primary использует ответ для финального формулирования. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Primary-агент `build`, доступен subagent `general`. |
| **When** | Модель `build` вызывает `task({ subagent_type: "general", description, prompt })`. |
| **Then** | Сервер запускает изолированную инференс-сессию от имени `general`, который имеет свой системный prompt, читает файлы, возвращает компактный результат через `task`-tool result. |
| **Input** | `description`, `prompt`, optional model override. |
| **Output** | `tool`-part со статусом `completed` и `output` от `general`. |
| **State** | Token usage добавляется к родительской сессии; runtime statistics обновляются. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | `task`-tool должен поддерживать список доступных subagent'ов через `Agent.list({ mode: "subagent" })`. |
| **FR-12** | Должна быть поддержка параллельного запуска нескольких task'ов из одного step. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Параллельные task'и не должны деградировать UI больше чем на 10 % FPS. |
| **NFR-11** | Лимит одновременных subagent'ов конфигурируем (по умолчанию 4). |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI dialog `dialog-agent.tsx` + status-bar agent indicator + CLI `opencode agent` (create/list). |
| **User Entry Points** | `Tab`, `dialog-agent`, `@mention`, `opencode agent create`, `opencode agent list`. |
| **Main Screens / Commands** | Agent picker dialog с фильтрами (primary/subagent), agent-create wizard (CLI prompts через `@clack/prompts`). |
| **Input / Output Format** | Markdown с YAML frontmatter (`name`, `description`, `mode`, `permission`, `model`, `temperature`, `topP`, `prompt`). |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Agent` (`packages/opencode/src/agent/agent.ts`) — Effect-based service. |
| **Responsibility** | Loading агентов из конфига и markdown, merge с defaults, генерация новых, lookup при `@mention`. |
| **Business Logic** | `agent.list()` сканит директории; `agent.get(name)` возвращает Info; `agent.generate(input)` вызывает LLM; `agent.defaultAgent()` определяется конфигом. |
| **API / Contract** | `GET /project/:projectID/agent?directory=<path>` → `Agent.Info[]`. |
| **Request Schema** | `{ name, description, mode, model?, prompt?, permission, options }`. |
| **Response Schema** | `Agent.Info` (см. `Schema.Struct({ name, description?, mode, native?, hidden?, topP?, temperature?, color?, permission, model?, variant?, prompt?, options, steps? })`). |
| **Error Handling** | `AgentNotFound`, `AgentInvalidFrontmatter`, `AgentGenerationFailed`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Agent.Info`, `Permission.Ruleset`, `Provider.Model`. |
| **Relationships (ER)** | Agent N—1 Provider/Model (через override); Agent 1—N Permission.Rule; Session N—1 Active Agent (на каждое сообщение). |
| **Data Flow (DFD)** | FS scan (`~/.config/opencode/agents/*.md`, `.opencode/agents/*.md`) → gray-matter parse → schema validate → merge defaults → cache → consumed by Session/Tool layers. |
| **Input Sources** | YAML frontmatter в md-файлах; `opencode.json` поле `agent`; bundled defaults; LLM-выход для generate. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Никаких дополнительных ресурсов сверх Feature 1; чтение/запись md-файлов в config-директорию. |
| Для генерации custom-агентов — доступ к LLM-провайдеру (модель ≥ Claude Sonnet/GPT-4-class). |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Реализация permission-default'ов для `plan` | Permission service | `plan` вызывает `ask` для edit/bash | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Session-level permission overrides на `Always` | T-1 | Always применяется до конца сессии | ST-4, ST-5 |
| UC-2.1 | T-3 | CLI `opencode agent create` + LLM generate | Provider, Auth | Команда создаёт корректный md | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | `@mention` parsing и subagent-инвокация | T-3 | Subagent работает в child-session | ST-9, ST-10 |
| UC-3.1 | T-5 | Parallel `task` execution через `general` | T-4 | До 4 параллельных задач | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Определить и захардкодить default permission-набор для встроенных `build` и `plan` агентов через `Permission.fromConfig`. |
| **Dependencies** | Permission service. |
| **DoD** | Тесты на `plan`: edit/bash требуют ask, read/grep/glob — allow. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Описать defaults в `agent.ts` и whitelisted dirs (Truncate.GLOB, tmp, skills) | — | Юнит-тест проходит |
| ST-2 | Реализовать merge user-permission поверх defaults | ST-1 | Override работает |
| ST-3 | Документация в `docs/agents.mdx` | ST-1 | Раздел Plan описан |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализовать `Always`-ответ как session-scope permission. |
| **Dependencies** | T-1 |
| **DoD** | После Always дальнейшие edits идут без prompt в той же сессии. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Расширение `PermissionTable` SQL-схемы и API `/permission/:id` для `always` | T-1 | Запись сохраняется |
| ST-5 | Команда `/permission reset` в TUI | ST-4 | Сбрасывает session permissions |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | CLI `opencode agent create` с LLM-генерацией identifier + systemPrompt и сохранением md. |
| **Dependencies** | Provider, Auth |
| **DoD** | Команда успешно создаёт md, который проходит schema-валидацию. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Прокинуть prompt `agent/generate.txt` и schema через `generateObject` | — | Возвращает валидный JSON |
| ST-7 | Записать markdown с frontmatter через gray-matter | ST-6 | Файл парсится обратно |
| ST-8 | Добавить интерактивные prompts (path/mode/model) | ST-6 | UX без ошибок |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Поддержка `@<agent>` в input-text и инвокация subagent через `task`-tool. |
| **Dependencies** | T-3 |
| **DoD** | Mention резолвится в правильный subagent, child-session создаётся с `parentID`. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Парсер `@`-mention в input layer | T-3 | `@general` распознаётся |
| ST-10 | Mapping mention → `task`-tool input | ST-9 | task выполняется |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Параллельный запуск нескольких `task`-tool вызовов в одном assistant step. |
| **Dependencies** | T-4 |
| **DoD** | До 4 одновременных subagent'ов, лимит конфигурируется. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Concurrency control в `task`-tool execution | T-4 | Не превышает лимит |
| ST-12 | Aggregation результатов в parent message | ST-11 | UI рендерит все task-parts |

---

# Feature 3 — Multi-Provider LLM Integration

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Multi-Provider LLM Integration |
| **Description (Goal / Scope)** | Возможность использовать любую LLM-модель: Anthropic Claude, OpenAI GPT, Google Gemini, GitHub Copilot, Azure OpenAI, Cloudflare Workers AI, OpenCode Zen, локальные через Ollama/LM Studio. Включает аутентификацию (`opencode auth login`) с OAuth для Anthropic/Copilot, API-key flow, единый адаптер `Provider.transform` к разным API, маршрутизацию запросов, фоллбэк при отказе, выбор модели и provider-specific variant'ов (high/max/minimal — reasoning effort). Scope: provider-схема, transform-слой, OAuth-flow, ModelsDev integration, диалоги `dialog-provider`/`dialog-model`/`dialog-variant`. |
| **Client** | Все пользователи opencode; в особенности enterprise (через Azure/Bedrock/Vertex), self-hosters (через Ollama), ценящие приватность. |
| **Problem** | Большинство AI-coding tools привязаны к одному вендору. Это создаёт vendor lock-in, повышает риск (квоты, цены), не даёт использовать корпоративный аккаунт (Copilot Business, Azure-deployment) или локальные модели (privacy). |
| **Solution** | Абстракция `Provider`: каждый провайдер описывается JSON-конфигом из ModelsDev (или кастомного), реализация общается через `ai`-SDK (Vercel AI SDK) с уникальным adapter'ом; OAuth-flow для Anthropic/Copilot через локальный callback; API-key для остальных; локальные модели через OpenAI-совместимые endpoint'ы. Provider-specific options («reasoning effort», «thinking») передаются через `variant`. |
| **Metrics** | • Поддержка ≥ 8 провайдеров out-of-the-box<br>• Среднее время `auth login` ≤ 30 сек<br>• % сессий с не-default провайдером ≥ 40 %<br>• Доля провайдеров с поддержкой OAuth ≥ 2 (Anthropic, Copilot)<br>• Latency penalty абстракции ≤ 5 % vs прямой SDK |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Пользователь Anthropic Claude |
| **User Story ID** | US-1 |
| **User Story** | As a Claude-пользователь, I want авторизоваться через OAuth Anthropic Console, so that не передавать raw API key в файлы и использовать subscription Claude Pro/Max. |
| **UX / User Flow** | 1. `opencode auth login`. 2. Выбрать `anthropic`. 3. Открывается локальный callback-сервер, в браузере — auth-страница. 4. После успеха токен сохраняется в keychain/file. 5. В TUI становится доступной модель Claude. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Пользователь не авторизован, имеет аккаунт Anthropic Console. |
| **When** | Запускает `opencode auth login` и выбирает `anthropic`. |
| **Then** | Стартует локальный HTTP listener на свободном порту, открывается браузер с OAuth URL, после redirect token приходит на callback и сохраняется в `auth.json` (encrypted при возможности). |
| **Input** | CLI выбор провайдера; user grants permission в браузере. |
| **Output** | Файл `~/.local/share/opencode/auth.json` с access/refresh-token; команда выводит `✓ Logged in as <user>`. |
| **State** | `Auth.Service` теперь возвращает credential для `anthropic`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Локальный callback должен слушать на 127.0.0.1 со случайным портом, использовать PKCE. |
| **FR-2** | Refresh token должен автоматически обновляться при экспирации до отправки запроса. |
| **FR-3** | Должна быть команда `opencode auth list` и `opencode auth logout <provider>`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Token-файл должен быть `chmod 600`. |
| **NFR-2** | Refresh-flow не должен задерживать первый запрос > 1 сек если токен уже валиден. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Пользователь авторизован, ввёл сообщение, активная модель — `anthropic/claude-sonnet-4-5`. |
| **When** | TUI отправляет сообщение → сервер делает запрос к Anthropic. |
| **Then** | Через `ai`-SDK с anthropic-adapter и system-prompt из `session/prompt/anthropic.txt`, идёт streaming response. |
| **Input** | Messages, tools, system prompt, model, max_tokens. |
| **Output** | Streamed `Part`s; usage usage statistics — input/output/cache tokens. |
| **State** | Session `usage` accum по сообщениям; provider statistics. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Для anthropic должен использоваться prompt-caching (cache_control) для system prompt и tool definitions. |
| **FR-5** | Должна сохраняться/применяться correct rate-limit error semantics (`429`, `Retry-After`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Cache hit rate ≥ 60 % после 3-го сообщения в долгой сессии. |
| **NFR-5** | Streaming chunk-to-render задержка ≤ 80 мс. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Self-hoster / privacy-сознательный |
| **User Story ID** | US-2 |
| **User Story** | As a self-hoster, I want подключить локальный Ollama-сервер с моделью `qwen2.5-coder`, so that не отправлять код в облако. |
| **UX / User Flow** | 1. Запустить `ollama serve` локально. 2. В `opencode.json` добавить custom-провайдер с `npm: "@ai-sdk/openai-compatible"`, baseURL `http://localhost:11434/v1`, models. 3. В TUI открыть `dialog-model` → выбрать локальную модель. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Файл `opencode.json` содержит блок `provider.local`. |
| **When** | Сервер бутстрапит и читает `Config.get()`. |
| **Then** | `Provider.Service` регистрирует local-провайдера, `dialog-model` показывает его модели. |
| **Input** | JSON config: `{ provider: { local: { npm, options: { baseURL }, models: { ... } } } }`. |
| **Output** | Список моделей провайдера в API. |
| **State** | Cached в memory provider registry. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Custom-провайдеры должны мерджиться поверх ModelsDev defaults. |
| **FR-7** | Поддерживать переопределение `apiKey`, `baseURL`, `headers` per provider. |
| **FR-8** | Variants — массив тонких настроек reasoning, доступных как `--variant high`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Загрузка provider-config ≤ 100 мс. |
| **NFR-7** | Если provider недоступен (timeout `connect`), показать понятную ошибку без падения сервера. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Локальная модель сконфигурирована, активна в TUI. |
| **When** | Пользователь шлёт сообщение, ollama сервер зависает или возвращает 500. |
| **Then** | TUI показывает структурированную ошибку «Provider unavailable: local — connection refused», предлагает retry или сменить модель. |
| **Input** | Network error / 5xx response. |
| **Output** | Error message в чате как assistant-error part; retry-button. |
| **State** | Сессия не break, можно продолжить с другим провайдером. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Ошибки провайдера должны нормализоваться в `NamedError` (ProviderUnavailable, ProviderRateLimit, etc.). |
| **FR-10** | Retry-policy: до 3 попыток с exponential backoff на сетевых ошибках. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Backoff не должен превышать 30 сек суммарно. |
| **NFR-9** | Сообщение об ошибке должно быть локализовано (en/zh/ru/...). |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want быстро переключать модели через диалог (`Ctrl+M`), so that пробовать разные модели на одном вопросе и сравнивать ответы. |
| **UX / User Flow** | 1. В TUI нажать `Ctrl+M` → открывается `dialog-model` с группировкой по провайдерам. 2. Поиск по имени модели. 3. Enter → активная модель меняется на следующее сообщение. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Авторизовано минимум 2 провайдера, в TUI открыта сессия. |
| **When** | Пользователь нажимает `Ctrl+M`, открывается диалог. |
| **Then** | Видны все доступные модели сгруппированные по провайдеру; выбор и `Enter` обновляет `session.model`. |
| **Input** | Keyboard navigation. |
| **Output** | Status-bar обновляет название модели; следующее сообщение использует новую модель. |
| **State** | `session.model = { providerID, modelID }`; persist в БД. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Список моделей должен быть отсортирован: pinned/recent → all. |
| **FR-12** | Должен поддерживаться `dialog-variant` для выбора reasoning effort. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Диалог открывается ≤ 100 мс. |
| **NFR-11** | Список ≥ 200 моделей не тормозит UI (виртуализация). |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI dialogs (`dialog-provider.tsx`, `dialog-model.tsx`, `dialog-variant.tsx`) + CLI `opencode auth login/list/logout` + `opencode providers`/`opencode models`. |
| **User Entry Points** | `Ctrl+M`, `Ctrl+P`, `opencode auth …`, `opencode run --model <provider/model>`. |
| **Main Screens / Commands** | Provider list, model picker (с группировкой), variant selector. |
| **Input / Output Format** | `model: "<providerID>/<modelID>"`; variant: string; auth: OAuth flow или API key prompt. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Provider.Service` (`packages/opencode/src/provider/`), `Auth.Service`, `ModelsDev.Service`. |
| **Responsibility** | Загрузка провайдер-конфигов (bundled + ModelsDev + user); инстанцирование adapter'ов; routing inference; обновление credential'ов. |
| **Business Logic** | На каждый запрос: pick model → resolve provider → load credential → instantiate `ai`-adapter → apply transform (system prompt, tools, cache_control) → stream. |
| **API / Contract** | `GET /provider?directory=...` → список провайдеров и моделей; `POST /auth/<provider>/login` → стартует OAuth; `GET /models` → flat list. |
| **Request Schema** | `{ providerID, modelID, variant? }`. |
| **Response Schema** | `Provider.Info` с моделями: `{ id, name, models: { id, name, contextWindow, capabilities } }`. |
| **Error Handling** | `ProviderUnauthorized`, `ProviderRateLimit`, `ProviderUnavailable`, `ProviderInvalidConfig`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Provider`, `Model`, `Variant`, `Auth.Credential`. |
| **Relationships (ER)** | Provider 1—N Model; Provider 1—1 Auth (или 1—N для multi-account); Session N—1 Active Model. |
| **Data Flow (DFD)** | ModelsDev API + bundled JSON + user config → Provider registry → on-demand adapter instantiation → Anthropic/OpenAI/Google REST → stream → Session. |
| **Input Sources** | `models.dev` API; bundled `meta.ts` defaults; user `opencode.json` `provider` блок; OS keychain (где доступно). |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Outbound HTTPS до выбранных провайдеров; локальный TCP listener для OAuth callback. |
| Для локальных моделей: достаточный RAM/VRAM (за рамками opencode). |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | OAuth flow для Anthropic + Copilot | Auth, Server | Token сохраняется и refresh работает | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Anthropic adapter с prompt caching | T-1 | Caching метрики ≥ 60 % | ST-4, ST-5 |
| UC-2.1 | T-3 | Custom provider config + ModelsDev merge | Config | Local Ollama работает | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Унифицированная error normalization + retry | T-3 | Retries и UX-error реализованы | ST-9, ST-10 |
| UC-3.1 | T-5 | TUI dialog-model с поиском и группировкой | TUI | Диалог открывается ≤ 100 мс | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать OAuth-callback сервер и flow для Anthropic Console и GitHub Copilot. |
| **Dependencies** | Auth-service, http-server. |
| **DoD** | `opencode auth login` для anthropic/copilot полностью проходит, tokens работают. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Локальный callback http listener с PKCE | — | Получает code |
| ST-2 | Token exchange и сохранение в `auth.json` | ST-1 | File `chmod 600` |
| ST-3 | Refresh-token logic | ST-2 | Авто-refresh при 401 |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Anthropic-specific adapter и transform-layer (cache_control, prompt files). |
| **Dependencies** | T-1 |
| **DoD** | Caching работает, tools передаются корректно, streaming идёт. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | `provider/transform.ts` для anthropic с cache_control | T-1 | Cache hit ≥ 60 % |
| ST-5 | System-prompt mapping `session/prompt/anthropic.txt` | T-1 | Использует bundled prompt |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Поддержка custom provider в config с merge ModelsDev defaults. |
| **Dependencies** | Config |
| **DoD** | Local Ollama настраивается за < 5 мин по docs. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Schema для custom provider в `cli/config.ts` | — | Schema валидна |
| ST-7 | Lazy load `npm`-пакета adapter'а | ST-6 | Не падает если пакет отсутствует |
| ST-8 | Доки `docs/providers.mdx` | — | Обновлены |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Нормализация ошибок и retry. |
| **Dependencies** | T-3 |
| **DoD** | Сетевые ошибки → понятные сообщения; retry с backoff. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Mapping HTTP errors → `NamedError` | T-3 | Все основные ошибки покрыты |
| ST-10 | Retry policy с jitter | ST-9 | Не более 3 попыток |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | TUI dialog `dialog-model.tsx` с поиском, группировкой по провайдеру, variants. |
| **Dependencies** | TUI |
| **DoD** | Диалог быстрый, удобный, поддерживает 200+ моделей. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | UI компонент с виртуализацией | — | Open ≤ 100 мс |
| ST-12 | Persist последних N выбранных моделей | ST-11 | Сортировка работает |

---

# Feature 4 — Built-in Tools & MCP Integration

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Built-in Tools & MCP Integration |
| **Description (Goal / Scope)** | Полный набор встроенных инструментов агента: `read`, `write`, `edit`, `apply_patch`, `bash`, `glob`, `grep`, `task`, `todowrite`, `webfetch`, `websearch` (Exa), `lsp`, `skill`, `question`, `plan_enter`/`plan_exit`. Интеграция Model Context Protocol — добавление local (stdio) и remote (HTTP) MCP-серверов с OAuth-поддержкой; их инструменты автоматически становятся доступны LLM наряду со встроенными. Scope: tool-registry, tool-схемы (zod), execution layer, truncation, MCP client (`@modelcontextprotocol/sdk`), MCP auth-flow, конфиг `mcp` в `opencode.json`. |
| **Client** | Все пользователи opencode; dev-team расширяющие агента под себя через MCP (например, GitHub MCP для issue-tracking, Linear MCP, кастомные внутренние tools). |
| **Problem** | LLM сам по себе не может работать с файлами, выполнять команды, искать в интернете. Каждой команде нужен расширяемый набор tools, причём поддерживающий стандарт (MCP), чтобы переиспользовать готовые сервера. |
| **Solution** | Tool-Registry: набор bundled tools с typed-зод-схемами; за каждым tool — TS-функция execute с return result + metadata. MCP-интеграция через `Client`/`StreamableHTTPClientTransport`, авто-listing tools + transparent proxy. Truncation для больших output'ов. Permission-проверки на каждый вызов. |
| **Metrics** | • ≥ 12 встроенных tools<br>• Время старта MCP-сервера ≤ 3 сек (locally)<br>• ≥ 20 % сессий используют ≥ 1 MCP-tool<br>• Tool execution timeout default 60 сек, конфигурируемый<br>• Output truncation срабатывает корректно при > 50 KB |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Разработчик |
| **User Story ID** | US-1 |
| **User Story** | As a разработчик, I want чтобы агент мог точечно править файлы (старая → новая строка) без перезаписи всего файла, so that diff-ы были минимальные и безопасные. |
| **UX / User Flow** | 1. Пользователь: «исправь typo в `README.md` строке про installation». 2. Агент вызывает `read README.md` → `edit { filePath, oldString, newString }`. 3. TUI рендерит unified-diff превью; permission-prompt при необходимости. 4. После apply — обновлённый файл. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Файл существует, последний `read` зарегистрирован в session-state. |
| **When** | LLM вызывает `edit({filePath, oldString, newString, replaceAll?})`. |
| **Then** | Tool валидирует уникальность `oldString`, генерирует `diff`, при необходимости запрашивает permission, применяет patch, сохраняет файл, возвращает metadata `{ diff, oldLines, newLines }`. |
| **Input** | `{filePath, oldString, newString, replaceAll}`. |
| **Output** | Обновлённый файл; `Tool.Result` с `output` и `metadata.diff`. |
| **State** | LSP получает `textDocument/didChange` (если LSP активен); snapshot создаётся перед изменением. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | `edit` должен fail-fast если `oldString` встречается > 1 раз и `replaceAll=false`. |
| **FR-2** | До применения должен быть зарегистрирован `read` того же файла в текущей сессии (правило защиты от слепой записи). |
| **FR-3** | После изменения tool возвращает unified diff и количество добавленных/удалённых строк. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Edit на файле до 1 MB ≤ 50 мс. |
| **NFR-2** | Snapshot позволяет revert через `POST /session/:id/revert`. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | `bash`-tool вызывает long-running команду `npm test`. |
| **When** | Команда работает > 60 сек или output > 50 KB. |
| **Then** | Output truncates middle/tail; команда либо завершается timeout'ом с понятной ошибкой, либо truncate-info попадает в metadata. |
| **Input** | `{command, timeout?, description}`. |
| **Output** | `{output, truncated: boolean, exitCode}`. |
| **State** | Если timeout — child процесс убит SIGTERM → SIGKILL. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Bash должен выполнять через cross-spawn или Bun shell, c корректным escape. |
| **FR-5** | Truncation должна сохранять head/tail (кратко в середине). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Утечки child-процессов не допускаются (atexit kill всех children). |
| **NFR-5** | `bash` поддерживает background-mode для серверов. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Разработчик с GitHub-проектами |
| **User Story ID** | US-2 |
| **User Story** | As a разработчик, I want добавить GitHub MCP server, so that агент мог читать issues/PRs/comments прямо из чата. |
| **UX / User Flow** | 1. Добавить в `opencode.json`: `mcp.github = { type: "remote", url: "https://api.githubcopilot.com/mcp/", oauth: true }`. 2. `opencode mcp login github` → пройти OAuth. 3. В TUI задать «прочитай issue #42 и предложи фикс» — агент использует `mcp__github__get_issue`. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | В config есть конфигурация MCP-сервера типа `remote` с `oauth: true`. |
| **When** | Пользователь выполняет `opencode mcp login <name>`. |
| **Then** | Стартует OAuth-flow через `McpOAuthProvider`, токен сохраняется, `mcp.status()` показывает `authenticated`. |
| **Input** | Конфиг + user OAuth grant. |
| **Output** | Token-record; `MCP.Service` инициализирует client. |
| **State** | Tools этого MCP-сервера автоматически зарегистрированы в registry на следующем sync. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | MCP-tools должны иметь префикс `mcp__<server>__<tool>` для избежания коллизий. |
| **FR-7** | `mcp.status()` возвращает `authenticated|expired|not_authenticated` для каждого. |
| **FR-8** | При `expired` состоянии — авто-refresh при первом обращении. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Discover tools от MCP ≤ 5 сек. |
| **NFR-7** | Обработка disconnect — graceful reconnect с backoff. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | MCP-сервер сконфигурирован как `local` (stdio): `{ type: "local", command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"] }`. |
| **When** | Сервер opencode стартует и пытается активировать MCP. |
| **Then** | Spawns child process, выполняется handshake `initialize` → `tools/list` → tools регистрируются. |
| **Input** | Команда + аргументы. |
| **Output** | Активный stdio MCP client в memory. |
| **State** | Lifecycle привязан к серверу — при остановке сервера child тоже kill'ается. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Local MCP должен пробрасывать `env` overrides (если указано). |
| **FR-10** | Stderr child процесса должен попадать в opencode log с prefix'ом server-name. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Падение local MCP сервера не должно ронять opencode. |
| **NFR-9** | Должна быть команда `opencode mcp restart <name>`. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want чтобы агент мог искать по интернету через `websearch` или fetch'ить URL через `webfetch`, so that получать актуальную информацию которой нет в knowledge cutoff. |
| **UX / User Flow** | 1. Спросить «опиши последние изменения в Bun 1.3». 2. Агент вызывает `websearch { query: "Bun 1.3 release notes" }` (Exa.ai). 3. Затем `webfetch` на лучший URL. 4. Финальный ответ с цитатами. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Tool `websearch` сконфигурирован (через Exa-token или OpenCode Zen). |
| **When** | LLM вызывает `websearch({query})`. |
| **Then** | Делается запрос к Exa, возвращается список result с title/url/snippet, агент решает дальше что fetch'ить. |
| **Input** | `{query, numResults?}`. |
| **Output** | `{results: [{title, url, snippet}]}`. |
| **State** | Stateless. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Должна быть отдельная permission `websearch` (default — `allow`). |
| **FR-12** | `webfetch` должен корректно обрабатывать редиректы и не превышать 5 редиректов. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Webfetch timeout default 30 сек. |
| **NFR-11** | Размер ответа truncate'ится при > 100 KB. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI tool-renderers (`run.ts`-стиль), `dialog-mcp.tsx`, CLI `opencode mcp <list|login|logout|restart>`. |
| **User Entry Points** | LLM-инициированные tool calls; `opencode mcp` CLI; конфиг. |
| **Main Screens / Commands** | MCP picker, MCP-status indicator в status-bar, tool execution panes. |
| **Input / Output Format** | Tool input — zod-схема per tool. Tool output — `{ output: string, metadata: object, status }`. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Tool.Service` (`packages/opencode/src/tool/registry.ts`), `MCP.Service` (`packages/opencode/src/mcp/`), `MCP.Auth`. |
| **Responsibility** | Регистрация bundled+plugin+MCP tools; вызов с permission-проверкой; truncation; lifecycle MCP-clients. |
| **Business Logic** | Builder собирает tools per agent (учёт permissions); LLM вызывает → tool execute → возвращается structured result; events публикуются в bus. |
| **API / Contract** | Внутренний interface `ToolDefinition { name, description, parameters, execute }`; для MCP — `mcp.tools()` возвращает unified list. |
| **Request Schema** | Tool-specific zod schemas; для MCP — JSON-RPC 2.0 `tools/call`. |
| **Response Schema** | `Tool.Result` с дискриминированным union (success/error). |
| **Error Handling** | Типизированные ошибки `ToolNotFound`, `ToolValidationError`, `ToolExecutionError`, `MCPDisconnected`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Tool.Def`, `MCP.Server.Config`, `MCP.Token`, `Tool.Invocation`, `Truncation.Policy`. |
| **Relationships (ER)** | Tool 1—N Invocation; MCP-Server 1—N Tool; Session 1—N Invocation. |
| **Data Flow (DFD)** | LLM → tool registry → permission gate → execute → optional MCP transport → result → truncate → bus event → session message. |
| **Input Sources** | Bundled `.txt` prompt-файлы для каждого tool; `opencode.json` `mcp` секция; user file system; интернет (webfetch/search). |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Достаточно прав на запись в текущий проект и `~/.cache/opencode`. |
| Outbound HTTPS для webfetch/websearch и remote MCP. |
| Доступная stdio для local MCP servers. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Реализация bundled `edit` + `apply_patch` | Permission, FS | Edit с уникальностью, diff metadata | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Bash-tool с timeout/truncate/cleanup | Permission | Timeout/truncate работают | ST-4, ST-5 |
| UC-2.1 | T-3 | Remote MCP с OAuth | Auth, MCP SDK | OAuth + tool-listing работают | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Local stdio MCP с lifecycle | T-3 | Local MCP корректно завершается | ST-9, ST-10 |
| UC-3.1 | T-5 | Websearch (Exa) + Webfetch | Provider | Поиск + fetch работают | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать bundled-tools `edit`, `write`, `apply_patch`, `read` с zod-схемами и pre-edit-read enforcement. |
| **Dependencies** | Permission, FS. |
| **DoD** | Все три работают, тесты на уникальность oldString и pre-edit-read проходят. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Schema + execute для `edit` | — | Diff metadata возвращается |
| ST-2 | Schema + execute для `write`/`read` | — | Перезапись и чтение |
| ST-3 | `apply_patch` (multi-hunk) | ST-1 | Поддержка multi-hunk |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализовать `bash`-tool с timeout, truncate, корректной cleanup-логикой child-процессов. |
| **Dependencies** | Permission |
| **DoD** | Long-running команды убиваются по timeout; output truncate; нет утечек. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Spawner с timeout + signal escalation | — | Завершает SIGKILL при необходимости |
| ST-5 | Truncation policy (head/tail middle-omit) | ST-4 | 50 KB предел соблюдается |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Поддержка remote MCP с OAuth (`StreamableHTTPClientTransport`). |
| **Dependencies** | Auth, MCP SDK |
| **DoD** | OAuth-flow проходит, tools видны и работают. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | `McpOAuthProvider` + callback | — | Token сохраняется |
| ST-7 | Tool listing + caching | ST-6 | TTL 5 мин |
| ST-8 | CLI `opencode mcp login/logout` | ST-6 | Команды работают |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Поддержка local stdio MCP с lifecycle и логированием stderr. |
| **Dependencies** | T-3 |
| **DoD** | Local MCP стартует, tools listed, child-процесс корректно завершается. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Spawner stdio + handshake | T-3 | `initialize` ok |
| ST-10 | Auto-restart при крахе (опционально) | ST-9 | Restart работает |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Реализовать `websearch` (Exa) и `webfetch` с правильными timeout'ами и truncation. |
| **Dependencies** | Provider |
| **DoD** | Tools работают за разумное время, ошибки понятные. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Exa client с retry | — | 3 попытки с backoff |
| ST-12 | Webfetch с redirect-limit и size-cap | — | 5 редиректов / 100 KB |

---

# Feature 5 — Sessions, Multi-Project, Worktrees & Sharing

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Sessions, Multi-Project, Worktrees & Sharing |
| **Description (Goal / Scope)** | Возможность одной инсталляции `opencode` управлять множеством проектов, для каждого — несколько worktree, для каждого worktree — множество сессий. Сессии поддерживают: создание/удаление, fork (чтобы продолжать ветвление), revert/unrevert (откат к снапшоту), abort (прерывание стрима), compact (сжатие истории при превышении токенов), share (публичный URL `opncd.ai/s/<id>`). Хранится в SQLite (Drizzle) с миграциями. Scope: Project-/Session-/Message-/Part-сущности, snapshot/revert механика, summarisation, compaction, share-URL flow, multi-project routing. |
| **Client** | Разработчики работающие на нескольких проектах одновременно; команды, которым нужна постоянная история диалогов; пользователи, делящиеся сессиями для code-review или troubleshooting. |
| **Problem** | Без многосессионной модели нельзя ни прервать долгий запрос, ни вернуться к ветке в обсуждении, ни использовать один процесс/сервер для нескольких проектов. Без compaction длинные сессии упираются в context window. Без share — обмен идёт через скриншоты. |
| **Solution** | Project-aware backend (`/project/:projectID/...`); SQLite-схема Sessions (с `parentID` для fork), Messages, Parts, Permission. Snapshots создаются перед потенциально-деструктивными операциями (edit/write/bash). Compaction: `summary.txt` prompt сжимает старые сообщения в summary. Share: создаёт share-id и пушит изменения в облачный sync-сервис, доступный по public URL. |
| **Metrics** | • Среднее число активных проектов на пользователя ≥ 2<br>• Доля сессий с >1 fork ≥ 10 %<br>• Compaction срабатывает в ≥ 80 % случаев перед context-overflow<br>• Share-URL генерится ≤ 2 сек<br>• Чтение последних 50 сессий ≤ 200 мс |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Разработчик с несколькими проектами |
| **User Story ID** | US-1 |
| **User Story** | As a разработчик, I want, чтобы один процесс opencode-server работал с несколькими проектами и worktrees параллельно, so that не запускать несколько серверов и переключаться без потери контекста. |
| **UX / User Flow** | 1. `opencode` в `~/projects/api`. 2. Открыть второй терминал, `cd ~/projects/web && opencode --attach http://localhost:4096` — TUI присоединяется к тому же серверу, но работает в проекте `web`. 3. Сессии каждого проекта изолированы. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Сервер запущен, в нём уже есть Project `api`. |
| **When** | TUI делает `POST /project/init` с `directory=/home/u/web`. |
| **Then** | Сервер резолвит canonical project root (git rev-parse), создаёт Project record (если новый) с привязкой к worktree, возвращает `Project.Info`. |
| **Input** | `directory` (path). |
| **Output** | `Project { id, name, path, worktree }`. |
| **State** | Запись в `project` SQLite-таблице; добавление в memory-кэш. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | `Project.id` детерминированный по path (хэш / canonical resolve). |
| **FR-2** | Worktree-aware: для одного git-репо разные worktree получают разные Project.id. |
| **FR-3** | `GET /project` возвращает все известные проекты. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Кэш проектов hit ≥ 95 % на повторных обращениях. |
| **NFR-2** | Запрос `/project/init` ≤ 100 мс. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Активная сессия в проекте `api`, пользователь начал разговор. |
| **When** | LLM делает edit-tool, потом пользователь решил продолжить альтернативную ветку («а что если сделать иначе»). |
| **Then** | Пользователь нажимает «Fork» → создаётся новая сессия с `parentID = текущая`, наследует историю до точки fork'а; продолжается отдельно. |
| **Input** | UI-fork action или `POST /session` с `{ parentID, ... }`. |
| **Output** | Новая `Session` запись; UI переключается на неё. |
| **State** | Параллельные ветки в БД; первоначальная сохраняется. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Fork должен делать deep-clone истории до текущего message. |
| **FR-5** | Должна быть возможность вернуться к parent-сессии. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Fork сессии длиной 100 сообщений ≤ 200 мс. |
| **NFR-5** | Целостность: foreign keys и cascading delete тестами покрыты. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Разработчик в долгой сессии |
| **User Story ID** | US-2 |
| **User Story** | As a разработчик, I want автоматически (или по `/compact`) сжимать старую историю при подходе к лимиту контекста, so that не получать ошибку «context length exceeded» и не терять важные детали. |
| **UX / User Flow** | 1. Сессия > N% контекста — статус-бар показывает warning. 2. Пользователь вводит `/compact` или система сжимает автоматически. 3. Старые сообщения заменяются на summary-message; продолжается далее. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Сессия достигла configured threshold (например 70 % context). |
| **When** | `POST /session/:id/compact` или auto-trigger. |
| **Then** | Берутся первые N сообщений → отправляются в LLM с `summary.txt` prompt → результирующее summary заменяет их в session-state; новая длина ≤ 30 % контекста. |
| **Input** | `sessionID`. |
| **Output** | Compacted session с `summary`-message. |
| **State** | `session.run_state = "compacting"` → `idle`; старые messages помечаются `archived`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Должна сохраняться история (archived), не теряется. |
| **FR-7** | Compaction должна сохранить ссылки на ключевые artifacts (файлы, todos). |
| **FR-8** | Auto-compaction конфигурируется в `opencode.json` (`compact: { auto: true, threshold: 0.7 }`). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Compaction ≤ 15 сек на сессию из 200 сообщений. |
| **NFR-7** | Не должно прерывать активный stream. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | LLM сделал ряд edit-операций, пользователь хочет откатить. |
| **When** | Выполняется `POST /session/:id/revert` с указанием snapshot id. |
| **Then** | Сессия возвращается к состоянию snapshot'а (файлы и история); отменённые сообщения помечаются как reverted. |
| **Input** | `sessionID`, `messageID` или `partID`. |
| **Output** | Восстановленный Session-state. |
| **State** | Snapshot восстановлен на FS, Messages помечены revert'нутыми. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Revert восстанавливает FS (через `Snapshot`-service) и помечает messages. |
| **FR-10** | `unrevert` должен возвращать вперёд (redo). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Snapshots сохраняются в `git`-style object store (content-addressed). |
| **NFR-9** | Не должно превышать 2x размера workspace на диске. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want шарить интересную сессию через короткий URL, so that отправить коллеге для ревью или вопроса, без копипасты. |
| **UX / User Flow** | 1. В TUI ввести `/share`. 2. URL копируется в clipboard и отображается в чате. 3. Коллега открывает URL → видит read-only страницу с историей. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Sharing включён в конфиге (`share: "manual"` или `"auto"`). |
| **When** | Пользователь выполняет `/share` → `POST /session/:id/share`. |
| **Then** | Создаётся share-id, сессия синхронизируется в облако, URL `opncd.ai/s/<id>` возвращается. |
| **Input** | `sessionID`. |
| **Output** | `{ url, shareID }`. |
| **State** | Sync поддерживает delta-обновления при новых сообщениях. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Должна быть команда `/unshare` для удаления share. |
| **FR-12** | Share-данные удаляются с серверов после `unshare` или TTL. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Share-URL должен быть ≤ 30 символов и не угадываемым (random 12+ chars). |
| **NFR-11** | Сессии конфигурируются как «никогда не sharable» опцией `share: "disabled"`. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI commands (`/share`, `/unshare`, `/compact`, `/fork`, `/revert`), `dialog-session-list`, `dialog-session-rename`, `dialog-session-delete-failed`. |
| **User Entry Points** | Slash commands в input; dialog session list (по `Ctrl+L`); CLI `opencode session list/share/delete`. |
| **Main Screens / Commands** | Session list, share confirm modal, compact-progress overlay. |
| **Input / Output Format** | Slash commands → REST вызовы. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Session.Service`, `Project.Service`, `Snapshot.Service`, `Share.Service`, `Compaction`. |
| **Responsibility** | CRUD сессий и сообщений; fork/revert/compact; sharing. |
| **Business Logic** | Session FSM (idle → running → awaiting_permission → idle / aborted); хуки на edit/write/bash для snapshots; auto-compact when threshold; share-sync через outbound HTTPS. |
| **API / Contract** | Полный набор `/project/:projectID/session/...` (см. `specs/project.md`). |
| **Request Schema** | См. spec; примеры: create `{ id?, parentID?, directory }`. |
| **Response Schema** | `Session`, `Message`, `Part`, `File`. |
| **Error Handling** | `SessionNotFound`, `SessionLocked`, `SnapshotMissing`, `ShareDisabled`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Project`, `Worktree`, `Session`, `Message`, `Part`, `Snapshot`, `Share`, `PermissionRequest`. |
| **Relationships (ER)** | Project 1—N Session; Session 1—N Message; Message 1—N Part; Session 1—1? Share; Session 1—N Snapshot; Session N—1 ParentSession (self-ref). |
| **Data Flow (DFD)** | TUI → REST → Session.Service → Drizzle ORM → SQLite (file `~/.local/share/opencode/storage.db`); Snapshot.Service → object-store (git-like) → FS restore on revert; Share.Service → opncd.ai sync API. |
| **Input Sources** | User input; LLM responses; tool results; FS snapshots. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Локальный SQLite файл (≤ 500 MB на типичного пользователя). |
| Snapshot store: до 2x размера worktree на диске. |
| Для share — опциональная облачная зависимость opncd.ai (HTTPS). |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Project init + canonicalisation | DB | `/project/init` стабильно идемпотентен | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Session fork | T-1 | Fork создаёт независимую ветку | ST-4, ST-5 |
| UC-2.1 | T-3 | Compaction (manual + auto) | Provider | Compaction сжимает контекст ≤ 30 % | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Snapshot + revert/unrevert | FS | Revert восстанавливает FS и историю | ST-9, ST-10 |
| UC-3.1 | T-5 | Share/Unshare с opncd.ai | Net | Share URL работает | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать project canonicalisation, multi-worktree-aware identity. |
| **Dependencies** | DB. |
| **DoD** | Идентичный путь даёт идентичный Project.id; разные worktree → разные Projects. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | `Project.resolve(path)` через git rev-parse | — | Стабильный id |
| ST-2 | Drizzle-схема + миграция | — | Запись в SQLite |
| ST-3 | API `/project`/`/project/init` | ST-1, ST-2 | Endpoints работают |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Реализовать fork — копию истории до точки + ссылку на parent. |
| **Dependencies** | T-1 |
| **DoD** | Fork работает в TUI и API. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | API `/session` с parentID + clone | T-1 | Новая сессия видна |
| ST-5 | UI fork-команда | ST-4 | Доступна как `/fork` |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Реализовать compaction (manual `/compact` + auto при threshold). |
| **Dependencies** | Provider |
| **DoD** | Сессия после compact имеет ≤ 30 % контекста, ничего не потеряно (archived). |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | `compaction.ts` через `summary.txt` prompt | — | Summary валидное |
| ST-7 | Auto-trigger логика | ST-6 | Срабатывает один раз перед overflow |
| ST-8 | UI индикатор compacting | — | Виден пользователю |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Snapshot + revert / unrevert. |
| **Dependencies** | FS |
| **DoD** | Файлы и история возвращаются к точке. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Content-addressed snapshot store | — | Дедупликация работает |
| ST-10 | API revert/unrevert | ST-9 | Файлы синхронизированы |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Реализовать `/share` и `/unshare` с sync в opncd.ai. |
| **Dependencies** | Net |
| **DoD** | URL живой, обновляется при новых сообщениях. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Share API + delta-sync | — | Sync работает |
| ST-12 | UI команды и copy-to-clipboard | ST-11 | `/share` копирует URL |

---

# Feature 6 — Permissions System

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Permissions System |
| **Description (Goal / Scope)** | Декларативная система разрешений, контролирующая, какие действия агента выполняются автоматически, какие — требуют подтверждения, какие — запрещены. Применяется на уровне пользователя (config), агента, сессии, отдельного запроса. Поддержка wildcard-паттернов (`*`, `?`), per-tool гранулярности (`bash` отдельно от `bash git *`), per-path для `edit`. Scope: `Permission.Service`, `Rule`/`Ruleset`/`Action` схемы, `evaluate.ts`, slash-config, обратная совместимость со старым `tools` boolean. |
| **Client** | Все пользователи (особенно security-сознательные); enterprise (где deny-by-default обязательны для compliance); CI/CD-сценарии. |
| **Problem** | Без permission-control любой LLM-агент может удалить файлы, запустить опасную команду, прочитать секреты. Нужна гранулярность: `git *` ок, `rm *` — нет; редактировать `docs/` ок, `package.json` — спросить. |
| **Solution** | Pattern-based ruleset где **последнее совпадающее правило выигрывает**. Pattern глобально (`*: ask`) перекрывается специфическим (`bash git *: allow`). Сохранение per-session «Always»-decisions. UI permission-prompt в TUI с понятным контекстом и опциями `Allow once / Allow always / Reject`. Audit log всех решений. |
| **Metrics** | • Среднее число permission-prompts на сессию ≤ 3 (после initial trust-build) <br>• Доля сессий без deny-инцидента ≥ 99 %<br>• Время evaluation правил ≤ 5 мс<br>• Доля пользователей с custom permission-config ≥ 25 % |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Security-сознательный разработчик |
| **User Story ID** | US-1 |
| **User Story** | As a security-сознательный разработчик, I want по дефолту запретить выполнение `rm *` и любых деструктивных bash-команд, so that исключить риск случайного удаления данных. |
| **UX / User Flow** | 1. В `~/.config/opencode/opencode.json` добавить `permission.bash`: `{ "*": "ask", "rm *": "deny", "git *": "allow" }`. 2. При попытке агента выполнить `rm node_modules` — операция блокируется с сообщением. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Конфиг с правилом `"rm *": "deny"`. |
| **When** | LLM вызывает `bash({command: "rm -rf node_modules"})`. |
| **Then** | `Permission.evaluate("bash", "rm -rf node_modules")` возвращает `deny`; tool возвращает `error` с понятным сообщением; LLM получает информативный error чтобы попробовать альтернативу. |
| **Input** | Tool call. |
| **Output** | `{status: "error", error: "Permission denied: rm * (deny rule)"}`. |
| **State** | Audit log записывает попытку. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Wildcard matcher: `*` (zero+ chars), `?` (один char), литералы. |
| **FR-2** | «Последнее совпадение выигрывает», поэтому global `"*"` должен быть в начале объекта. |
| **FR-3** | Tool возвращает структурированную ошибку, не падает. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Evaluation на 100 правил ≤ 5 мс. |
| **NFR-2** | Audit log должен включать timestamp, action, pattern matched, agent, sessionID. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | `permission.edit = { "*": "deny", "docs/**": "allow" }`. |
| **When** | Агент пытается `edit({filePath: "src/index.ts"})`. |
| **Then** | Pattern `*` matches → deny; src-файл не редактируется. |
| **Input** | Tool call с filePath. |
| **Output** | Error response. |
| **State** | Без изменений FS. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Path-pattern должен поддерживать `**` (глубокая) — но базовый wildcard как в README описано. |
| **FR-5** | Agent-level overrides поверх user-level. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Не должно лишних file-stat вызовов. |
| **NFR-5** | Логирование с уровнем DEBUG для evaluation trace. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Разработчик в TUI |
| **User Story ID** | US-2 |
| **User Story** | As a пользователь TUI, I want получать prompt при `ask`-permission с понятным предпросмотром операции, so that принимать решение быстро и осознанно. |
| **UX / User Flow** | 1. Активна сессия `plan`. 2. LLM хочет `edit` файл — открывается overlay с diff-preview, кнопками `Allow once`, `Always (this session)`, `Reject`. 3. Выбрать → tool продолжает. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Permission `ask` для `edit`. |
| **When** | Tool call. |
| **Then** | Создаётся `PermissionRequest`, в TUI рендерится prompt с input/diff/команды; пользователь выбирает; ответ возвращается через `POST /permission/:id`. |
| **Input** | Tool input + user choice. |
| **Output** | `Reply: "once" | "always" | "reject"`. |
| **State** | DB `PermissionTable` запись; session-level patch при `always`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Prompt должен показывать pattern, на который решение распространяется. |
| **FR-7** | `Esc` или закрытие overlay = `reject`. |
| **FR-8** | Не должно быть параллельных prompts: prompt-queue. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Время prompt-render ≤ 50 мс. |
| **NFR-7** | Prompt должен быть screenreader-friendly (для desktop UI). |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Сессия запущена с `--dangerously-skip-permissions`. |
| **When** | Tool call который был бы `ask`. |
| **Then** | Auto-approve без prompt; UI показывает yellow-warning indicator «dangerous mode». |
| **Input** | CLI flag. |
| **Output** | Tools выполняются автоматически. |
| **State** | `session.dangerous = true` сохраняется в metadata. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Флаг распространяется только на `ask`, не на `deny`. |
| **FR-10** | Должен быть viz-индикатор и подтверждение в стартовом сообщении. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Нельзя включить flag через config — только CLI/env. |
| **NFR-9** | Audit log должен пометить такие действия специально. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want проверить, какие правила применяются к действию через `opencode permissions`-команду, so that отлаживать конфликты правил. |
| **UX / User Flow** | 1. Запустить `opencode permissions` или slash-команду `/permissions`. 2. Вывод — таблица: action, pattern, source (default/user/agent), action. 3. Можно протестировать конкретный input: `opencode permissions test bash "rm -rf foo"`. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Конфиг сложный, есть правила и от user, и от агента. |
| **When** | Запускается `opencode permissions test edit src/index.ts`. |
| **Then** | Выводится evaluated rule + decision + reasoning trace. |
| **Input** | `permission`, `pattern_arg`. |
| **Output** | `{ matched: { pattern, action, source }, trace: [...] }`. |
| **State** | Stateless. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Команда должна показывать какой rule выиграл и почему. |
| **FR-12** | Поддержка JSON-вывода для CI. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Команда ≤ 200 мс. |
| **NFR-11** | Trace не раскрывает секретные значения env. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI permission overlay; CLI `opencode permissions` (debug); slash `/permissions reset/list/test`. |
| **User Entry Points** | Tool calls; manual debug commands. |
| **Main Screens / Commands** | Permission overlay (with diff/cmd preview, choices); status indicator (dangerous mode). |
| **Input / Output Format** | `Permission.Reply`. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Permission.Service`, `evaluate.ts`. |
| **Responsibility** | Evaluating ruleset, fielding prompts, persisting decisions. |
| **Business Logic** | Build effective ruleset (defaults < user < agent < session-overrides) → on each tool: match pattern → return action → если `ask`, await user reply via deferred event. |
| **API / Contract** | `POST /project/:projectID/session/:sessionID/permission/:permissionID` — body `{ reply: "once" \| "always" \| "reject" }`. |
| **Request Schema** | `PermissionRule { permission, pattern, action }`. |
| **Response Schema** | Updated session permission set. |
| **Error Handling** | `PermissionInvalid`, `PermissionTimeout` (если пользователь не ответил в time). |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Rule`, `Ruleset`, `PermissionRequest`, `Action`. |
| **Relationships (ER)** | Session 1—N PermissionRequest; Session 1—N session-level Rule (`always` decisions). |
| **Data Flow (DFD)** | Tool → evaluate → if ask → emit `permission.requested` → TUI renders prompt → user reply → `permission.replied` → tool resumes/aborts. |
| **Input Sources** | Defaults (`agent.ts`), user `opencode.json` `permission`, `agent` frontmatter `permission`, runtime `--dangerously-skip-permissions`, CLI `--rule`. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Никаких сверх Feature 1 (та же DB). |
| Опциональный аудит-лог в `~/.local/share/opencode/audit.log`. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Pattern matcher + evaluator | — | Тесты проходят, evaluation ≤ 5 мс | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Path-aware permission для `edit` | T-1 | Path-rules работают | ST-4, ST-5 |
| UC-2.1 | T-3 | TUI permission overlay | TUI | Overlay и replies работают | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | `--dangerously-skip-permissions` flow | T-1 | Flag работает с warning | ST-9, ST-10 |
| UC-3.1 | T-5 | Debug-команда `opencode permissions` | T-1 | Trace и test работают | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать pattern-matcher (`Wildcard`) и `evaluate.ts`. |
| **Dependencies** | — |
| **DoD** | Тесты на all/most popular patterns зелёные. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Реализовать `Wildcard.match` | — | `*`, `?`, литералы |
| ST-2 | Реализовать `evaluate(ruleset, permission, input)` | ST-1 | Last-match-wins |
| ST-3 | Юнит-тесты ≥ 90 % покрытия | ST-2 | Coverage |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Path-aware patterns для `edit`/`apply_patch`/`write`. |
| **Dependencies** | T-1 |
| **DoD** | Path-rules применяются. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Поддержка `**` в pattern | T-1 | Глубокий match |
| ST-5 | Тесты на mixed user+agent rules | ST-4 | Конфликты разрешаются |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | TUI permission overlay с очередью и preview. |
| **Dependencies** | TUI |
| **DoD** | UX user-friendly. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Подписка на `permission.requested` | — | Prompt появляется |
| ST-7 | Render preview (diff/cmd) | ST-6 | Diff syntax-highlight |
| ST-8 | Очередь нескольких prompts | ST-6 | Не теряются |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | `--dangerously-skip-permissions` flag в `opencode run` и runtime. |
| **Dependencies** | T-1 |
| **DoD** | Flag меняет evaluation, виден indicator. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Прокинуть flag через session metadata | T-1 | Не игнорируется |
| ST-10 | Visual indicator + audit | ST-9 | Виден пользователю |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Debug CLI `opencode permissions list/test`. |
| **Dependencies** | T-1 |
| **DoD** | Команды показывают полный trace. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `list` — печать effective ruleset | — | Таблица читаема |
| ST-12 | `test` — pattern simulation | T-1 | Trace + decision |

---

# Feature 7 — Plugins & Skills System

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Plugins & Skills System |
| **Description (Goal / Scope)** | Расширяемая платформа: (a) **Plugins** — TypeScript/JS-модули из npm или локально, регистрирующие новые tools, hooks (pre-tool, post-tool), commands. (b) **Skills** — markdown-файлы (`SKILL.md` с YAML-frontmatter) с reusable инструкциями, которые агент может загружать on-demand через native `skill`-tool. Поддерживаются `.opencode/skills/`, `~/.config/opencode/skills/`, а также Claude-compatible (`.claude/skills/`) и agent-compatible (`.agents/skills/`) пути. Scope: plugin loader, sandbox, hook system; Skill discovery, frontmatter validation, on-demand loading. |
| **Client** | Опытные пользователи и team-leads, желающие стандартизовать workflow; авторы opensource-плагинов (например, для специфичных линтеров, форматтеров, custom-tools); пользователи, переходящие с Claude Code (compatibility со skill-форматом). |
| **Problem** | Агент один и тот же для всех пользователей. Невозможно «один раз» научить агента tribal knowledge команды. Установка готовых tool-наборов (например, под конкретный фреймворк) требует ручной перенастройки. |
| **Solution** | Двухуровневая система: **Skills** для лёгких текстовых рецептов (markdown инструкции), агент видит metadata и загружает full-text при необходимости через `skill`-tool. **Plugins** — для full-fledged расширений: код, регистрация новых tools, перехват событий. Plugin-конфиг через `opencode.json` поле `plugin: ["./local-plugin", "@scope/pkg"]`. |
| **Metrics** | • ≥ 5 встроенных хуков для plugin'ов<br>• Skill-discovery walk до git root ≤ 50 мс<br>• ≥ 10 % проектов имеют ≥ 1 SKILL.md<br>• Plugin load fail не должен ронять opencode<br>• Hot-reload плагинов в dev mode |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Author кастомного tool'а |
| **User Story ID** | US-1 |
| **User Story** | As a автор внутреннего tool'а, I want написать opencode-plugin с новым `deploy`-tool'ом, so that команда могла дёргать deploy через AI-агент. |
| **UX / User Flow** | 1. `npm init` → импортировать `@opencode-ai/plugin`. 2. Экспортировать default плагин с `tools: [...]`. 3. В `opencode.json` указать `"plugin": ["./my-plugin"]`. 4. Перезапустить opencode — новый tool доступен агенту. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Plugin-package реализует интерфейс `Plugin.Definition` и экспортируется default. |
| **When** | Сервер бутстрапит и подтягивает плагины из `Config.plugin`. |
| **Then** | `Plugin.Service` импортирует через `import()` (ESM), валидирует, регистрирует tools/hooks/commands. |
| **Input** | Plugin module file path или npm-spec. |
| **Output** | Plugin зарегистрирован в реестре; tools видны LLM. |
| **State** | Cached в memory. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Plugin SDK должен предоставлять типизированные интерфейсы (`ToolDefinition`, `Hook`, `Command`). |
| **FR-2** | Падение одного плагина не должно ронять остальные. |
| **FR-3** | `--pure` flag должен пропускать external plugins. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Plugin load ≤ 500 мс (при cold cache npm). |
| **NFR-2** | Безопасность: plugin runs in same process — рекомендуется sandbox в будущем; сейчас trust-based. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Плагин определяет hook `onToolCall` для логирования. |
| **When** | Любой tool вызывается в сессии. |
| **Then** | Plugin hook вызывается с input/output, может модифицировать metadata, не блокирует выполнение. |
| **Input** | Tool invocation context. |
| **Output** | Logged event. |
| **State** | Без побочных эффектов на сессии (если hook не возвращает мутации). |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Hooks: `onSessionStart`, `onMessage`, `onToolCall`, `onToolResult`, `onSessionEnd`, `onConfigLoad`. |
| **FR-5** | Hooks может быть async; timeout 5 сек. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Suma overhead всех hooks на event ≤ 20 мс. |
| **NFR-5** | Errors от hooks логируются, не пропагируются. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Tech-lead команды |
| **User Story ID** | US-2 |
| **User Story** | As a тех-лид, I want определить SKILL.md «react-component-style» с командными гайдлайнами, so that агент следовал бы им при создании React-компонентов. |
| **UX / User Flow** | 1. Создать `.opencode/skills/react-component-style/SKILL.md` с frontmatter `name`, `description`. 2. Содержимое — гайдлайны (стиль, naming, patterns). 3. В разговоре агент видит список skills, и при работе над React загружает скилл через `skill({name})`. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | В проекте есть `.opencode/skills/react-component-style/SKILL.md`. |
| **When** | Сервер бутстрапит сессию в этом проекте. |
| **Then** | `Skill.Service` рекурсивно (вверх до git root) находит skill-папки, парсит frontmatter, делает доступным список skills агенту. |
| **Input** | Project root path. |
| **Output** | `Skill.Info[]` (только metadata, без full content). |
| **State** | Cached с file-watcher на изменения. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Должна валидироваться required-frontmatter (`name`, `description`). |
| **FR-7** | Одинаковые `name` из разных мест разрешаются по приоритету: project > global; opencode > claude > agents. |
| **FR-8** | Поддержка metadata field как string-to-string map. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Discovery ≤ 100 мс для проекта с 500 файлами. |
| **NFR-7** | File-watcher не должен превышать 1 % CPU. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Агент видит skill metadata. |
| **When** | LLM вызывает `skill({name: "react-component-style"})`. |
| **Then** | Tool читает full SKILL.md content и возвращает как result для использования в дальнейшем reasoning. |
| **Input** | `name`. |
| **Output** | Markdown content. |
| **State** | Stateless. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Skill-tool должен иметь permission `allow` для whitelisted skill-dirs. |
| **FR-10** | Должна быть защита от path traversal (только в skill-папках). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Ответ tool ≤ 50 мс. |
| **NFR-9** | Размер SKILL.md лимитируется 200 KB. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want просматривать список доступных skills и плагинов в TUI, so that видеть, что у меня сконфигурировано. |
| **UX / User Flow** | 1. В TUI открыть `dialog-skill` (или slash `/skills`). 2. Видеть список с источниками (project/global, .opencode/.claude/.agents). 3. Аналогично `/plugins` для плагинов и hooks. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | TUI открыт. |
| **When** | Пользователь нажимает skill-keybind или вводит `/skills`. |
| **Then** | Открывается `dialog-skill.tsx` со списком skills, источниками и позволяющим preview content. |
| **Input** | Keybind / slash. |
| **Output** | Diaolog UI. |
| **State** | Без изменений state. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Должен быть фильтр по name/description. |
| **FR-12** | Preview MD-rendered. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Открытие ≤ 100 мс. |
| **NFR-11** | Preview render для 50 KB MD ≤ 100 мс. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI dialogs (`dialog-skill.tsx`, plugin-list); CLI `opencode plug` команды. |
| **User Entry Points** | Bootstrap → load → register → доступно агенту. |
| **Main Screens / Commands** | Skill picker, Plugin status. |
| **Input / Output Format** | YAML frontmatter + MD body для skills; ESM module export для plugins. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Plugin.Service`, `Skill.Service`. |
| **Responsibility** | Discovery + load + register + lifecycle. |
| **Business Logic** | Plugin: dynamic import → validate exports → register; Skill: walk dirs → parse frontmatter → cache; merging by priority. |
| **API / Contract** | Internal interfaces; REST: `GET /skills`, `GET /plugins`. |
| **Request Schema** | — |
| **Response Schema** | `Skill.Info`, `Plugin.Info`. |
| **Error Handling** | `PluginLoadError`, `SkillInvalidFrontmatter`. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Plugin`, `Skill`, `Hook`, `ToolDefinition` (from plugin). |
| **Relationships (ER)** | Plugin 1—N Tool/Hook/Command; Skill 1—1 Frontmatter; Project 1—N Skill. |
| **Data Flow (DFD)** | FS scan (skills) / npm-import (plugins) → cache → merge into registries → consumed by Tool/Session/UI. |
| **Input Sources** | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`, `~/.config/opencode/`, `~/.claude/`, `~/.agents/`; `opencode.json` `plugin`. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Node/Bun module loader; npm cache (для `@scope/pkg`). |
| Доступ только в whitelisted skill paths для `skill`-tool. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Plugin loader + SDK types | Config | Plugin регистрирует tool | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Plugin hooks (onTool*, onSession*) | T-1 | Hooks вызываются | ST-4, ST-5 |
| UC-2.1 | T-3 | Skill discovery + frontmatter parsing | FS | Discovery работает | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Native `skill`-tool + safety | T-3, Permission | Tool читает SKILL.md | ST-9, ST-10 |
| UC-3.1 | T-5 | TUI dialog-skill + plugin-list | TUI | UI работает | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать Plugin loader: dynamic import, validation, registration. SDK package `@opencode-ai/plugin` с типами. |
| **Dependencies** | Config |
| **DoD** | Hello-world plugin регистрирует tool, виден агенту. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Опубликовать SDK с типами `ToolDefinition`, `Plugin` | — | NPM-package работает |
| ST-2 | Реализовать `Plugin.Service.load()` | ST-1 | Поддержка ESM |
| ST-3 | `--pure` flag bypass | — | OPENCODE_PURE=1 пропускает |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Внедрить hook-points в session/tool layers и вызывать plugin hooks. |
| **Dependencies** | T-1 |
| **DoD** | Все 6 hooks работают и стабильны. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Hook-bus subscribers from plugins | T-1 | Подписка работает |
| ST-5 | Timeout + error isolation | ST-4 | 5-сек timeout |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Skill discovery (project + global, opencode/claude/agents-compatible). |
| **Dependencies** | FS |
| **DoD** | Discovery находит все 6 источников. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Walk-up до git root | — | Останов в worktree |
| ST-7 | Frontmatter parser + schema | — | Required fields проверяются |
| ST-8 | Priority merging | ST-6, ST-7 | Project > global |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Native `skill`-tool с whitelisting и size cap. |
| **Dependencies** | T-3, Permission |
| **DoD** | Tool безопасно читает SKILL.md. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Implementation + zod schema | — | Tool работает |
| ST-10 | Path-traversal protection | ST-9 | Безопасно |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | UI диалог skills + plugin list. |
| **Dependencies** | TUI |
| **DoD** | Open ≤ 100 мс, preview работает. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | `dialog-skill.tsx` | — | Интуитивный UX |
| ST-12 | Plugin-list view | T-1 | Show loaded plugins |

---

# Feature 8 — GitHub Integration (Issues / PRs / Actions)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | GitHub Integration (Issues / PRs / Actions) |
| **Description (Goal / Scope)** | OpenCode умеет подключаться к GitHub-репозиторию: реагировать на упоминания `/opencode` или `/oc` в комментариях issue, PR-review, workflow_dispatch — и выполнять задачу прямо в GitHub Actions runner. Установка через `opencode github install`: ставит GitHub App, добавляет workflow yml, настраивает secrets. Дополнительно — режим `opencode pr` для локальной работы с PR (review, разбор diff). Scope: GitHub App, Octokit-обёртка, parsing webhooks, GitHub Actions integration, локальный pr-command. |
| **Client** | Open-source maintainers; команды, использующие GitHub как central hub; разработчики, желающие триажить issue / автогенерировать PR. |
| **Problem** | Чтобы агент работал на проекте, разработчик должен открыть его локально, склонировать репо, запустить opencode. Нет способа дать «робот»-помощника всему репозиторию или сообществу. Нет single-click PR generation от issue. |
| **Solution** | GitHub App + GHA workflow реагируют на mention → стартует `opencode run` в runner с переменными среды → агент анализирует issue, создаёт ветку, делает изменения, открывает PR с правильным форматом. Безопасность через GH-secrets и runner sandbox. |
| **Metrics** | • % проектов с opencode-bot ≥ 5% от общего числа активных пользователей<br>• Время от mention до first response ≤ 60 сек<br>• Доля автоматически открытых PRs, что прошли human review успешно ≥ 70 %<br>• Установка `opencode github install` ≤ 3 мин |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Open-source maintainer |
| **User Story ID** | US-1 |
| **User Story** | As a maintainer, I want упомянуть `/opencode` в комментарии к issue, so that бот посмотрел issue и создал PR с фиксом. |
| **UX / User Flow** | 1. Установить через `opencode github install`. 2. В issue с описанием бага написать «/opencode пофикси этот баг». 3. Через workflow opencode-runner стартует, анализирует код, создаёт ветку и PR с описанием. 4. Maintainer ревьюит и мерджит. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Установлен GitHub App, добавлен `.github/workflows/opencode.yml`, выставлены secrets (API key). |
| **When** | В issue появляется comment с `/opencode <prompt>`. |
| **Then** | Workflow триггерится, runner вытягивает репо, инстанцирует `opencode run --message ...`, создаёт ветку `opencode/issue-N`, коммитит изменения, открывает PR с reference на issue. |
| **Input** | Webhook event `issue_comment.created`. |
| **Output** | Created branch + PR; comment в issue с ссылкой. |
| **State** | Issue остаётся открытой; PR helm. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Workflow должен поддерживать `issue_comment`, `pull_request_review_comment`, `issues`, `workflow_dispatch`. |
| **FR-2** | `opencode github install` должен walk через installation steps (App, workflow, secrets). |
| **FR-3** | Бот должен оставлять понятные комментарии («работаю над этим…», «готово, PR #N»). |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Запуск runner ≤ 60 сек. |
| **NFR-2** | Не должно ломать workflow при отсутствии прав GH-app. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Workflow дёргается, opencode-run закончил, изменения готовы. |
| **When** | Шаг создания PR выполняется. |
| **Then** | PR создаётся через Octokit, заголовок и body заполняются на основе сессии и issue context. |
| **Input** | session результат + issue context. |
| **Output** | PR на GitHub. |
| **State** | Push коммитов в новой ветке. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Шаблон PR описания должен включать ссылку на issue, summary изменений, test-plan. |
| **FR-5** | Должна быть проверка пустого diff — скорее ничего не делать, чем создавать пустой PR. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | PR creation ≤ 10 сек. |
| **NFR-5** | Не должно быть утечки tokens в logs (mask). |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Reviewer |
| **User Story ID** | US-2 |
| **User Story** | As a reviewer, I want оставить PR-review-comment с `/opencode` на конкретной строке, so that бот точечно поправил эту проблему. |
| **UX / User Flow** | 1. На review-комментарии написать `/opencode переименуй переменную в snake_case`. 2. Workflow стартует с контекстом file/line. 3. Бот делает commit на той же ветке PR. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | PR открыт, на нём review-comment с `/opencode <инструкция>`. |
| **When** | Workflow триггерится событием `pull_request_review_comment.created`. |
| **Then** | Runner получает PR head ref, file path, line number, выполняет `opencode run` с этим контекстом и пушит обновлённый файл в PR. |
| **Input** | Webhook event с PR-context. |
| **Output** | Новый коммит в PR-branch. |
| **State** | PR-branch обновляется. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Должны передаваться path и line как контекст. |
| **FR-7** | Бот должен ответить на review-comment либо одобрением, либо follow-up. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Push в PR ≤ 30 сек после получения webhook. |
| **NFR-7** | Не должно быть конфликтов при concurrent комментах (queue). |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Review-comment автор не имеет write-access к репо. |
| **When** | Workflow триггерится. |
| **Then** | Workflow проверяет permission: если comment author не collaborator/owner, останавливается с комментом «requires write access». |
| **Input** | GitHub permission check. |
| **Output** | Отказ; comment-объяснение. |
| **State** | Без изменений. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-8** | Permission check на основе `author_association`. |
| **FR-9** | Конфигурируемый allow-list пользователей. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Permission check ≤ 1 сек. |
| **NFR-9** | Audit log всех triggered runs. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want локально просмотреть и проревьюить PR через `opencode pr`, so that получать AI-помощь без открытия web-UI. |
| **UX / User Flow** | 1. `cd <repo>` → `opencode pr review 123`. 2. opencode скачивает diff, открывает session с pre-loaded контекстом PR. 3. Можно задать вопросы, попросить fix-suggestions. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Локальная клонированная репа, опц. `gh auth login` уже сделан. |
| **When** | Запускается `opencode pr review <number>`. |
| **Then** | Через `Octokit` подгружается diff и обсуждение, добавляется как контекст в новую сессию, открывается TUI. |
| **Input** | PR number. |
| **Output** | Сессия с контекстом PR. |
| **State** | Persisted session. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-10** | Поддержка `--repo owner/name` если не текущая. |
| **FR-11** | Должен использовать gh-cli или GitHub token из env. |
| **FR-12** | Diff > 1 MB должен предупредить и предложить выборку файлов. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Подгрузка PR ≤ 5 сек. |
| **NFR-11** | Кэшируется на 5 мин для повторного открытия. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | GitHub App (на github.com/apps/opencode-agent), GHA workflow yml, локальный CLI `opencode github`/`opencode pr`. |
| **User Entry Points** | `/opencode` mention в comment; `opencode github install`; `opencode pr review/comment/list`. |
| **Main Screens / Commands** | Install wizard, PR review TUI с pre-loaded контекстом. |
| **Input / Output Format** | GitHub webhook payloads (Octokit types), GraphQL queries, REST. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | GitHub-runner (внутри GHA), `cli/cmd/github.ts`, `cli/cmd/pr.ts`. |
| **Responsibility** | Парсинг webhooks; проверка permissions; запуск `opencode run`; PR/branch creation; локальные операции на PR. |
| **Business Logic** | Webhook → router → permission gate → context build → opencode run → push branch → open PR / comment. |
| **API / Contract** | GitHub Webhooks; Octokit REST/GraphQL. |
| **Request Schema** | Webhook payloads (typed `@octokit/webhooks-types`). |
| **Response Schema** | PR/comment objects (Octokit). |
| **Error Handling** | Permission denied, rate-limit, app-not-installed, network fail. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | `Issue`, `PR`, `Comment`, `ReviewComment`, `Branch`, `Commit`, `Workflow`. |
| **Relationships (ER)** | Repo 1—N Issue/PR; PR 1—N ReviewComment; PR 1—1 Branch. |
| **Data Flow (DFD)** | GitHub webhook → opencode-app workflow → runner → opencode-cli → git push → GitHub API. |
| **Input Sources** | Webhook events; repo state; secrets (API keys); user comment text. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| GitHub Actions runner (стандартный ubuntu-latest достаточен). |
| Outbound HTTPS до Anthropic/OpenAI и github.com. |
| GitHub-secrets для API keys. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | GitHub App + workflow template + install command | Octokit | App работает, workflow в репо | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Auto-PR generation после run | T-1 | PR с правильным шаблоном | ST-4, ST-5 |
| UC-2.1 | T-3 | Поддержка PR-review-comment событий | T-1 | Точечный фикс работает | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Permission check author_association | T-1 | Не-collaborator получает отказ | ST-9, ST-10 |
| UC-3.1 | T-5 | `opencode pr review` локальная команда | Auth | TUI с PR-контекстом | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Поднять GitHub App и реализовать `opencode github install` wizard, включая создание workflow.yml и установку secrets. |
| **Dependencies** | Octokit |
| **DoD** | Чистый репо за < 3 мин получает работающий бот. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Создать GitHub App + manifest | — | App установлена |
| ST-2 | Шаблон `.github/workflows/opencode.yml` | — | Корректный YAML |
| ST-3 | CLI wizard через `@clack/prompts` | — | UX без ошибок |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | После завершения `opencode run` собрать diff, создать ветку, открыть PR с шаблоном. |
| **Dependencies** | T-1 |
| **DoD** | PR корректно создаётся, шаблон описания заполнен. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Branch + commit + push | — | Не падает на пустом diff |
| ST-5 | PR-create через Octokit | ST-4 | PR-link комментится в issue |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Поддержка `pull_request_review_comment` с file/line context. |
| **Dependencies** | T-1 |
| **DoD** | Точечные фиксы работают. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Парсинг review payload | — | path/line корректны |
| ST-7 | Передача в `opencode run` как контекст | ST-6 | Файл правится точно |
| ST-8 | Push commit в PR-branch | ST-7 | Без force-push |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Permission check на основе `author_association`. |
| **Dependencies** | T-1 |
| **DoD** | Не-collaborator получает понятный отказ. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Чтение `author_association` из payload | — | Корректно |
| ST-10 | Allow-list config в workflow | ST-9 | Команда может расширить |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Локальный `opencode pr review <num>` — открывает TUI с PR-context. |
| **Dependencies** | Auth |
| **DoD** | Работает offline-friendly (cache). |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Octokit fetch + cache | — | Кэш TTL 5 мин |
| ST-12 | Inject PR-context как первый message | ST-11 | TUI стартует с контекстом |

---

# Feature 9 — IDE Integrations (VS Code / Zed)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | IDE Integrations (VS Code & Zed) |
| **Description (Goal / Scope)** | Расширения для VS Code (`sdks/vscode`) и Zed (`packages/extensions/zed`), позволяющие открывать opencode прямо из IDE: запустить новый chat в integrated-терминале, прикрепить контекст из активного файла/выделения, открыть session-list. Также — **ACP (Agent Communication Protocol)** через `opencode acp` — стандарт интеграции с любым ACP-совместимым IDE/клиентом (например, Zed Assistant). Поддержка LSP-bridge между opencode и IDE. Scope: VS Code extension manifest, Zed-extension config, ACP server, LSP-passthrough. |
| **Client** | VS Code-пользователи (подавляющее большинство dev-сообщества); Zed-юзеры (растущая аудитория, terminal-savvy); пользователи других ACP-совместимых клиентов. |
| **Problem** | TUI отлично, но многие разработчики живут в IDE — нужен «быстрый доступ» к opencode без выхода из редактора. Дополнительно — глубокая интеграция (передача выделения, открытых файлов, diagnostics) даёт лучший UX. |
| **Solution** | Native расширения IDE, запускающие opencode в integrated-терминале или через ACP. Команды-шорткаты (`Cmd+Shift+P` → `opencode: New Session` и т. д.). Передача контекста: путь активного файла, выделение, открытые файлы — как attachments. ACP — стандартизированный protocol для IDE-агентов. |
| **Metrics** | • VS Code marketplace install count ≥ 5k за 6 мес<br>• Среднее время от install до first-use ≤ 2 мин<br>• Частота использования IDE-extension vs CLI ≥ 30 % среди IDE-пользователей<br>• Crash-rate extension < 0.5 % сессий |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | VS Code пользователь |
| **User Story ID** | US-1 |
| **User Story** | As a VS Code пользователь, I want нажать `Cmd+Shift+P` → `opencode: Open` и сразу попасть в чат-сессию для текущего workspace, so that не открывать отдельный терминал. |
| **UX / User Flow** | 1. Установить «opencode» extension из marketplace. 2. Открыть VS Code в проекте. 3. `Cmd+Shift+P` → `opencode: Open`. 4. В integrated-terminal стартует TUI; статус-бар IDE показывает «opencode running». |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Установлен extension и `opencode` бинарник доступен в PATH. |
| **When** | Команда `opencode: Open` запускается. |
| **Then** | Extension создаёт новую terminal-instance в VS Code, выполняет `opencode --dir <workspace>`, фокусирует терминал. |
| **Input** | Командное действие. |
| **Output** | Открытый terminal с TUI. |
| **State** | Terminal сохранён под id, можно closeUntil. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Если `opencode` не найден в PATH — диалог с предложением установить. |
| **FR-2** | Если уже есть открытый opencode terminal — фокус на него (не дублировать). |
| **FR-3** | Передавать workspace folder как `--dir`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Запуск ≤ 2 сек. |
| **NFR-2** | Extension не должен подъедать > 50 MB RAM. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | В редакторе открыт файл `src/app.ts`, выделена строка 42. |
| **When** | Right-click → `opencode: Ask about selection`. |
| **Then** | Extension отправляет в TUI новое сообщение с включённым контекстом: file path + selection text + line range. |
| **Input** | Active editor + selection. |
| **Output** | Pre-filled message; TUI focused. |
| **State** | Сессия использует выделение как attachment-part. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Selection / file должны передаваться как attachments через `--file` и контекст-сообщение. |
| **FR-5** | Должны быть quick-actions: «Explain», «Fix», «Refactor», «Test». |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Action отрабатывает ≤ 1 сек. |
| **NFR-5** | Поддержка multi-cursor selections. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Zed-пользователь |
| **User Story ID** | US-2 |
| **User Story** | As a Zed-пользователь, I want использовать opencode как ACP-агент в Zed Assistant, so that чатиться через native Zed-UI. |
| **UX / User Flow** | 1. В Zed-конфиге добавить opencode как ACP-провайдера. 2. Открыть Zed Assistant pane. 3. Чат идёт через Zed UI; backend — opencode. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Установлен `opencode` бинарник, в Zed-config настроен ACP-провайдер. |
| **When** | Zed Assistant создаёт новую сессию. |
| **Then** | Zed запускает `opencode acp` (stdio JSON-RPC), opencode принимает команды/messages по ACP-spec, отвечает streamed messages. |
| **Input** | ACP messages (JSON-RPC over stdio). |
| **Output** | Streaming responses в Zed Assistant pane. |
| **State** | Сессия живёт в opencode-process; Zed UI отображает её. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | `opencode acp` должен полностью поддерживать ACP-spec (initialize, message/send, message/stream, tool/call, etc.). |
| **FR-7** | Tool calls должны рендериться корректно в Zed UI (через ACP `tool` events). |
| **FR-8** | Permission-prompts должны работать через ACP `permission/request`. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Latency overhead ACP ≤ 5 % vs нативный TUI. |
| **NFR-7** | Crash recovery: если opencode упал, Zed получает graceful close. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | ACP-сессия активна. |
| **When** | Пользователь закрывает Zed pane. |
| **Then** | ACP-process получает `terminate`, корректно завершает, persist'ит сессию. |
| **Input** | Close-event. |
| **Output** | Saved session, exit 0. |
| **State** | Доступно для resume через `opencode run --continue`. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | Должно сохраняться без потерь при graceful shutdown. |
| **FR-10** | Resume через CLI или через ACP `session/resume` event. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Shutdown ≤ 2 сек. |
| **NFR-9** | SQLite WAL flush гарантирован. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a разработчик, I want IDE-extension показывал статус и количество активных opencode-сессий, so that знать, что что-то работает в фоне. |
| **UX / User Flow** | 1. После запуска opencode-сессии — в IDE status-bar появляется индикатор «opencode: 1 active». 2. Click → опции `Focus / New / List sessions / Stop`. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Extension установлен и какая-то сессия активна. |
| **When** | IDE рендерит status-bar. |
| **Then** | Extension polling-ит локальный сервер (`/session list`) и обновляет индикатор. |
| **Input** | Periodic poll. |
| **Output** | Status-bar item с count. |
| **State** | Отслеживается active session-count. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Polling interval — 5 сек, останавливается при отсутствии серверов. |
| **FR-12** | Click открывает QuickPick с опциями. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Polling overhead ≤ 0.1 % CPU. |
| **NFR-11** | При network-error indicator переключается в greyed mode. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | VS Code extension (TypeScript, vscode API) `sdks/vscode`; Zed extension (Rust + JSON config) `packages/extensions/zed`. |
| **User Entry Points** | Command palette, keyboard shortcuts, right-click menu, status-bar, Zed Assistant pane. |
| **Main Screens / Commands** | `opencode: Open`, `opencode: Ask about selection`, `opencode: New session`, `opencode: List sessions`, `opencode: Stop`. |
| **Input / Output Format** | VS Code commands → spawned terminal или ACP-запуск; Zed → stdio JSON-RPC ACP. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `cli/cmd/acp.ts` (ACP server entrypoint), `Server` (HTTP), используется extension'ом. |
| **Responsibility** | ACP — обёртка вокруг session/message API в JSON-RPC формате; HTTP — для VS Code extension. |
| **Business Logic** | `opencode acp` стартует ACP-process на stdio; маппит ACP-events на внутренние server-events. |
| **API / Contract** | ACP-spec (open spec); HTTP API (см. Feature 10). |
| **Request Schema** | ACP messages: `initialize`, `session/new`, `message/send`, `message/stream`, `tool/call`, `permission/request`. |
| **Response Schema** | ACP responses + streaming events. |
| **Error Handling** | JSON-RPC error codes; structured errors. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | Те же, что в Feature 5 (`Session`/`Message`/`Part`); добавляется `ACPClient`. |
| **Relationships (ER)** | ACP client 1—1 opencode-session. |
| **Data Flow (DFD)** | IDE event → extension → spawn `opencode acp` или HTTP-call → opencode-server → SQLite/Provider → response → IDE-UI. |
| **Input Sources** | IDE events (selection, file, command); workspace path. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Установлен `opencode` бинарник; IDE (VS Code 1.85+ или Zed). |
| Достаточно RAM для extension (~50 MB) + opencode-process. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | VS Code extension + `opencode: Open` | VS Code API | Команда работает в marketplace-build | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Selection-aware quick actions | T-1 | Quick actions работают | ST-4, ST-5 |
| UC-2.1 | T-3 | ACP server `opencode acp` | Server | ACP проходит spec-tests | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Graceful shutdown через ACP | T-3 | Resume работает | ST-9, ST-10 |
| UC-3.1 | T-5 | Status-bar indicator + QuickPick | T-1 | Indicator стабилен | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Скелет VS Code extension с командой `opencode: Open`, packaging, marketplace publish. |
| **Dependencies** | VS Code API |
| **DoD** | Extension в marketplace, команда работает в Stable VS Code. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | `package.json` + `extension.ts` skeleton | — | Activates корректно |
| ST-2 | Spawn terminal с opencode | ST-1 | Терминал открывается |
| ST-3 | Marketplace-publish workflow | — | CI publishes extension |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Quick actions для selection: Explain/Fix/Refactor/Test. |
| **Dependencies** | T-1 |
| **DoD** | Все 4 действия дают релевантный prompt. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Меню right-click + command-палитра | T-1 | Действия видны |
| ST-5 | Передача selection как контекст в prompt | ST-4 | Prompt содержит код |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Реализовать `opencode acp` — ACP-spec совместимый server. |
| **Dependencies** | Server |
| **DoD** | Проходит ACP test-suite, работает с Zed. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | JSON-RPC over stdio framing | — | Корректные msgs |
| ST-7 | Mapping internal → ACP events | ST-6 | Streaming работает |
| ST-8 | Permission-bridging | ST-7 | Prompts корректны |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Graceful shutdown ACP-process с persistence. |
| **Dependencies** | T-3 |
| **DoD** | Resume сессии работает после restart. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | Signal handlers + flush | — | WAL flushes |
| ST-10 | Resume API через `session/resume` | T-3 | UI восстанавливается |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Status-bar indicator + QuickPick меню. |
| **Dependencies** | T-1 |
| **DoD** | Indicator стабильно показывает количество. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Polling 5 сек + greyed-mode | T-1 | Не нагружает CPU |
| ST-12 | QuickPick options | ST-11 | Все 4 действия работают |

---

# Feature 10 — Headless Server & Client/Server Architecture

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Headless Server & Client/Server Architecture |
| **Description (Goal / Scope)** | OpenCode реализован как клиент-серверное приложение: TUI и IDE-extensions — это клиенты к локальному (или удалённому) серверу. Сервер запускается командой `opencode serve` без UI и предоставляет HTTP REST + SSE/WebSocket API, описанный OpenAPI 3.1 спецификацией. Это позволяет: (a) запускать opencode на удалённой машине и управлять через мобильный/web client, (b) использовать SDK на разных языках, (c) интегрировать в любую существующую систему. Особенности: `--port`, `--hostname`, `--cors`, `--mdns` (auto-discovery в LAN), HTTP basic auth через `OPENCODE_SERVER_PASSWORD`. Scope: HTTP server (Bun-based), OpenAPI generation, SDK auto-generation (`packages/sdk`), `opencode web` (web UI client). |
| **Client** | Power-users, желающие запускать opencode на VPS / homelab; авторы клиентов и интеграций (mobile apps, web dashboards, CI integrations); enterprise со специфичными требованиями. |
| **Problem** | Без отделения от UI невозможно: использовать opencode на удалённой машине, иметь несколько одновременных клиентов, программно автоматизировать работу. |
| **Solution** | HTTP-server на стандартном протоколе (REST + SSE) + auto-generated SDK + OpenAPI spec → любой язык может говорить с opencode. mDNS — discovery в локальной сети. Basic auth + CORS — простая безопасность. |
| **Metrics** | • Uptime сервера ≥ 99 % за сутки uninterrupted use<br>• REST P95 latency на основных endpoint'ах ≤ 100 мс<br>• SSE-stream latency для нового token ≤ 80 мс<br>• Поддержка ≥ 100 одновременных клиентов на одном сервере<br>• Auto-generated SDK ≤ 5 % разница vs ручной TS-API |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | Power user / homelab |
| **User Story ID** | US-1 |
| **User Story** | As a power-user, I want запустить `opencode serve` на homelab-сервере и подключаться к нему с ноутбука/мобильного, so that не тратить локальные ресурсы и иметь доступ из любой точки сети. |
| **UX / User Flow** | 1. На VPS запустить `OPENCODE_SERVER_PASSWORD=secret opencode serve --port 4096 --hostname 0.0.0.0`. 2. На ноуте: `opencode --attach http://server:4096 -p secret`. 3. TUI работает с remote backend. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | Сервер запущен с password, доступен по сети. |
| **When** | Клиент `opencode --attach <url>` инициализирует. |
| **Then** | Происходит handshake: GET `/config`, basic auth check, открывается SSE-подписка на bus events. |
| **Input** | URL + credentials. |
| **Output** | Активная session-list, готов к message. |
| **State** | Connection отслеживается, при разрыве — auto-reconnect с backoff. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | Должна быть HTTP basic auth с `OPENCODE_SERVER_PASSWORD`. |
| **FR-2** | CORS-список origins должен поддерживаться через `--cors`. |
| **FR-3** | Endpoint без `OPENCODE_SERVER_PASSWORD` должен warning'ом сообщать о небезопасности. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Сервер должен принимать ≥ 100 параллельных подключений на стандартном hardware. |
| **NFR-2** | TLS должен быть возможен через reverse proxy (документируется). |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Сервер запущен с `--mdns`, в той же сети — клиент. |
| **When** | Клиент сканит сеть (TUI или extension). |
| **Then** | Опубликованный mDNS service `opencode.local` обнаруживается, клиент предлагает подключиться. |
| **Input** | `--mdns` на сервере. |
| **Output** | Discoverable service `_opencode._tcp.local`. |
| **State** | mDNS-broadcast регулярно. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | mDNS-domain должен быть конфигурируем (`--mdns-domain`). |
| **FR-5** | Должен корректно работать в Linux/macOS/Windows. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | mDNS-broadcast не должен превышать 100 байт/мин. |
| **NFR-5** | Service ttl 30 сек. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Автор клиента/интеграции |
| **User Story ID** | US-2 |
| **User Story** | As a автор интеграции, I want использовать typed SDK (TS) для общения с opencode-сервером, so that не писать REST вручную. |
| **UX / User Flow** | 1. `npm install @opencode-ai/sdk`. 2. `import { createOpencodeClient } from "@opencode-ai/sdk/v2"`. 3. `const sdk = createOpencodeClient({ baseURL, auth })` → `sdk.session.list()`, `sdk.session.create({ ... })`, etc. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Сервер выдаёт OpenAPI 3.1 spec на `/openapi.json`. |
| **When** | Запускается `./packages/sdk/js/script/build.ts`. |
| **Then** | OpenAPI spec парсится, генерируются TypeScript types и client-functions, packed в npm-package. |
| **Input** | OpenAPI spec. |
| **Output** | `@opencode-ai/sdk` npm package. |
| **State** | SDK версия = opencode версии. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | SDK поддерживает все session/message/share/permission endpoints. |
| **FR-7** | SDK типизирован для tool-results через discriminated unions. |
| **FR-8** | Должен быть отдельный modular import для streaming events. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | SDK overhead ≤ 5 % vs raw fetch. |
| **NFR-7** | Размер bundle ≤ 50 KB minified. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | Web UI client `opencode web` запущен, подключён к серверу. |
| **When** | Пользователь работает в web-interface. |
| **Then** | UI делает все операции через тот же HTTP API + SSE; никакой write-down логики на frontend. |
| **Input** | Browser pages/actions. |
| **Output** | UI обновляется по events. |
| **State** | Server остаётся source-of-truth. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | `opencode web` должен поддерживать sub-routing (multiple sessions через URL). |
| **FR-10** | Должен использоваться ETag/cache-control для статики. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | Initial page load ≤ 2 сек на 4G. |
| **NFR-9** | Web UI должен работать в Safari/Chrome/Firefox последних 2 версий. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a DevOps, I want получать observability события сервера (logs, metrics) через standard endpoint, so that мониторить здоровье и расходы. |
| **UX / User Flow** | 1. `GET /log` для получения логов в JSON-stream. 2. (planned) `GET /metrics` для prometheus-like экспорта. 3. Конфиг через `OPENCODE_LOG_LEVEL`. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | Сервер активен. |
| **When** | DevOps делает `curl <url>/log` или подписывается на `/events`. |
| **Then** | Возвращается structured log stream с уровнем согласно `OPENCODE_LOG_LEVEL`. |
| **Input** | HTTP request с auth. |
| **Output** | Newline-delimited JSON logs. |
| **State** | Buffered queue, не теряем events. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Logs должны редактировать sensitive fields (API keys, tokens). |
| **FR-12** | Log level должен быть конфигурируемый runtime через CLI flag. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Запрос на `/log` не должен влиять на latency других endpoints. |
| **NFR-11** | Поддержка `Accept: application/x-ndjson` и `text/event-stream`. |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | TUI (Feature 1), VS Code (Feature 9), Zed (Feature 9), Web UI (`opencode web`), Desktop (Feature 11), любой 3rd-party SDK-client. |
| **User Entry Points** | `opencode serve`, `opencode web`, `opencode --attach <url>`. |
| **Main Screens / Commands** | Web UI с тем же layout что TUI (планируется); CLI-management. |
| **Input / Output Format** | HTTP REST JSON, SSE event-stream, OpenAPI spec. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | `Server` (`packages/opencode/src/server/`), `cli/cmd/serve.ts`. |
| **Responsibility** | Listen HTTP, route requests, broker events, generate OpenAPI, serve static (web). |
| **Business Logic** | Bootstrap → Layer composition (Effect) → Bun adapter → routes → middleware (cors/auth) → invoke services. |
| **API / Contract** | Полный OpenAPI 3.1 spec; выгрузка через `/openapi.json`; SSE endpoints для streams; stable v2 namespace. |
| **Request Schema** | Per-route Zod schemas. |
| **Response Schema** | Per-route Zod schemas. |
| **Error Handling** | Structured `{ name, message, data }` body, корректные HTTP-коды (4xx user, 5xx internal). |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | Все из Feature 5 + `Connection`, `Subscription`. |
| **Relationships (ER)** | Server 1—N Connection; Connection 1—N Subscription. |
| **Data Flow (DFD)** | Client (TUI/SDK) → HTTP/SSE → Bun-adapter → routes → Layer services → DB → events → bus → SSE → all subscribed clients. |
| **Input Sources** | Client requests; bus internal events. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Server: ≥ 1 vCPU, ≥ 1 GB RAM (без активных моделей). |
| Outbound HTTPS до провайдеров. |
| Опционально TLS termination через reverse proxy (nginx/caddy). |
| For mDNS — local network broadcast permission. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | HTTP server + basic auth + CORS | Bun adapter | `serve` принимает запросы | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | mDNS discovery service | T-1 | Discoverable | ST-4, ST-5 |
| UC-2.1 | T-3 | OpenAPI generation + SDK build | T-1 | SDK генерируется CI | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | `opencode web` static client | T-1 | Web UI работает | ST-9, ST-10 |
| UC-3.1 | T-5 | `/log` endpoint + редакция | T-1 | Logs стримятся | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Реализовать `Server.listen` с adapter Bun/Node, middleware cors/auth, реестр routes. |
| **Dependencies** | Bun adapter |
| **DoD** | Все API endpoints отвечают, auth работает. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Bun-adapter с listen | — | Сервер стартует |
| ST-2 | Middleware CORS + basic auth | — | Auth требует password |
| ST-3 | Маршрутизация всех endpoint'ов | ST-1 | Все routes работают |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | mDNS service-publish для local discovery. |
| **Dependencies** | T-1 |
| **DoD** | Service виден в `dns-sd -B _opencode._tcp`. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | mdns publishing | — | Visible in browser |
| ST-5 | UI auto-discover в TUI | ST-4 | Список серверов в TUI |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | OpenAPI 3.1 spec generation + auto-build SDK для TS/JS. |
| **Dependencies** | T-1 |
| **DoD** | SDK published на npm на каждом релизе. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Spec generator на основе Zod schemas | T-1 | Корректный JSON |
| ST-7 | SDK build script | ST-6 | Generated SDK работает |
| ST-8 | CI publish on tag | — | Tag → npm |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | `opencode web` — server static + browser SPA. |
| **Dependencies** | T-1 |
| **DoD** | Web UI открывается на `/`. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | SPA build pipeline | — | Bundle ≤ 1 MB gz |
| ST-10 | Static-serve route + cache headers | T-1 | Корректные ETag |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | `/log` endpoint с уровнями + redaction. |
| **Dependencies** | T-1 |
| **DoD** | Logs стримятся, секреты редактируются. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Streaming endpoint NDJSON/SSE | — | Subscribers получают |
| ST-12 | Redaction для known sensitive fields | — | Tokens замазаны |

---

# Feature 11 — Desktop App (macOS / Windows / Linux)

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Desktop App (BETA) |
| **Description (Goal / Scope)** | Native desktop-приложение для macOS (Apple Silicon + Intel), Windows и Linux (.deb / .rpm / AppImage). Реализовано на Tauri (Rust) — `packages/desktop` + `src-tauri`. Под капотом — тот же opencode-server (`opencode serve`), а UI — нативное веб-приложение, показывающее тот же интерфейс что web-client, но с native-фичами: системный tray, autostart, нативные notifications, deep-linking, file-association. Установка через `.dmg`/`.exe`/`.deb`, через brew-cask `opencode-desktop` или scoop `extras/opencode-desktop`. Scope: Tauri-bundle, native menu, autoupdater, deep-link handler. |
| **Client** | Пользователи, не любящие терминал; designer-разработчики; команды, нуждающиеся в стандартизованном UI без зависимостей от терминала; беты-tester'ы. |
| **Problem** | TUI требует современного терминала и привычки к терминальным интерфейсам. Часть пользователей предпочитают native window с системным интегрированием — tray, notifications, alt-tab. Также — установка для не-developers сложна. |
| **Solution** | Tauri-приложение: компактный native-shell (Rust + WebView), WebView рендерит UI, под капотом — embedded или external opencode-server. Easy install через стандартные форматы (.dmg/.exe/.deb). Автообновление через signed releases. |
| **Metrics** | • Размер бандла ≤ 30 MB на платформу<br>• Cold start ≤ 3 сек<br>• Memory footprint в idle ≤ 200 MB<br>• Beta-rating ≥ 4 / 5<br>• % beta-пользователей, не вернувшихся к TUI ≥ 20 % |

## 2. User Stories and Use Cases

### User Story 1

| Field | Fill In |
|---|---|
| **Role** | macOS пользователь без терминала |
| **User Story ID** | US-1 |
| **User Story** | As a macOS пользователь, I want скачать `.dmg`, установить и сразу пользоваться opencode без открытия терминала, so that начать работу за 1 минуту. |
| **UX / User Flow** | 1. Скачать `opencode-desktop-darwin-aarch64.dmg` с релизов или `brew install --cask opencode-desktop`. 2. Перетащить в Applications, открыть. 3. Welcome-onboarding: выбрать провайдера → авторизация → первая сессия. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.1 |
| **Given** | На системе нет opencode CLI, скачан `.dmg`. |
| **When** | Пользователь устанавливает и открывает приложение. |
| **Then** | Tauri-shell стартует, embedded opencode-server поднимается на random localhost-port, UI открывает welcome-screen. |
| **Input** | Click on app. |
| **Output** | Открытое окно с UI. |
| **State** | Server-process под управлением Tauri-process. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-1** | `.dmg` должен включать notarized binary с code-signing. |
| **FR-2** | Embedded server лежит в bundle resources и запускается одновременно с UI. |
| **FR-3** | Welcome-onboarding должен охватывать auth и выбор agents. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-1** | Cold start ≤ 3 сек на Apple Silicon. |
| **NFR-2** | Размер `.dmg` ≤ 30 MB. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-1.2 |
| **Given** | Приложение запущено, пользователь свернул главное окно. |
| **When** | Active session получает завершение задачи. |
| **Then** | Native notification сообщает «Task completed: 3 files modified», dock-icon показывает badge. |
| **Input** | Bus event `session.completed`. |
| **Output** | Native notification. |
| **State** | Без изменения сессии. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-4** | Должен быть toggle нотификаций в settings. |
| **FR-5** | Click on notification — open main window и фокус на сессию. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-4** | Notification API native, без Electron-overhead. |
| **NFR-5** | Не должно превышать OS-rate limit. |

### User Story 2

| Field | Fill In |
|---|---|
| **Role** | Windows-пользователь |
| **User Story ID** | US-2 |
| **User Story** | As a Windows-пользователь, I want установить через scoop и иметь tray-icon с быстрыми действиями, so that управлять opencode без открытия главного окна. |
| **UX / User Flow** | 1. `scoop bucket add extras; scoop install extras/opencode-desktop`. 2. Запустить — в tray появляется icon. 3. Right-click → New Session / Recent Sessions / Settings / Quit. |

#### Use Case BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.1 |
| **Given** | Tauri tray-плагин активен. |
| **When** | Пользователь right-click на tray icon. |
| **Then** | Открывается меню `New session`, `Recent sessions`, `Settings`, `Quit`. Click — выполняет действие через Tauri command. |
| **Input** | Tray menu interaction. |
| **Output** | Соответствующее действие. |
| **State** | Главное окно может быть закрыто. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-6** | Tray-icon работает в Windows / Linux KDE/GNOME / macOS. |
| **FR-7** | Closing main window → app продолжает работать в tray (configurable). |
| **FR-8** | Quit полностью завершает server. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-6** | Tray-update latency ≤ 200 мс. |
| **NFR-7** | Не должно занимать > 1 % CPU когда window closed. |

#### Use Case (+ Edges) BDD 2

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-2.2 |
| **Given** | На Linux установлен AppImage. |
| **When** | Пользователь запускает AppImage. |
| **Then** | Приложение работает self-contained без установки системных зависимостей; deep-link `opencode://session/<id>` обрабатывается. |
| **Input** | AppImage execution. |
| **Output** | UI работает. |
| **State** | Standalone process. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-9** | AppImage должен включать все Tauri-зависимости. |
| **FR-10** | Deep-link scheme `opencode://` зарегистрирован при первом запуске. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-8** | AppImage запускается на Ubuntu 20.04+ без модификаций. |
| **NFR-9** | Размер AppImage ≤ 50 MB. |

### User Story 3

| Field | Fill In |
|---|---|
| **User Story ID** | US-3 |
| **User Story** | As a desktop-пользователь, I want получать автоматические обновления при выходе нового релиза, so that не следить за версиями вручную. |
| **UX / User Flow** | 1. При запуске приложение проверяет latest release. 2. Если новый — non-blocking notification «Update available: v0.5.1, click to install». 3. Click → download + apply при следующем restart. |

#### Use Case (+ Edges) BDD 1

| Field | Fill In |
|---|---|
| **Use Case ID** | UC-3.1 |
| **Given** | App-version меньше latest GitHub release. |
| **When** | App стартует и делает фоновый check. |
| **Then** | Tauri-updater находит новую версию, проверяет signature, предлагает download. |
| **Input** | GitHub releases API. |
| **Output** | Notification + UI badge. |
| **State** | Downloaded update в pending state до restart. |

##### Functional Requirements

| Req ID | Requirement |
|---|---|
| **FR-11** | Updater должен проверять Ed25519-signature releases. |
| **FR-12** | Не должно быть auto-restart без подтверждения пользователя. |

##### Non-Functional Requirements

| Req ID | Requirement |
|---|---|
| **NFR-10** | Background check не должен задерживать start ≥ 100 мс. |
| **NFR-11** | Должен корректно работать за корпоративным proxy (HTTP_PROXY). |

## 3. Architecture / Solution

### 3.1 Client Side

| Area | Fill In |
|---|---|
| **Client Type** | Tauri 2.x desktop app (`packages/desktop` + `src-tauri`); web-tech UI (тот же что Web), Rust shell. |
| **User Entry Points** | Application icon, tray, deep-link `opencode://`, file-associations. |
| **Main Screens / Commands** | Welcome-onboarding, main chat-window, settings (providers, agents, themes), session-list. |
| **Input / Output Format** | UI events ↔ Tauri commands ↔ embedded HTTP server. |

### 3.2 Backend Services

| Area | Fill In |
|---|---|
| **Service Name** | Embedded opencode-server (см. Feature 10), Tauri-плагины (window/tray/updater/notification). |
| **Responsibility** | Window management, lifecycle (start/stop server), bundling, OS-integrations. |
| **Business Logic** | На старте — spawn server child-process с локальным random port + auth-secret; UI получает endpoint через injected env var. |
| **API / Contract** | Tauri commands (Rust → JS) + HTTP/SSE к серверу. |
| **Request Schema** | Tauri commands typed (через `serde`). |
| **Response Schema** | Same. |
| **Error Handling** | Server crash → restart with backoff; UI получает error-state. |

### 3.3 Data Architecture and Flows

| Area | Fill In |
|---|---|
| **Main Entities (ER)** | Те же что в Feature 5/10 + `WindowState`, `TrayState`, `Notification`. |
| **Relationships (ER)** | Desktop process 1—1 server-process; 1—N windows. |
| **Data Flow (DFD)** | Tauri-shell (Rust) ↔ WebView (UI) ↔ HTTP/SSE (server-process) ↔ DB. |
| **Input Sources** | OS events; user actions; deep-links; updater. |

### 3.4 Infrastructure

| Required Hardware / Resources |
|---|
| Desktop с macOS 11+, Windows 10+, или Linux glibc 2.31+. |
| ≥ 4 GB RAM (рекомендуется 8 GB). |
| Notarization сертификаты для macOS, Windows code-signing cert. |
| GitHub Releases как source для updates. |

## 4. Work Plan

### Mapping: Use Case → Tasks

| Use Case | Task ID | Task | Dependencies | DoD | Subtasks |
|---|---|---|---|---|---|
| UC-1.1 | T-1 | Tauri-shell + embedded server bundling | Server | Релиз `.dmg`/`.exe`/`.deb` работает | ST-1, ST-2, ST-3 |
| UC-1.2 | T-2 | Native notifications | T-1 | Notifications уведомляют | ST-4, ST-5 |
| UC-2.1 | T-3 | Tray icon + menu | T-1 | Меню работает на 3 OS | ST-6, ST-7, ST-8 |
| UC-2.2 | T-4 | Deep-link scheme `opencode://` | T-1 | Open links работают | ST-9, ST-10 |
| UC-3.1 | T-5 | Tauri-updater + signing | T-1 | Updates подтянуть и применить | ST-11, ST-12 |

## 5. Detailed Task Breakdown

### Task 1

| Field | Fill In |
|---|---|
| **Task ID** | T-1 |
| **Related Use Case** | UC-1.1 |
| **Task Description** | Скелет Tauri-приложения с встроенным server-bin и UI; CI builds для 3 платформ. |
| **Dependencies** | Server |
| **DoD** | Release artefacts: `.dmg` (notarized), `.exe`, `.deb`, `.rpm`, AppImage. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-1 | Tauri config + bundle server | — | Server стартует от Tauri |
| ST-2 | UI initial wiring (existing web SPA) | ST-1 | UI рендерится |
| ST-3 | CI matrix builds + signing | — | Все 3 платформы |

### Task 2

| Field | Fill In |
|---|---|
| **Task ID** | T-2 |
| **Related Use Case** | UC-1.2 |
| **Task Description** | Native-notifications через Tauri plugin. |
| **Dependencies** | T-1 |
| **DoD** | Notifications срабатывают на нужные events. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-4 | Subscribe на bus events | — | Reliable |
| ST-5 | Settings toggle | ST-4 | UI работает |

### Task 3

| Field | Fill In |
|---|---|
| **Task ID** | T-3 |
| **Related Use Case** | UC-2.1 |
| **Task Description** | Tray icon + menu items. |
| **Dependencies** | T-1 |
| **DoD** | Tray стабильно работает на 3 OS. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-6 | Native tray создание | — | Виден в OS |
| ST-7 | Menu items + actions | ST-6 | Все действия |
| ST-8 | Toggle close-to-tray | — | Конфигурируемо |

### Task 4

| Field | Fill In |
|---|---|
| **Task ID** | T-4 |
| **Related Use Case** | UC-2.2 |
| **Task Description** | Регистрация `opencode://` scheme и обработка deep-links. |
| **Dependencies** | T-1 |
| **DoD** | Открытие ссылки → нужная сессия. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-9 | OS-уровень регистрация scheme | — | Откликается |
| ST-10 | Routing внутри UI | ST-9 | Деки работают |

### Task 5

| Field | Fill In |
|---|---|
| **Task ID** | T-5 |
| **Related Use Case** | UC-3.1 |
| **Task Description** | Auto-update flow с signature checks. |
| **Dependencies** | T-1 |
| **DoD** | Обновляется на новый релиз без потери сессий. |

#### Subtasks

| Subtask ID | Description | Dependencies | Acceptance Criteria |
|---|---|---|---|
| ST-11 | Updater config + manifest endpoint | — | Manifest корректен |
| ST-12 | UI prompt + apply on next start | ST-11 | UX без сюрпризов |

---

## Footer / Notes

- Все feature-ids и task-ids внутри отдельного блока «Feature N» сбрасываются с 1 (US-1, UC-1.1, FR-1, T-1) — это намеренно для соответствия SPEC Template.
- Для cross-feature ссылок используется текст «см. Feature N».
- Источник всех названий, схем, путей и API: репозиторий [github.com/anomalyco/opencode](https://github.com/anomalyco/opencode), коммит `dev` (default branch).
- Документация фич: `packages/web/src/content/docs/*.mdx`. Технический спек session-API: `specs/project.md`, `specs/v2/session.md`.










