"""F013 — ReelRebuilder: пересобрать mp4 по операторским выборам.

При «💾 Сохранить» в edit-mode оператор зафиксировал свой набор
candidates[active_idx] на каждом сегменте. Нужно собрать новый reel.mp4
из тех же voice_NN.mp3 и НОВЫХ bg-клипов и заменить review.output_uri.

Сервис чистый — никаких side-effects кроме создания нового mp4 в work_dir.
Telegram-edit делает вызывающий код.

Tested by tests/unit/test_reel_rebuilder.py.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Protocol

from nup_pipeline.domain.review import ReviewSession
from nup_pipeline.domain.segment import Segment
from nup_pipeline.services.ffmpeg_builder import build as build_ffmpeg


Downloader = Callable[[str, str], None]


def _default_download(url: str, dest: str) -> None:
    import httpx
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)


class _FfmpegRunner(Protocol):
    def run(self, argv, *, output_path: str, timeout: int = ...) -> None: ...


class ReelRebuilder:
    def __init__(
        self,
        runner: _FfmpegRunner,
        *,
        download: Downloader | None = None,
    ) -> None:
        self._runner = runner
        self._download = download or _default_download

    def rebuild(self, review: ReviewSession) -> str:
        """Возвращает путь к новому reel.mp4. Старый — заменяется in-place.

        Raises FileNotFoundError, если рабочий каталог уже подчищен.
        """
        if not review.output_uri:
            raise ValueError("review has no output_uri to derive work_dir from")
        work_dir = Path(review.output_uri).parent
        if not work_dir.exists():
            raise FileNotFoundError(f"work_dir gone: {work_dir}")
        segments = review.segments_snapshot or []
        if not segments:
            raise ValueError("review has no segments_snapshot")

        built: list[Segment] = []
        for i, seg in enumerate(segments):
            audio_path = seg.get("audio_path") or ""
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"missing voice for seg{i}: {audio_path}")
            candidates = seg.get("candidates") or []
            if not candidates:
                raise ValueError(f"seg{i} has no candidates")
            active_idx = int(seg.get("active_idx", 0))
            active_idx = max(0, min(active_idx, len(candidates) - 1))
            cand = candidates[active_idx]
            video_local = cand.get("local_path") or ""
            if not video_local or not os.path.exists(video_local):
                # Кандидат был preuploaded но локально не сохранён —
                # качаем по video_url в work_dir.
                url = cand.get("video_url") or ""
                if not url:
                    raise ValueError(f"seg{i} active candidate has no video_url")
                video_local = str(work_dir / f"rebuild_{i:02d}_{active_idx}.mp4")
                if not os.path.exists(video_local):
                    self._download(url, video_local)
                # Кешируем local_path обратно в snapshot для повторных пересборок.
                cand["local_path"] = video_local
            built.append(Segment(
                audio_uri=audio_path,
                video_uri=video_local,
                audio_duration_sec=float(seg.get("duration", 0.0)),
                subtitle_text=seg.get("text", ""),
            ))

        new_out = str(work_dir / "reel.mp4")
        argv = build_ffmpeg(built, music_uri=None, output_path=new_out)
        self._runner.run(argv, output_path=new_out, timeout=600)
        return new_out
