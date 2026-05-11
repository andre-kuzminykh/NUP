"""F08 — orchestrating service: takes segments, runs ffmpeg, uploads to S3.

Idempotent: re-submitting a succeeded job_id returns the existing output_uri
without re-rendering (REQ-F08-010).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from nup_pipeline.domain.render_job import (
    IllegalStateError,
    RenderJob,
    RenderStatus,
)
from nup_pipeline.domain.segment import Segment
from nup_pipeline.infra.ffmpeg import FfmpegError
from nup_pipeline.services.ffmpeg_builder import build

log = logging.getLogger(__name__)


class RenderJobRepo(Protocol):
    def get(self, job_id: str) -> RenderJob | None: ...
    def save(self, job: RenderJob) -> None: ...


class Runner(Protocol):
    def run(self, argv: list[str], output_path: str, timeout: float) -> str: ...


class Storage(Protocol):
    def upload(self, key: str, local_path: str) -> str: ...


class AssembleService:
    def __init__(
        self,
        repo: RenderJobRepo,
        runner: Runner,
        storage: Storage,
        *,
        work_dir: str = "/tmp",
        timeout: float = 180.0,
    ) -> None:
        self.repo = repo
        self.runner = runner
        self.storage = storage
        self.work_dir = Path(work_dir)
        self.timeout = timeout

    # --- API ---------------------------------------------------------------

    def submit(
        self,
        segments: list[Segment],
        music_uri: str | None,
        *,
        job_id: str | None = None,
    ) -> RenderJob:
        """Create a new pending job — or return existing one (idempotency)."""
        if job_id:
            existing = self.repo.get(job_id)
            if existing is not None:
                return existing
        job = RenderJob.new(segments=segments, music_uri=music_uri, job_id=job_id)
        self.repo.save(job)
        return job

    def assemble(self, job_id: str) -> RenderJob:
        """Run ffmpeg + upload. Idempotent on succeeded jobs."""
        job = self.repo.get(job_id)
        if job is None:
            raise KeyError(f"render job {job_id} not found")

        if job.status is RenderStatus.SUCCEEDED:
            return job  # idempotent — REQ-F08-010
        if job.status not in (RenderStatus.PENDING,):
            # Already running or failed: don't restart implicitly.
            return job

        try:
            job.transition(RenderStatus.RUNNING)
            self.repo.save(job)
        except IllegalStateError:
            return job

        local_out = str(self.work_dir / f"{job.id}.mp4")
        argv = build(job.segments, job.music_uri, output_path=local_out)
        try:
            self.runner.run(argv, output_path=local_out, timeout=self.timeout)
            uri = self.storage.upload(f"renders/{job.id}.mp4", local_out)
            job.output_uri = uri
            job.transition(RenderStatus.SUCCEEDED)
            self.repo.save(job)
            log.info("render succeeded", extra={"job_id": job.id, "uri": uri})
        except FfmpegError as e:
            job.error_message = str(e)
            job.transition(RenderStatus.FAILED)
            self.repo.save(job)
            log.warning("render failed", extra={"job_id": job.id, "err": str(e)})
        return job
