"""F011 — ReviewSubmitter.

Traces: REQ-F011-001, REQ-F011-002, REQ-F011-004, REQ-F011-005, REQ-F011-006.
"""
import pytest

from nup_pipeline.domain.render_job import RenderJob, RenderStatus
from nup_pipeline.domain.review import IllegalReviewStateError, ReviewStatus
from nup_pipeline.services.review_submission import ReviewSubmitter


class InMemRenderJobRepo:
    def __init__(self) -> None:
        self.jobs: dict[str, RenderJob] = {}

    def get(self, job_id: str) -> RenderJob | None:
        return self.jobs.get(job_id)


class InMemReviewRepo:
    def __init__(self) -> None:
        self.rows: dict[str, object] = {}
        self.by_render: dict[str, str] = {}

    def get_by_render_job(self, render_job_id: str):
        rid = self.by_render.get(render_job_id)
        return self.rows.get(rid) if rid else None

    def save(self, r) -> None:
        self.rows[r.id] = r
        self.by_render[r.render_job_id] = r.id


class FakeTelegram:
    def __init__(self, message_id: int = 555) -> None:
        self.calls: list[dict] = []
        self._next = message_id - 1

    def send_video(self, chat_id, video, *, caption=None, reply_markup=None) -> int:
        self._next += 1
        self.calls.append(
            {
                "chat_id": chat_id,
                "video": video,
                "caption": caption,
                "reply_markup": reply_markup,
            }
        )
        return self._next


def _succeeded_job(job_id: str = "job-1") -> RenderJob:
    job = RenderJob.new(segments=[], music_uri=None, job_id=job_id, status=RenderStatus.RUNNING)
    job.output_uri = "s3://nup-media/renders/abc.mp4"
    job.transition(RenderStatus.SUCCEEDED)
    return job


def _bundle(
    job_status: RenderStatus = RenderStatus.SUCCEEDED,
    title_ru: str = "Заголовок",
    content_ru: str = "Тело новости.",
    title_en: str = "Headline",
    content_en: str = "News body.",
    link: str | None = None,
) -> dict:
    return {
        "title_ru": title_ru,
        "content_ru": content_ru,
        "title_en": title_en,
        "content_en": content_en,
        "link": link,
    }


@pytest.mark.unit
@pytest.mark.req("REQ-F011-001")
@pytest.mark.req("REQ-F011-005")
def test_submit_persists_pending_review_and_sends_video() -> None:
    rjrepo = InMemRenderJobRepo()
    rjrepo.jobs["job-1"] = _succeeded_job("job-1")
    rrepo = InMemReviewRepo()
    tg = FakeTelegram(message_id=777)
    submitter = ReviewSubmitter(render_job_repo=rjrepo, review_repo=rrepo, telegram=tg)

    rs = submitter.submit(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1003924811323,
        caption_bundle=_bundle(),
    )
    assert rs.status is ReviewStatus.PENDING_REVIEW
    assert rs.message_id == 777
    assert rrepo.rows[rs.id] is rs
    assert len(tg.calls) == 1
    call = tg.calls[0]
    assert call["chat_id"] == 42
    assert call["video"] == "s3://nup-media/renders/abc.mp4"
    assert call["reply_markup"] is not None


@pytest.mark.unit
@pytest.mark.req("REQ-F011-004")
def test_reply_markup_has_three_callbacks_with_review_id() -> None:
    rjrepo = InMemRenderJobRepo()
    rjrepo.jobs["job-1"] = _succeeded_job("job-1")
    rrepo = InMemReviewRepo()
    tg = FakeTelegram()
    submitter = ReviewSubmitter(render_job_repo=rjrepo, review_repo=rrepo, telegram=tg)

    rs = submitter.submit(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1,
        caption_bundle=_bundle(),
    )
    markup = tg.calls[0]["reply_markup"]
    # Format: {"inline_keyboard": [[ {text, callback_data}, ... ]]}
    rows = markup["inline_keyboard"]
    flat = [btn for row in rows for btn in row]
    assert len(flat) == 3
    callbacks = sorted(btn["callback_data"] for btn in flat)
    assert callbacks == sorted(
        [f"review:approve:{rs.id}", f"review:decline:{rs.id}", f"review:edit:{rs.id}"]
    )
    # Each label must be bilingual (RU + EN), e.g. contain a slash separator.
    for btn in flat:
        assert "/" in btn["text"]


@pytest.mark.unit
@pytest.mark.req("REQ-F011-003")
def test_caption_is_bilingual() -> None:
    rjrepo = InMemRenderJobRepo()
    rjrepo.jobs["job-1"] = _succeeded_job("job-1")
    rrepo = InMemReviewRepo()
    tg = FakeTelegram()
    submitter = ReviewSubmitter(render_job_repo=rjrepo, review_repo=rrepo, telegram=tg)
    submitter.submit(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1,
        caption_bundle=_bundle(
            title_ru="Hi", content_ru="ru_body", title_en="Hello", content_en="en_body"
        ),
    )
    caption = tg.calls[0]["caption"]
    assert "ru_body" in caption
    assert "en_body" in caption
    assert caption.index("ru_body") < caption.index("en_body")


@pytest.mark.unit
@pytest.mark.req("REQ-F011-002")
def test_submit_fails_if_render_is_not_succeeded() -> None:
    rjrepo = InMemRenderJobRepo()
    rjrepo.jobs["job-1"] = RenderJob.new(segments=[], music_uri=None, job_id="job-1")
    rrepo = InMemReviewRepo()
    tg = FakeTelegram()
    submitter = ReviewSubmitter(render_job_repo=rjrepo, review_repo=rrepo, telegram=tg)
    with pytest.raises(IllegalReviewStateError):
        submitter.submit(
            render_job_id="job-1",
            reviewer_chat_id=42,
            channel_id=-1,
            caption_bundle=_bundle(),
        )
    assert tg.calls == []


@pytest.mark.unit
@pytest.mark.req("REQ-F011-006")
def test_resubmit_for_same_render_returns_existing() -> None:
    rjrepo = InMemRenderJobRepo()
    rjrepo.jobs["job-1"] = _succeeded_job("job-1")
    rrepo = InMemReviewRepo()
    tg = FakeTelegram()
    submitter = ReviewSubmitter(render_job_repo=rjrepo, review_repo=rrepo, telegram=tg)
    first = submitter.submit(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1,
        caption_bundle=_bundle(),
    )
    second = submitter.submit(
        render_job_id="job-1",
        reviewer_chat_id=42,
        channel_id=-1,
        caption_bundle=_bundle(),
    )
    assert first.id == second.id
    assert len(tg.calls) == 1   # no second send_video
