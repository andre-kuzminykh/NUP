# F07 — Stock Search & Vision Selection

По `Segment.keywords` искать вертикальные клипы в Pexels, для каждого preview-фрейма получать описание через GPT-4o vision, выбирать лучший по семантическому соответствию `Segment.text`.

## User stories

- **US-F07-1**: As an editor, I want per-segment search to return ≥3 portrait clips so that selection has meaningful choice.
- **US-F07-2**: As an editor, I want a vision LLM to describe each preview frame in 1–2 RU sentences so that the picker model has structured context.
- **US-F07-3**: As an editor, I want a final picker LLM to return only one `best_video_url` per segment so that downstream assembly is deterministic.
- **US-F07-4**: As an operator, I want per-clip dedupe (no clip repeated across segments of the same Reels) so that видеоряд не выглядит одинаково.

## User flow

```
event "reels.tts_complete" ─► for each segment:
   PexelsAdapter.search(keywords, orientation=portrait, per_page=3) → candidates
   for each candidate:
       VisionLLM.describe(preview_url) → ru text
   PickerLLM.choose(segment.text, [candidates+descriptions]) → best_video_url
   SegmentRepo.update(video_uri=best_video_url)
event "reels.video_picked" when ALL segments have video_uri
```
