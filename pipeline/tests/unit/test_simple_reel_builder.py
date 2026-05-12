"""F008 smoke variant — builder for the colored-bg single-source Reel."""
import pytest

from nup_pipeline.services.simple_reel_builder import build_simple_reel_ffmpeg


@pytest.mark.unit
def test_argv_has_color_bg_and_audio_inputs() -> None:
    argv = build_simple_reel_ffmpeg(
        audio_path="/tmp/voice.mp3",
        duration_sec=30.0,
        title="OpenAI выпустила GPT-5",
        chunks=["один два три", "четыре пять"],
        output_path="/tmp/reel.mp4",
    )
    assert argv[0] == "ffmpeg"
    assert argv[-1] == "/tmp/reel.mp4"
    # color input
    assert "-f" in argv and "lavfi" in argv
    # audio input
    assert "/tmp/voice.mp3" in argv
    # output is 1080x1920
    vf = argv[argv.index("-vf") + 1]
    assert "GPT-5" in vf or "GPT" in vf   # title escaped/present
    # both subtitle chunks present (after escape)
    assert "один" in vf
    assert "четыре" in vf


@pytest.mark.unit
def test_empty_chunks_yields_null_vf() -> None:
    """Если ни title, ни subtitles нет — vf=null (no-op), ffmpeg валиден."""
    argv = build_simple_reel_ffmpeg(
        audio_path="/tmp/v.mp3",
        duration_sec=5.0,
        title="",
        chunks=[""],
        output_path="/tmp/o.mp4",
    )
    vf = argv[argv.index("-vf") + 1]
    assert vf == "null"


@pytest.mark.unit
def test_subtitle_time_windows_partition_duration() -> None:
    """3 chunks × duration=30 ⇒ окна 0-10, 10-20, 20-30."""
    argv = build_simple_reel_ffmpeg(
        audio_path="/tmp/v.mp3",
        duration_sec=30.0,
        title="",
        chunks=["a", "b", "c"],
        output_path="/tmp/o.mp4",
    )
    vf = argv[argv.index("-vf") + 1]
    assert "between(t,0.000,10.000)" in vf
    assert "between(t,10.000,20.000)" in vf
    assert "between(t,20.000,30.000)" in vf
