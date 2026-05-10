"""FFmpeg subprocess runner.

Builder is pure (services/ffmpeg_builder.py); this module is the only place
that actually invokes the binary.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class FfmpegError(RuntimeError):
    """Wraps a non-zero exit (or timeout) from ffmpeg with stderr tail."""


class FfmpegRunner:
    """Thin subprocess.run wrapper.

    Kept tiny so unit tests can replace it with a fake.
    """

    def run(self, argv: list[str], output_path: str, timeout: float = 180.0) -> str:
        log.info("ffmpeg invoke", extra={"argv_head": argv[:10], "output": output_path})
        try:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise FfmpegError(f"ffmpeg timed out after {timeout}s") from exc
        if proc.returncode != 0:
            tail = (proc.stderr or "")[-2000:]
            raise FfmpegError(f"ffmpeg exited with {proc.returncode}: {tail}")
        if not Path(output_path).exists():
            raise FfmpegError(f"ffmpeg succeeded but output {output_path} is missing")
        return output_path
