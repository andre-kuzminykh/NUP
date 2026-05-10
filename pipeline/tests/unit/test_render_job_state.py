"""F08 — RenderJob state machine.

Traces: REQ-F08-008.
"""
import pytest

from nup_pipeline.domain.render_job import (
    IllegalStateError,
    RenderJob,
    RenderStatus,
)


def _job(status: RenderStatus = RenderStatus.PENDING) -> RenderJob:
    return RenderJob.new(segments=[], music_uri=None, status=status)


@pytest.mark.unit
@pytest.mark.req("REQ-F08-008")
@pytest.mark.parametrize(
    "src, dst",
    [
        (RenderStatus.PENDING, RenderStatus.RUNNING),
        (RenderStatus.RUNNING, RenderStatus.SUCCEEDED),
        (RenderStatus.RUNNING, RenderStatus.FAILED),
    ],
)
def test_legal_transitions(src: RenderStatus, dst: RenderStatus) -> None:
    job = _job(src)
    job.transition(dst)
    assert job.status is dst


@pytest.mark.unit
@pytest.mark.req("REQ-F08-008")
@pytest.mark.parametrize(
    "src, dst",
    [
        (RenderStatus.PENDING, RenderStatus.SUCCEEDED),
        (RenderStatus.PENDING, RenderStatus.FAILED),
        (RenderStatus.SUCCEEDED, RenderStatus.RUNNING),
        (RenderStatus.SUCCEEDED, RenderStatus.PENDING),
        (RenderStatus.FAILED, RenderStatus.RUNNING),
        (RenderStatus.FAILED, RenderStatus.SUCCEEDED),
    ],
)
def test_illegal_transitions_raise(src: RenderStatus, dst: RenderStatus) -> None:
    job = _job(src)
    with pytest.raises(IllegalStateError):
        job.transition(dst)
