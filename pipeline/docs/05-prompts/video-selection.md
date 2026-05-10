# Prompt: Video Selection (F07 — picker)

Variables: `{{segment_text}}`, `{{candidates_json}}`, `{{segment_id}}`.

```
Ты ассистент, который выбирает наиболее подходящий видеоролик для текста.

Текст сегмента:
"{{segment_text}}"

Кандидаты:
{{candidates_json}}

Задача: внимательно выбери только один video_url из списка для видеоролика, описание которого лучше всего соответствует тексту сегмента по смыслу. Учитывай и описание превью, и сам текст.

Верни только JSON строго в таком виде:
{
  "segment_id": {{segment_id}},
  "text": "{{segment_text}}",
  "best_video_url": "..."
}
```

Output validation: JSON со схемой `{segment_id:int, text:str, best_video_url:url}`.
