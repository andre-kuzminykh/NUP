"""F08 — AssembleService orchestration tests.

Traces: REQ-F08-007, REQ-F08-009, REQ-F08-010.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from nup_pipeline.domain.render_job import RenderStatus
from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.ffmpeg import FfmpegError
from nup_pipeline.services.video_assembly import AssembleService


# --- doubles ----------------------------------------------------------------

class FakeRunner:
    def __init__(self, raise_with: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.raise_with = raise_with

    def run(self, argv: list[str], output_path: str, timeout: float) -> str:
        self.calls.append(argv)
        if self.raise_with:
            raise self.raise_with
        # Pretend ffmpeg wrote the file.
        Path(output_path).write_bytes(b"\x00fake mp4")
        return output_path


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, str] = {}  # key -> uri

    def upload(self, key: str, local_path: str) -> str:
        self.uploaded[key] = f"s3://nup-media/{key}"
        return self.uploaded[key]


class InMemoryRepo:
    def __init__(self) -> None:
        self.jobs: dict[str, object] = {}

    def get(self, job_id: str):
        return self.jobs.get(job_id)

    def save(self, job) -> None:
        self.jobs[job.id] = job


def _segments() -> list[Segment]:
    return [
        Segment(
            audio_uri="https://x/a0.mp3",
            video_uri="https://x/v0.mp4",
            audio_duration_sec=2.0,
            subtitle_text="hello world here",
        ),
        Segment(
            audio_uri="https://x/a1.mp3",
            video_uri="https://x/v1.mp4",
            audio_duration_sec=2.0,
            subtitle_text="another segment text",
        ),
    ]


# --- tests ------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.req("REQ-F08-007")
def test_uploads_to_deterministic_key(tmp_path) -> None:
    repo, runner, storage = InMemoryRepo(), FakeRunner(), FakeStorage()
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    job = svc.submit(_segments(), music_uri=None)
    svc.assemble(job.id)
    assert f"renders/{job.id}.mp4" in storage.uploaded
    assert storage.uploaded[f"renders/{job.id}.mp4"].endswith(f"renders/{job.id}.mp4")


@pytest.mark.unit
@pytest.mark.req("REQ-F08-009")
def test_ffmpeg_failure_marks_job_failed_with_message(tmp_path) -> None:
    repo, runner, storage = (
        InMemoryRepo(),
        FakeRunner(raise_with=FfmpegError("invalid input")),
        FakeStorage(),
    )
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    job = svc.submit(_segments(), music_uri=None)
    svc.assemble(job.id)
    stored = repo.get(job.id)
    assert stored.status is RenderStatus.FAILED
    assert "invalid input" in (stored.error_message or "")
    assert storage.uploaded == {}  # nothing uploaded


@pytest.mark.unit
@pytest.mark.req("REQ-F08-010")
def test_idempotent_resubmit_skips_ffmpeg(tmp_path) -> None:
    repo, runner, storage = InMemoryRepo(), FakeRunner(), FakeStorage()
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    job = svc.submit(_segments(), music_uri=None)
    svc.assemble(job.id)
    first_uri = repo.get(job.id).output_uri
    assert len(runner.calls) == 1

    # Re-submit with same job_id (manually constructed UUID, replaying).
    again = svc.submit(_segments(), music_uri=None, job_id=job.id)
    assert again.status is RenderStatus.SUCCEEDED
    assert again.output_uri == first_uri
    # Run again — must early-return without invoking ffmpeg.
    svc.assemble(job.id)
    assert len(runner.calls) == 1, "ffmpeg must not be re-invoked on succeeded idempotent job"


@pytest.mark.unit
@pytest.mark.req("REQ-F08-001")
def test_submit_without_job_id_generates_uuid(tmp_path) -> None:
    repo, runner, storage = InMemoryRepo(), FakeRunner(), FakeStorage()
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    job = svc.submit(_segments(), music_uri=None)
    # UUID parses
    uuid.UUID(job.id)
    assert job.status is RenderStatus.PENDING


@pytest.mark.unit
@pytest.mark.req("REQ-F08-001")
def test_submit_with_explicit_job_id_uses_it(tmp_path) -> None:
    repo, runner, storage = InMemoryRepo(), FakeRunner(), FakeStorage()
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    fixed = "11111111-2222-3333-4444-555555555555"
    job = svc.submit(_segments(), music_uri=None, job_id=fixed)
    assert job.id == fixed
