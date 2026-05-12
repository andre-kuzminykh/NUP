"""Сборщик argv для смок-теста Reels.

Минимальный режим: 1 цветной фон 1080×1920, 1 TTS-дорожка, drawtext с
заголовком сверху и субтитрами по 3 слова в кадр снизу.

Pure function — не делает I/O, можно юнит-тестировать структуру команды.
"""
from __future__ import annotations

OUT_W = 1080
OUT_H = 1920


def _esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\\'")
        .replace(",", r"\,")
    )


def build_simple_reel_ffmpeg(
    *,
    audio_path: str,
    duration_sec: float,
    title: str,
    chunks: list[str],
    output_path: str,
    bg_color: str = "0x1e293b",
    font_color: str = "white",
    fontsize: int = 56,
    title_fontsize: int = 64,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Собрать argv для одного Reels.

    chunks — список 3-словных строк (см. domain.segment.chunk_subtitle).
    Они равномерно распределяются по timeline'у.
    """
    filters: list[str] = []

    if title:
        filters.append(
            f"drawtext=text='{_esc(title)}':"
            f"fontcolor={font_color}:fontsize={title_fontsize}:"
            f"box=1:boxcolor=black@0.5:boxborderw=22:"
            f"x=(w-text_w)/2:y=h*0.18"
        )

    non_empty = [c for c in chunks if c]
    if non_empty:
        per = duration_sec / len(chunks)
        for i, c in enumerate(chunks):
            if not c:
                continue
            t0 = i * per
            t1 = (i + 1) * per
            filters.append(
                f"drawtext=text='{_esc(c)}':"
                f"fontcolor={font_color}:fontsize={fontsize}:"
                f"box=1:boxcolor=black@0.55:boxborderw=16:"
                f"x=(w-text_w)/2:y=h*0.72:"
                f"enable='between(t,{t0:.3f},{t1:.3f})'"
            )

    vf = ",".join(filters) if filters else "null"

    return [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"color=c={bg_color}:s={OUT_W}x{OUT_H}:d={duration_sec:.3f}",
        "-i", audio_path,
        "-vf", vf,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
