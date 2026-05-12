"""Pure FFmpeg argv builder for F08 Video Assembly.

Conventions:
- All video inputs come first, then all audio inputs, then optional music.
  -i V0 -i V1 ... -i VN-1 -i A0 -i A1 ... -i AN-1 [-i MUSIC]
- Output: 1080x1920 9:16 H.264, AAC.
- Per-segment subtitle = 3-word chunks (chunk_subtitle), distributed equally
  over segment length, drawn in lower-third area.

This module performs ZERO I/O. All filesystem touches happen in
nup_pipeline.infra.ffmpeg.FfmpegRunner.

Tested by:
- tests/unit/test_ffmpeg_builder.py
- tests/integration/test_ffmpeg_real.py
"""
from __future__ import annotations

from nup_pipeline.domain.segment import Segment, chunk_subtitle

OUT_W = 1080
OUT_H = 1920
MUSIC_VOLUME = 0.01
# Чанки по 2 слова: русские слова длиннее английских, 3 часто не помещаются.
# 2 слова почти всегда умещаются в одну строку без переноса.
SUBTITLE_WORDS_PER_CHUNK = 2
# Шрифт с кириллицей; ставится в Dockerfile (fonts-dejavu-core).
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _esc_drawtext(s: str) -> str:
    """Escape a string for ffmpeg drawtext text=... value (single-quoted form).
    Wrap-логику (multi-line через \\n) сняли: drawtext \\n внутри filtergraph
    рендерится непредсказуемо. Если 2-словный чанк всё равно слишком длинный
    (редкий случай), пусть лучше переползёт край, чем выйдет литералом 'n'.
    """
    return (
        s.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\\'")
        .replace(",", r"\,")
    )


def _segment_video_filter(
    seg_idx: int, in_label: str, dur: float, subtitle: str, out_label: str
) -> str:
    """One filter chain for a single segment's video: scale → crop → trim → drawtexts."""
    chain = (
        f"[{in_label}]"
        f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
        f"crop={OUT_W}:{OUT_H},"
        f"setsar=1,"
        f"trim=duration={dur:.3f},"
        f"setpts=PTS-STARTPTS"
    )
    chunks = chunk_subtitle(subtitle, n=SUBTITLE_WORDS_PER_CHUNK)
    non_empty = [c for c in chunks if c]
    if non_empty:
        per = dur / len(chunks)
        for i, c in enumerate(chunks):
            if not c:
                continue
            t0 = i * per
            t1 = (i + 1) * per
            chain += (
                f",drawtext=fontfile='{DEFAULT_FONT}':text='{_esc_drawtext(c)}':"
                f"fontcolor=white:fontsize=58:"
                f"box=1:boxcolor=black@0.55:boxborderw=18:"
                f"x=(w-text_w)/2:y=h*0.72:"
                f"enable='between(t,{t0:.3f},{t1:.3f})'"
            )
    chain += f"[{out_label}]"
    return chain


def _segment_audio_filter(in_label: str, dur: float, out_label: str) -> str:
    return (
        f"[{in_label}]"
        f"atrim=duration={dur:.3f},"
        f"asetpts=PTS-STARTPTS"
        f"[{out_label}]"
    )


def build(
    segments: list[Segment],
    music_uri: str | None,
    output_path: str,
    *,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Build a complete `argv` for ffmpeg. Pure function; performs no I/O.

    Args:
        segments: ≥1 segments, each carrying video_uri, audio_uri, audio_duration_sec, subtitle_text.
        music_uri: optional background music input URL/path.
        output_path: target file path.
        ffmpeg_bin: binary name (override for tests).

    Returns:
        argv list suitable for subprocess.run.
    """
    if not segments:
        raise ValueError("at least one segment is required")

    n = len(segments)
    argv: list[str] = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]

    # Inputs: videos first, then audios, then music.
    for s in segments:
        argv += ["-i", s.video_uri]
    for s in segments:
        argv += ["-i", s.audio_uri]
    if music_uri:
        argv += ["-i", music_uri]
    music_idx = 2 * n if music_uri else None

    # Build filter graph.
    chains: list[str] = []
    total_dur = 0.0
    seg_v_labels: list[str] = []
    seg_a_labels: list[str] = []
    for i, s in enumerate(segments):
        v_in = f"{i}:v"
        a_in = f"{n + i}:a"
        v_out = f"v{i}"
        a_out = f"a{i}"
        chains.append(_segment_video_filter(i, v_in, s.audio_duration_sec, s.subtitle_text, v_out))
        chains.append(_segment_audio_filter(a_in, s.audio_duration_sec, a_out))
        seg_v_labels.append(v_out)
        seg_a_labels.append(a_out)
        total_dur += s.audio_duration_sec

    # Concat: interleave [v0][a0][v1][a1]...
    concat_inputs = "".join(f"[{v}][{a}]" for v, a in zip(seg_v_labels, seg_a_labels))
    chains.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vfinal][acat]")

    if music_idx is not None:
        # Loop music to total duration, then mix at low volume.
        chains.append(
            f"[{music_idx}:a]aloop=loop=-1:size=2147483647,"
            f"atrim=duration={total_dur:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"volume={MUSIC_VOLUME}[mbg]"
        )
        chains.append("[acat][mbg]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    else:
        chains.append("[acat]anull[aout]")

    filter_complex = ";".join(chains)

    argv += [
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-movflags", "+faststart",
        "-shortest",
        output_path,
    ]
    return argv
