"""Сборщик argv для одного Reels (без многосегментной нарезки F008).

Два режима:
  - bg_color="0x..."     → одноцветный фон через lavfi color (без видео-фона)
  - bg_video_path=...    → стоковый клип (loop+scale+crop до 1080x1920)

Над фоном — drawtext: заголовок сверху и субтитры по 3 слова в кадр.
Pure function — не делает I/O, юнит-тестируется по структуре argv.
"""
from __future__ import annotations

OUT_W = 1080
OUT_H = 1920
# DejaVuSans-Bold ставится в Dockerfile (fonts-dejavu-core). На локальных
# Debian/Ubuntu путь тот же. Переопределяется параметром font_file.
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\\'")
        .replace(",", r"\,")
    )


def _drawtext_chain(
    *,
    title: str,
    chunks: list[str],
    duration_sec: float,
    font_color: str,
    fontsize: int,
    title_fontsize: int,
    font_file: str,
) -> str:
    filters: list[str] = []
    if title:
        filters.append(
            f"drawtext=fontfile='{font_file}':text='{_esc(title)}':"
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
                f"drawtext=fontfile='{font_file}':text='{_esc(c)}':"
                f"fontcolor={font_color}:fontsize={fontsize}:"
                f"box=1:boxcolor=black@0.55:boxborderw=16:"
                f"x=(w-text_w)/2:y=h*0.72:"
                f"enable='between(t,{t0:.3f},{t1:.3f})'"
            )
    return ",".join(filters) if filters else "null"


def build_simple_reel_ffmpeg(
    *,
    audio_path: str,
    duration_sec: float,
    title: str,
    chunks: list[str],
    output_path: str,
    bg_color: str = "0x1e293b",
    bg_video_path: str | None = None,
    font_color: str = "white",
    fontsize: int = 56,
    title_fontsize: int = 64,
    font_file: str = DEFAULT_FONT,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Собрать argv для одного Reels.

    Если bg_video_path передан — стоковый клип используется как фон
    (loop + scale + center-crop до 1080x1920). Иначе — одноцветный bg_color.
    """
    drawtexts = _drawtext_chain(
        title=title,
        chunks=chunks,
        duration_sec=duration_sec,
        font_color=font_color,
        fontsize=fontsize,
        title_fontsize=title_fontsize,
        font_file=font_file,
    )

    if bg_video_path:
        # Loop short clips, scale+crop to 1080x1920, then drawtext over the top.
        # Звук берётся ТОЛЬКО из TTS (audio_path), исходный звук стока заглушается.
        chain = (
            f"[0:v]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
            f"crop={OUT_W}:{OUT_H},"
            f"setsar=1,"
            f"trim=duration={duration_sec:.3f},"
            f"setpts=PTS-STARTPTS"
        )
        if drawtexts and drawtexts != "null":
            chain += f",{drawtexts}"
        chain += "[v]"
        return [
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", bg_video_path,
            "-i", audio_path,
            "-filter_complex", chain,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-c:a", "aac",
            "-shortest", "-movflags", "+faststart",
            output_path,
        ]

    # Fallback — однотонный фон через lavfi color.
    return [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"color=c={bg_color}:s={OUT_W}x{OUT_H}:d={duration_sec:.3f}",
        "-i", audio_path,
        "-vf", drawtexts,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac",
        "-shortest", "-movflags", "+faststart",
        output_path,
    ]
