"""Persistent ReviewSession storage (SQLite for unit; Postgres in prod)."""
import os
import tempfile

import pytest

from nup_pipeline.domain.review import ReviewSession, ReviewStatus
from nup_pipeline.infra.review_repo_pg import PostgresReviewRepo


@pytest.fixture
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield PostgresReviewRepo(f"sqlite:///{path}")
    os.unlink(path)


@pytest.mark.unit
def test_save_and_get_round_trip(repo) -> None:
    s = ReviewSession.new(render_job_id="job-1", reviewer_chat_id=42, channel_id=-100)
    s.output_uri = "s3://x/y.mp4"
    s.caption = "*hello*"
    s.segments_snapshot = [
        {"text": "first", "candidates": [{"video_url": "a.mp4"}, {"video_url": "b.mp4"}], "active_idx": 0},
    ]
    s.edit_state = {"cursor": 1}
    repo.save(s)

    fetched = repo.get(s.id)
    assert fetched is not None
    assert fetched.render_job_id == "job-1"
    assert fetched.status is ReviewStatus.PENDING_REVIEW
    assert fetched.output_uri == "s3://x/y.mp4"
    assert fetched.segments_snapshot[0]["text"] == "first"
    assert fetched.edit_state == {"cursor": 1}


@pytest.mark.unit
def test_save_is_upsert(repo) -> None:
    s = ReviewSession.new(render_job_id="job-1", reviewer_chat_id=42, channel_id=-100)
    repo.save(s)
    s.transition(ReviewStatus.APPROVED)
    s.publication_message_id = 9999
    repo.save(s)
    again = repo.get(s.id)
    assert again.status is ReviewStatus.APPROVED
    assert again.publication_message_id == 9999


@pytest.mark.unit
def test_get_by_render_job(repo) -> None:
    s = ReviewSession.new(render_job_id="job-X", reviewer_chat_id=42, channel_id=-100)
    repo.save(s)
    assert repo.get_by_render_job("job-X").id == s.id
    assert repo.get_by_render_job("nope") is None


@pytest.mark.unit
def test_get_unknown_returns_none(repo) -> None:
    assert repo.get("nope") is None
