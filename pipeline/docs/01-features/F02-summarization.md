# F02 — Article Summarization

LLM превращает `Article.raw_content` в `Summary{title_ru, content_ru, content_tg}` — пост для Telegram-канала.

## User stories

- **US-F02-1**: As an editor, I want each ingested article to be summarized in Russian with a short bold headline so that posts have consistent style.
- **US-F02-2**: As an editor, I want the model to keep technical terms (`LLM`, `multiagent systems`) intact or use a fixed Russian translation so that the channel doesn't drift in vocabulary.
- **US-F02-3**: As an operator, I want a single source-of-truth prompt file in repo so that prompt edits are reviewed in PRs.

## User flow

```
event "article.ingested" ─► SummarizerService(article)
   ├─► load prompt from docs/05-prompts/article-summary.md
   ├─► OpenAI chat.completions(model=gpt-4.1, ...)
   ├─► validate output (regex headline + non-empty body)
   └─► SummaryRepo.save(article_id, …)
       └─► emit "article.summarized"
```
