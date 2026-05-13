"""F013 — CandidateRefresher: подсосать новых клипов на текущий сегмент.

Используется кнопкой «🔄 Найти ещё» в edit-mode, когда оператора не
устраивают предложенные 5-10 кандидатов. Сервис:

1. Берёт current segment (по `edit_state.cursor`).
2. Зовёт Pexels/Pixabay снова — со страницы `refresh_offset+1`, чтобы
   гарантированно получить НЕ те же видео.
3. Качает mp4 во временный файл → uploadит в Telegram (silent) →
   фиксирует file_id → удаляет message + локальный файл.
4. ДОБАВЛЯЕТ свежих кандидатов В КОНЕЦ списка (cap MAX_CANDIDATES_PER_SEG=90),
   старые НЕ убирает. active_idx переставляется на ПЕРВЫЙ новый клип, чтобы
   оператор сразу увидел свежий вариант.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Protocol

from nup_pipeline.domain.review import ReviewSession


MAX_CANDIDATES_PER_SEG = 90


class _ReviewRepo(Protocol):
    def get(self, review_id: str) -> ReviewSession | None: ...
    def save(self, r: ReviewSession) -> None: ...


class _StockSearch(Protocol):
    def search_videos(self, query: str, *, per_page: int, **kw) -> list[dict]: ...


class _TelegramUploader(Protocol):
    def upload_video_for_file_id(
        self, chat_id, local_path,
    ) -> tuple[str, int]: ...
    def delete_message(self, chat_id, message_id: int) -> None: ...


class _TextLlm(Protocol):
    def complete_text(self, prompt: str) -> str: ...


Downloader = Callable[[str, str], None]


def _default_download(url: str, dest: str) -> None:
    import httpx
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


class CandidateRefresher:
    def __init__(
        self,
        repo: _ReviewRepo,
        pexels: _StockSearch | None,
        pixabay: _StockSearch | None,
        telegram: _TelegramUploader,
        *,
        per_page: int = 10,
        download: Downloader | None = None,
        llm: _TextLlm | None = None,
    ) -> None:
        self._repo = repo
        self._pexels = pexels
        self._pixabay = pixabay
        self._tg = telegram
        self._per_page = per_page
        self._download = download or _default_download
        self._llm = llm

    def refresh(self, review_id: str, query: str | None = None) -> dict:
        """Заменить кандидатов текущего сегмента на свежую партию.

        query: если задан — переопределяет keyword для поиска. Иначе берём
        из текущего сегмента (`seg['keyword']`) или из текста сегмента.
        Если по next-странице ничего нового не нашлось — просим LLM выдать
        другой keyword (один LLM-вызов) и повторяем поиск с page=1.
        """
        r = self._repo.get(review_id)
        if r is None:
            raise KeyError(review_id)
        segments = list(r.segments_snapshot or [])
        if not segments:
            return self._payload(r)
        cursor = int((r.edit_state or {}).get("cursor", 0))
        cursor = max(0, min(cursor, len(segments) - 1))
        seg = dict(segments[cursor])

        seen_urls = {
            c.get("video_url")
            for c in (seg.get("candidates") or [])
            if c.get("video_url")
        }
        # tried_keywords хранит все ранее использованные на этом сегменте
        # запросы, чтобы LLM не выдал то же самое снова.
        tried_keywords: list[str] = list(seg.get("tried_keywords") or [])
        original_kw = seg.get("keyword") or (seg.get("text") or "").strip()[:60]
        if original_kw and original_kw not in tried_keywords:
            tried_keywords.append(original_kw)

        refresh_offset = int(seg.get("refresh_offset", 0)) + 1
        kw = query or seg.get("keyword") or original_kw
        if not kw:
            return self._payload(r)

        fresh = self._search(kw, refresh_offset + 1, seen_urls)
        if not fresh and self._llm is not None:
            new_kw = self._rephrase(seg.get("text", ""), tried_keywords)
            if new_kw and new_kw not in tried_keywords:
                tried_keywords.append(new_kw)
                kw = new_kw
                refresh_offset = 0  # новый keyword → начинаем с page=1
                fresh = self._search(kw, 1, seen_urls)

        if not fresh:
            seg["refresh_offset"] = refresh_offset
            seg["tried_keywords"] = tried_keywords
            seg["keyword"] = kw
            segments[cursor] = seg
            r.segments_snapshot = segments
            self._repo.save(r)
            return self._payload(r)

        # Ограничиваем сколько ещё можно добавить, чтобы не пробить лимит 90.
        existing = list(seg.get("candidates") or [])
        room = max(0, MAX_CANDIDATES_PER_SEG - len(existing))
        if room == 0:
            seg["refresh_offset"] = refresh_offset
            seg["tried_keywords"] = tried_keywords
            seg["keyword"] = kw
            segments[cursor] = seg
            r.segments_snapshot = segments
            self._repo.save(r)
            return self._payload(r)
        fresh = fresh[: min(self._per_page, room)]
        new_candidates = self._download_and_preupload(r, fresh)
        if not new_candidates:
            return self._payload(r)

        # Append + перевод курсора на первый новый клип.
        first_new_idx = len(existing)
        seg["candidates"] = existing + new_candidates
        seg["active_idx"] = first_new_idx
        seg["refresh_offset"] = refresh_offset
        seg["tried_keywords"] = tried_keywords
        seg["keyword"] = kw
        segments[cursor] = seg
        r.segments_snapshot = segments
        self._repo.save(r)
        return self._payload(r)

    # --- helpers -----------------------------------------------------------

    def _search(self, kw: str, page: int, seen_urls: set) -> list[dict]:
        raw: list[dict] = []
        for source in (self._pexels, self._pixabay):
            if source is None:
                continue
            try:
                raw += source.search_videos(
                    kw, per_page=self._per_page, page=page,
                )
            except Exception:
                continue
        return [
            c for c in raw
            if c.get("video_url") and c["video_url"] not in seen_urls
        ]

    def _rephrase(self, sentence: str, tried: list[str]) -> str:
        prompt = (
            "You're choosing search terms for stock-video sites (Pexels/Pixabay).\n"
            f"Article sentence: {sentence[:200]}\n"
            f"AVOID these keywords (already tried): {', '.join(tried) or '(none)'}\n"
            "Output ONE short ENGLISH visual keyword (1-3 words, lowercase, no\n"
            "proper nouns). Different angle from what was tried before.\n"
            "OUTPUT (just the keyword):"
        )
        try:
            raw = (self._llm.complete_text(prompt) or "").strip()
        except Exception:
            return ""
        # Первое слово/строка, чистим bullets и нумерацию.
        line = raw.splitlines()[0].strip().strip("-•*").strip() if raw else ""
        if line and line[0].isdigit() and "." in line[:4]:
            line = line.split(".", 1)[1].strip()
        return line.lower()

    def _download_and_preupload(
        self, r: ReviewSession, fresh: list[dict],
    ) -> list[dict]:
        new_candidates: list[dict] = []
        with tempfile.TemporaryDirectory() as tmp:
            for j, c in enumerate(fresh):
                url = c["video_url"]
                local = str(Path(tmp) / f"refresh_{j}.mp4")
                try:
                    self._download(url, local)
                except Exception:
                    continue
                file_id: str | None = None
                try:
                    file_id, msg_id = self._tg.upload_video_for_file_id(
                        r.reviewer_chat_id, local,
                    )
                    self._tg.delete_message(r.reviewer_chat_id, msg_id)
                except Exception:
                    file_id = None
                new_candidates.append({
                    "video_url": url,
                    "local_path": "",
                    "preview_url": c.get("preview_url", ""),
                    "file_id": file_id,
                })
                try:
                    os.remove(local)
                except OSError:
                    pass
        return new_candidates

    def _payload(self, r: ReviewSession) -> dict[str, Any]:
        # Тонкая обёртка над editor._payload — но мы не зависим от editor,
        # чтобы избежать цикл. импорта. Локальный slim-projection.
        segments = r.segments_snapshot or []
        total = len(segments)
        cursor = int((r.edit_state or {}).get("cursor", 0)) if total else 0
        cursor = max(0, min(cursor, total - 1)) if total else 0
        if total == 0:
            return {
                "review_id": r.id, "status": r.status.value,
                "cursor": 0, "total": 0, "segment_text": "",
                "candidate_idx": 0, "candidate_total": 0,
                "active_video_url": None, "active_preview_url": None,
                "active_file_id": None,
            }
        seg = segments[cursor]
        candidates = seg.get("candidates") or []
        active_idx = int(seg.get("active_idx", 0))
        active_idx = max(0, min(active_idx, len(candidates) - 1)) if candidates else 0
        active = candidates[active_idx] if candidates else {}
        return {
            "review_id": r.id,
            "status": r.status.value,
            "cursor": cursor,
            "total": total,
            "segment_text": seg.get("text", ""),
            "candidate_idx": active_idx,
            "candidate_total": len(candidates),
            "active_video_url": active.get("video_url") if active else None,
            "active_preview_url": active.get("preview_url") if active else None,
            "active_file_id": active.get("file_id") if active else None,
        }
