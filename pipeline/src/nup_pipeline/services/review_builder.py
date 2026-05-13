"""F013/F014 — ReviewBuilder: общая логика сборки Reels для submit и regenerate.

Извлечена из cli/submit_for_review.py чтобы:
- API endpoint /regenerate мог пересобрать review для той же статьи
  (новые формулировки, новые клипы) без дублирования кода.
- CLI остался тонким враппером над сервисом.

Сервис делает: summary → voiceover → split → TTS → per-seg keywords →
search/preupload кандидатов → ffmpeg render. НЕ отправляет/редактирует
сообщение в Telegram — это делает caller (CLI sends, API edits).
"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Protocol

from nup_pipeline.domain.article import Article
from nup_pipeline.domain.review import ReviewSession
from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.ffprobe import probe_duration_sec
from nup_pipeline.infra.telegram import TelegramError
from nup_pipeline.services.ffmpeg_builder import build as build_ffmpeg
from nup_pipeline.services.summarize import BilingualSummarizer
from nup_pipeline.services.visual_keywords import VisualKeywords
from nup_pipeline.services.voiceover_scripter import VoiceoverScripter


# Простые порт-протоколы — облегчают тесты.

class _Llm(Protocol):
    def complete_json(self, prompt: str) -> dict: ...
    def complete_text(self, prompt: str) -> str: ...


class _Tts(Protocol):
    def synthesize(self, text: str) -> bytes: ...


class _StockSearch(Protocol):
    def search_videos(self, query: str, *, per_page: int, **kw) -> list[dict]: ...


class _TelegramUploader(Protocol):
    def upload_video_for_file_id(self, chat_id, local_path) -> tuple[str, int]: ...
    def delete_message(self, chat_id, message_id: int) -> None: ...


class _FfmpegRunner(Protocol):
    def run(self, argv, *, output_path: str, timeout: int = ...) -> None: ...


class _ReviewRepo(Protocol):
    def save(self, r: ReviewSession) -> None: ...


_SENT = re.compile(r"(?<=[\.!?\?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]


def _download(url: str, dest: str) -> None:
    import httpx
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


def _short_description(content_ru: str, limit: int = 320) -> str:
    """Короткое описание для caption: первые 1-2 предложения, ≤ limit."""
    text = (content_ru or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Обрезаем по последнему завершённому предложению.
    last_dot = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_dot > limit // 2:
        return cut[: last_dot + 1].strip()
    return cut.rstrip() + "…"


def build_caption(title_ru: str, content_ru: str, link: str) -> str:
    desc = _short_description(content_ru)
    parts = [f"*{title_ru}*"]
    if desc:
        parts.append(desc)
    parts.append(f"[📰 Полная новость]({link})")
    return ("\n\n".join(parts))[:1024]


class ReviewBuilder:
    def __init__(
        self,
        *,
        llm: _Llm,
        tts: _Tts,
        pexels: _StockSearch | None,
        pixabay: _StockSearch | None,
        telegram: _TelegramUploader,
        ffmpeg_runner: _FfmpegRunner,
        review_repo: _ReviewRepo,
        out_root: Path,
        candidates_per_segment: int = 10,
    ) -> None:
        self._llm = llm
        self._tts = tts
        self._pexels = pexels
        self._pixabay = pixabay
        self._tg = telegram
        self._ffmpeg = ffmpeg_runner
        self._repo = review_repo
        self._out_root = out_root
        self._cands = candidates_per_segment

    def build(self, article: Article, review: ReviewSession) -> ReviewSession:
        """Полностью пересобирает контент для review: новые segments_snapshot,
        новый reel.mp4 в свежей work-папке, обновлённые output_uri/caption.
        Сохраняет review через repo. Возвращает её же."""
        bundle = BilingualSummarizer(llm=self._llm).summarize(article)
        voice_text = VoiceoverScripter(llm=self._llm).script(bundle.content_ru)
        sentences = split_sentences(voice_text)
        if not sentences:
            raise ValueError("empty voiceover script")

        work_dir = self._out_root / f"reel_{uuid.uuid4().hex[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. TTS.
        audio_paths: list[Path] = []
        durations: list[float] = []
        for i, sentence in enumerate(sentences):
            path = work_dir / f"voice_{i:02d}.mp3"
            path.write_bytes(self._tts.synthesize(sentence))
            durations.append(probe_duration_sec(str(path)))
            audio_paths.append(path)

        # 2. Visual keywords.
        per_seg_kws = VisualKeywords(llm=self._llm).keywords_per_segment(
            bundle.title_en, sentences,
            fallback=[bundle.title_en or "technology"],
        )

        # 3. Per-segment search + preupload (≤candidates_per_segment).
        used_urls: set[str] = set()
        segments_snapshot: list[dict] = []
        chosen_video_paths: list[Path] = []
        for i in range(len(sentences)):
            kw = per_seg_kws[i]
            cands_raw = self._search(kw, want=max(self._cands * 2, 6))
            if not cands_raw:
                raise RuntimeError(f"no clips for seg{i} keyword={kw!r}")
            unused = [c for c in cands_raw if c["video_url"] not in used_urls]
            ordered = unused + [c for c in cands_raw if c["video_url"] in used_urls]
            candidates = ordered[: self._cands]
            used_urls.add(candidates[0]["video_url"])

            # ВАЖНО: preupload в Telegram НЕ делаем — оператор не хочет видеть
            # silent uploads-deletes в чате. file_id заполнится лениво при
                # первом edit_media в edit-mode (Telegram сам кеширует URL).
            candidates_meta: list[dict] = []
            for j, c in enumerate(candidates):
                url = c["video_url"]
                # Качаем только active-клип (cand[0]) — нужен для ffmpeg.
                # Остальные кандидаты подгружаются по URL при «Сохранить».
                local_path_str = ""
                if j == 0:
                    local = work_dir / f"bg_{i:02d}_{j}.mp4"
                    _download(url, str(local))
                    local_path_str = str(local)
                candidates_meta.append({
                    "video_url": url,
                    "local_path": local_path_str,
                    "preview_url": c.get("preview_url", ""),
                    "file_id": None,
                })
            segments_snapshot.append({
                "text": sentences[i],
                "audio_path": str(audio_paths[i]),
                "duration": durations[i],
                "keyword": kw,
                "candidates": candidates_meta,
                "active_idx": 0,
                "refresh_offset": 0,
            })
            chosen_video_paths.append(Path(candidates_meta[0]["local_path"]))

        # 4. ffmpeg render.
        out_path = work_dir / "reel.mp4"
        argv = build_ffmpeg(
            [
                Segment(
                    audio_uri=str(audio_paths[i]),
                    video_uri=str(chosen_video_paths[i]),
                    audio_duration_sec=durations[i],
                    subtitle_text=sentences[i],
                )
                for i in range(len(sentences))
            ],
            music_uri=None,
            output_path=str(out_path),
        )
        self._ffmpeg.run(argv, output_path=str(out_path), timeout=600)
        # Latest copy под reels_out для scp.
        try:
            shutil.copy(
                out_path,
                Path(os.environ.get("REELS_OUT_DIR", "/tmp")) / "last_reel.mp4",
            )
        except OSError:
            pass

        # 5. Update review.
        review.output_uri = str(out_path)
        review.caption = build_caption(bundle.title_ru, bundle.content_ru, article.link)
        review.segments_snapshot = segments_snapshot
        review.edit_state = None
        self._repo.save(review)
        return review

    def _search(self, kw: str, *, want: int) -> list[dict]:
        out: list[dict] = []
        if self._pexels is not None:
            try:
                out += self._pexels.search_videos(kw, per_page=want)
            except Exception:
                pass
        if len(out) < want and self._pixabay is not None:
            try:
                out += self._pixabay.search_videos(kw, per_page=want)
            except Exception:
                pass
        if out and len(out) < want:
            while len(out) < want:
                out.append(out[len(out) % len(out)])
        return out[:want]
