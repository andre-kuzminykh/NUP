"""F08 — FfmpegBuilder pure-function tests.

Traces: REQ-F08-002, REQ-F08-003, REQ-F08-004, REQ-F08-005, REQ-F08-006, REQ-F08-011, REQ-F08-012.
"""
from __future__ import annotations

import pytest

from nup_pipeline.domain.segment import Segment
from nup_pipeline.services.ffmpeg_builder import build


def _seg(i: int, dur: float = 2.0, text: str = "one two three four") -> Segment:
    return Segment(
        audio_uri=f"https://example.com/audio_{i}.mp3",
        video_uri=f"https://example.com/video_{i}.mp4",
        audio_duration_sec=dur,
        subtitle_text=text,
    )


@pytest.mark.unit
@pytest.mark.req("REQ-F08-011")
def test_builder_returns_argv_list_starting_with_ffmpeg() -> None:
    argv = build([_seg(0)], music_uri=None, output_path="/tmp/out.mp4")
    assert isinstance(argv, list)
    assert all(isinstance(x, str) for x in argv)
    assert argv[0] == "ffmpeg"
    assert argv[-1] == "/tmp/out.mp4"


@pytest.mark.unit
@pytest.mark.req("REQ-F08-011")
def test_builder_is_pure_no_io(tmp_path) -> None:
    """Calling build() must not touch the filesystem or network."""
    # Pass non-existent paths — pure builder must not check them.
    argv = build(
        [Segment(
            audio_uri="/nonexistent/audio.mp3",
            video_uri="/nonexistent/video.mp4",
            audio_duration_sec=1.0,
            subtitle_text="x",
        )],
        music_uri="/nonexistent/music.mp3",
        output_path=str(tmp_path / "out.mp4"),
    )
    assert "ffmpeg" == argv[0]
    # tmp_path must remain empty — builder didn't write anything.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
@pytest.mark.req("REQ-F08-002")
def test_output_codec_and_pixfmt_flags_present() -> None:
    argv = build([_seg(0)], music_uri=None, output_path="/tmp/o.mp4")
    assert "-c:v" in argv
    assert argv[argv.index("-c:v") + 1] == "libx264"
    assert "-pix_fmt" in argv
    assert argv[argv.index("-pix_fmt") + 1] == "yuv420p"
    assert "-c:a" in argv
    assert argv[argv.index("-c:a") + 1] == "aac"


@pytest.mark.unit
@pytest.mark.req("REQ-F08-003")
def test_each_segment_has_scale_crop_to_1080x1920() -> None:
    segs = [_seg(0), _seg(1), _seg(2)]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    fc = argv[argv.index("-filter_complex") + 1]
    # Per segment: one scale and one crop to 1080x1920.
    assert fc.count("scale=1080:1920") == len(segs)
    assert fc.count("crop=1080:1920") == len(segs)


@pytest.mark.unit
@pytest.mark.req("REQ-F08-004")
def test_voiceover_replaces_video_audio_in_filter_graph() -> None:
    """Each segment's audio in the concat must come from the audio input, not from
    the video file's own audio."""
    segs = [_seg(0), _seg(1)]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    fc = argv[argv.index("-filter_complex") + 1]
    # Audio inputs are placed AFTER all video inputs: indexes N..2N-1.
    n = len(segs)
    for i in range(n):
        audio_idx = n + i
        # Concat must reference [a{i}] tags built from the audio inputs:
        assert f"[{audio_idx}:a]" in fc, f"audio input {audio_idx} must appear in filter graph"
    # And the concat label list ends with [aout]
    assert "[aout]" in fc


@pytest.mark.unit
@pytest.mark.req("REQ-F08-005")
def test_subtitle_drawtext_present_per_chunk() -> None:
    # "one two three four" → 2 chunks → 2 drawtext invocations for that segment.
    segs = [_seg(0, text="one two three four")]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    fc = argv[argv.index("-filter_complex") + 1]
    assert fc.count("drawtext=") == 2


@pytest.mark.unit
@pytest.mark.req("REQ-F08-005")
def test_subtitle_drawtext_skipped_for_empty_text() -> None:
    segs = [_seg(0, text="")]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    fc = argv[argv.index("-filter_complex") + 1]
    assert "drawtext=" not in fc


@pytest.mark.unit
@pytest.mark.req("REQ-F08-006")
def test_music_uri_is_added_with_low_volume_when_provided() -> None:
    segs = [_seg(0), _seg(1)]
    argv = build(segs, music_uri="https://example.com/m.mp3", output_path="/tmp/o.mp4")
    # Music input must appear as -i {music_uri}
    is_music = ["-i", "https://example.com/m.mp3"]
    assert any(argv[i:i + 2] == is_music for i in range(len(argv) - 1))
    fc = argv[argv.index("-filter_complex") + 1]
    assert "volume=0.01" in fc
    assert "amix" in fc


@pytest.mark.unit
@pytest.mark.req("REQ-F08-006")
def test_no_music_input_when_music_uri_is_none() -> None:
    segs = [_seg(0), _seg(1)]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    # Number of -i flags must equal exactly 2 * N (video+audio per segment).
    assert argv.count("-i") == 2 * len(segs)
    fc = argv[argv.index("-filter_complex") + 1]
    assert "amix" not in fc
    assert "volume=0.01" not in fc


@pytest.mark.unit
@pytest.mark.req("REQ-F08-002")
def test_inputs_appear_in_video_then_audio_order() -> None:
    """Convention assumed by audio-replacement test: all video inputs first, then all audio."""
    segs = [_seg(0), _seg(1), _seg(2)]
    argv = build(segs, music_uri=None, output_path="/tmp/o.mp4")
    # Collect every value following a -i flag.
    inputs = [argv[i + 1] for i, x in enumerate(argv) if x == "-i"]
    expected = [s.video_uri for s in segs] + [s.audio_uri for s in segs]
    assert inputs == expected
