"""F08 — real FFmpeg invocation with synthetic inputs.

Generates tiny audio + video via ffmpeg's lavfi, builds argv via FfmpegBuilder,
runs FfmpegRunner, ffprobes the output to verify dimensions and codec.

Traces: REQ-F08-002, REQ-F08-003, REQ-F08-004.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.ffmpeg import FfmpegRunner
from nup_pipeline.services.ffmpeg_builder import build

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def synth_inputs(tmp_path_factory) -> tuple[Path, Path]:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    d = tmp_path_factory.mktemp("synth")
    video = d / "v.mp4"
    audio = d / "a.mp3"
    # 2 sec horizontal 1280x720 colored bars, with silent audio (which we'll override).
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "smptebars=duration=2:size=1280x720:rate=25",
            "-f", "lavfi", "-i", "anullsrc=cl=stereo:r=44100",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-t", "2",
            str(video),
        ],
        check=True, capture_output=True,
    )
    # 2 sec sine-wave tone @440Hz as voiceover.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:a", "libmp3lame",
            str(audio),
        ],
        check=True, capture_output=True,
    )
    return video, audio


def _ffprobe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(path),
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


@pytest.mark.req("REQ-F08-002")
@pytest.mark.req("REQ-F08-003")
def test_render_output_is_1080x1920_h264(synth_inputs, tmp_path) -> None:
    video, audio = synth_inputs
    seg = Segment(
        audio_uri=str(audio),
        video_uri=str(video),
        audio_duration_sec=2.0,
        subtitle_text="hello world",
    )
    out = tmp_path / "out.mp4"
    argv = build([seg], music_uri=None, output_path=str(out))
    FfmpegRunner().run(argv, output_path=str(out), timeout=60)

    info = _ffprobe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert v["width"] == 1080
    assert v["height"] == 1920
    assert v["codec_name"] == "h264"
    # duration approximately 2 sec
    duration = float(info["format"]["duration"])
    assert 1.8 <= duration <= 2.4
