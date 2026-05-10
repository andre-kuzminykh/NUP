"""F08 — /v1/renders endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from nup_pipeline.api.deps import get_assemble_service
from nup_pipeline.domain.render_job import RenderJob, RenderStatus
from nup_pipeline.domain.segment import Segment
from nup_pipeline.services.video_assembly import AssembleService

router = APIRouter(prefix="/v1/renders", tags=["renders"])


# ---- DTOs ------------------------------------------------------------------

class SegmentDTO(BaseModel):
    audio_uri: str
    video_uri: str
    audio_duration_sec: float = Field(gt=0.05)
    subtitle_text: str = ""

    def to_domain(self) -> Segment:
        return Segment(
            audio_uri=self.audio_uri,
            video_uri=self.video_uri,
            audio_duration_sec=self.audio_duration_sec,
            subtitle_text=self.subtitle_text,
        )


class RenderRequest(BaseModel):
    job_id: str | None = None
    segments: list[SegmentDTO] = Field(min_length=1)
    music_uri: str | None = None


class RenderJobDTO(BaseModel):
    job_id: str
    status: RenderStatus
    output_uri: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, j: RenderJob) -> "RenderJobDTO":
        return cls(
            job_id=j.id,
            status=j.status,
            output_uri=j.output_uri,
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            updated_at=j.updated_at.isoformat(),
        )


# ---- Endpoints --------------------------------------------------------------

@router.post(
    "",
    responses={
        202: {"description": "New job accepted"},
        200: {"description": "Already-succeeded job (idempotent)"},
        400: {"description": "Invalid input"},
    },
)
def submit_render(
    body: RenderRequest,
    response: Response,
    svc: Annotated[AssembleService, Depends(get_assemble_service)],
):
    if body.job_id is not None:
        try:
            uuid.UUID(body.job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="job_id must be a UUID") from e

    job = svc.submit(
        [s.to_domain() for s in body.segments],
        body.music_uri,
        job_id=body.job_id,
    )

    if job.status is RenderStatus.SUCCEEDED:
        # Idempotent: same job_id, already done.
        response.status_code = status.HTTP_200_OK
        return RenderJobDTO.from_domain(job)

    # Synchronous assemble for v0; in production this is enqueued to Celery.
    job = svc.assemble(job.id)
    response.status_code = (
        status.HTTP_202_ACCEPTED
        if job.status is not RenderStatus.SUCCEEDED
        else status.HTTP_202_ACCEPTED
    )
    return RenderJobDTO.from_domain(job)


@router.get("/{job_id}", response_model=RenderJobDTO)
def get_render(
    job_id: str,
    svc: Annotated[AssembleService, Depends(get_assemble_service)],
):
    job = svc.repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    return RenderJobDTO.from_domain(job)
