# SPEC — Feature 12: Agents / Skills / System-Prompt Subcommands

## 1. Feature Context

| Section | Fill In |
|---|---|
| **Feature** | Operational Subcommands: `claw agents`, `claw skills`, `claw system-prompt` |
| **Description (Goal / Scope)** | Три CLI subcommand'а из USAGE.md, обслуживающие inspection и управление agent-ресурсами вне основного REPL: (1) **`agents`** — список зарегистрированных sub-agents (специализированные роли — например code-reviewer, security-auditor) с их configs; (2) **`skills`** — список доступных skills (расширения с собственными prompts/инструкциями), маппинг на namespace; (3) **`system-prompt`** — печать текущего effective system-prompt (включая встроенный + аппенды от skills/agents/CLAUDE.md). Все три поддерживают `--output-format json`. Вне скоупа: создание agents/skills (это файловая операция в `.claw/agents/` или `.claw/skills/`). |
| **Client** | Разработчики (debug effective prompt), CI (audit зарегистрированных agents/skills), обертки (genertor settings UI). |
| **Problem** | Без `system-prompt` команды невозможно отладить, что именно модель видит как контекст — какие skills активны, что добавлено из CLAUDE.md. Без `agents`/`skills` сложно понять, какие специализированные роли установлены и что ожидать. |
| **Solution** | (1) Реестр agents (`.claw/agents/*.md` или `*.json`) — специализированные роли с custom system-prompt + tool-allowlist; (2) Реестр skills (`.claw/skills/*/SKILL.md`) — модульные расширения с собственными инструкциями; (3) `system-prompt` команда собирает effective prompt: built-in skeleton → CLAUDE.md project → активные skills → agent-specific (если в режиме sub-agent). |
| **Metrics** | (1) Все три команды отвечают ≤ 200 мс; (2) JSON output под schema, валиден; (3) `system-prompt` точно соответствует тому, что отправляется в API (verified parity-тестом); (4) Discovery 100 agents/skills ≤ 100 мс. |

## 2. User Stories and Use Cases

### US-1: `claw agents` — список и detail зарегистрированных sub-agents

| Field | Value |
|---|---|
| **Role** | Разработчик / оркестратор |
| **User Story** | Как пользователь, я хочу узнать, какие sub-agents (специализированные роли) доступны в моём окружении и какие у них tool-allowlists/system-prompts, чтобы выбрать правильного для делегирования. |

**UC-1.1: List agents.** Given в `.claw/agents/` есть 3 файла: `code-reviewer.md`, `security-auditor.md`, `docs-writer.md` → When `claw agents list` → Then таблица: `name | description | model | tools_count | mode`.

**FR-1:** Реестр agents читает `.claw/agents/*.md` (frontmatter + body) и `~/.claw/agents/*.md` с приоритетом repo > user. **FR-2:** Frontmatter обязательный: `{name, description, model?, tools?: Vec<String>, mode?: read-only|workspace-write}`. **NFR-1:** List ≤ 100 мс на 100 agents.

**UC-1.2: Show agent detail.** Given пользователь хочет увидеть полный system-prompt agent'а → When `claw agents show code-reviewer --output-format json` → Then JSON `{name, description, model, tools, mode, system_prompt: "<full>"}`.

**FR-3:** `show` поддерживает text (frontmatter table + body) и JSON формат. **FR-4:** Если agent не найден — exit 2 с suggestion (Levenshtein-based "did you mean").

### US-2: `claw skills` — discovery и инспекция skills

| Field | Value |
|---|---|
| **Role** | Разработчик |
| **User Story** | Как пользователь, я хочу видеть, какие skills (модульные расширения с custom-инструкциями) активны и при каких триггерах они подгружаются, чтобы понимать, как меняется поведение агента. |

**UC-2.1: List skills + status (active/passive).** Given в `.claw/skills/` есть `simplify/SKILL.md`, `claude-api/SKILL.md`, и в `~/.claw/skills/` — `init/SKILL.md` → When `claw skills list` → Then таблица: `name | source | description | trigger | status`.

**FR-5:** Skills имеют structure: `<skill-dir>/SKILL.md` (с frontmatter `{name, description, trigger?: regex|always|on-demand}`) + опциональные дополнительные файлы (templates, scripts). **FR-6:** Источник: `repo > user > builtin`; одинаковые имена с приоритетом по источнику. **NFR-2:** Discovery параллельный (rayon), 100 skills ≤ 100 мс.

**UC-2.2: Show skill content.** Given `claw skills show simplify --output-format json` → Then `{name, source, description, trigger, instructions: "<body>", files: [<additional file paths>]}`.

**FR-7:** Поддержка обоих форматов (text/JSON). **FR-8:** Skill instructions могут содержать template-placeholders `{{cwd}}`, `{{date}}` — resolved при подгрузке.

### US-3: `claw system-prompt` — effective prompt inspection

| Field | Value |
|---|---|
| **Role** | Разработчик / debugger |
| **User Story** | Как разработчик, я хочу видеть точный system-prompt, который отправляется в API, со всеми компонентами (built-in + CLAUDE.md + skills + agent-specific), чтобы отлаживать поведение модели и проверять prompt-injection. |

**UC-3.1: Print effective system-prompt.** Given текущая сессия использует agent `code-reviewer` + 2 active skills + project CLAUDE.md → When `claw system-prompt` → Then выводится конкатенированный effective prompt с разделителями `--- [section: builtin] ---`, `--- [section: project CLAUDE.md] ---`, `--- [section: skill: simplify] ---`, `--- [section: agent: code-reviewer] ---`.

**FR-9:** Composition order detereministic: builtin → user CLAUDE.md → project CLAUDE.md → active skills (alphabetical) → agent-specific. **FR-10:** `--output-format json` возвращает `{sections: [{label, content}], total_chars, total_tokens_estimate}`. **NFR-3:** Полученный prompt **точно совпадает** с тем, что отправляется в API (parity-тест).

**UC-3.2: Compare system-prompt across modes.** Given нужно сравнить prompt для разных agents → When `claw system-prompt --agent code-reviewer` vs `--agent docs-writer` → Then можно diff'ить вручную через `diff <(claw system-prompt --agent code-reviewer) <(claw system-prompt --agent docs-writer)`.

**FR-11:** Флаг `--agent <name>` overrides текущий sub-agent для preview. **FR-12:** Флаг `--without-skills` исключает skills для baseline. **NFR-4:** Команда не делает API-вызовов (полностью offline).

## 3. Architecture / Solution

| Area | Fill In |
|---|---|
| **Client Type** | CLI subcommands; интегрирован с `commands` crate |
| **Backend** | Discovery в `runtime` crate (новые модули `agents.rs`, `skills.rs`, `system_prompt.rs`); реестры in-memory с lazy-load |
| **Data Flow** | На subcommand: discovery всех источников → merge с приоритетами → render text/JSON. Для system-prompt: composition pipeline. |
| **Files** | `.claw/agents/*.md`, `.claw/skills/*/SKILL.md`, `~/.claw/agents/`, `~/.claw/skills/`; builtin embedded через `include_str!` |
| **Infra** | Файловая система; нет network |

## 4. Work Plan

| UC | Task | DoD | Subtasks |
|---|---|---|---|
| UC-1.1, UC-1.2 | T-1: Agents registry + `list`/`show` subcommands + JSON output | 100 agents discoverable; show с JSON-schema validation | ST-1, ST-2, ST-3 |
| UC-2.1, UC-2.2 | T-2: Skills registry с triggers + `list`/`show` | Skills discoverable из 3 источников; trigger-types работают | ST-4, ST-5 |
| UC-3.1 | T-3: System-prompt composition pipeline + `system-prompt` command | Composition deterministic; parity-тест с реальным API call | ST-6, ST-7, ST-8 |
| UC-3.2 | T-4: Флаги `--agent`, `--without-skills`, `--output-format json` | Все флаги покрыты integration-тестами | ST-9, ST-10 |
| — | T-5: Builtin skills/agents embedded через `include_str!` | Стандартный набор доступен сразу после установки | ST-11, ST-12 |

## 5. Detailed Task Breakdown

**T-1 / Agents.** ST-1: parser frontmatter + body для `*.md`; ST-2: registry с приоритетом repo > user; ST-3: subcommand handlers (list/show) + JSON-renderer.
**T-2 / Skills.** ST-4: discovery `<skill-dir>/SKILL.md` + extra files; ST-5: trigger-types (regex/always/on-demand) + active-set computation.
**T-3 / System-prompt composition.** ST-6: composition pipeline (builtin → user → project → skills → agent); ST-7: token-estimate (через tiktoken-rs или эквивалент); ST-8: parity-тест: prompt из команды === prompt отправленный в API.
**T-4 / Флаги.** ST-9: `--agent <name>` overrides; ST-10: `--without-skills` + JSON-output schema.
**T-5 / Builtin embedding.** ST-11: builtin skills (init, security-review, и т.д.) через `include_str!`; ST-12: builtin agents (code-reviewer и др.) с дефолтными tool-allowlists.
