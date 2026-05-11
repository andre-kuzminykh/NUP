"""F08 — full HTTP round-trip via FastAPI TestClient.

Uses InMemoryRepo + FakeRunner + FakeStorage by overriding FastAPI deps,
so neither ffmpeg nor MinIO are required.

Traces: REQ-F08-001, REQ-F08-008, REQ-F08-010.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nup_pipeline.api.app import build_app
from nup_pipeline.api.deps import get_assemble_service
from nup_pipeline.services.video_assembly import AssembleService

# Reuse the same doubles from the unit test module.
from tests.unit.test_video_assembly_service import FakeRunner, FakeStorage, InMemoryRepo


@pytest.fixture
def app(tmp_path):
    repo, runner, storage = InMemoryRepo(), FakeRunner(), FakeStorage()
    svc = AssembleService(repo=repo, runner=runner, storage=storage, work_dir=str(tmp_path))
    app = build_app()
    app.dependency_overrides[get_assemble_service] = lambda: svc
    app.state._test_repo = repo
    app.state._test_runner = runner
    app.state._test_storage = storage
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _payload(music_uri=None, job_id=None):
    body = {
        "segments": [
            {
                "audio_uri": "https://x/a0.mp3",
                "video_uri": "https://x/v0.mp4",
                "audio_duration_sec": 2.0,
                "subtitle_text": "hello world here",
            },
            {
                "audio_uri": "https://x/a1.mp3",
                "video_uri": "https://x/v1.mp4",
                "audio_duration_sec": 2.5,
                "subtitle_text": "another segment text follows",
            },
        ],
    }
    if music_uri:
        body["music_uri"] = music_uri
    if job_id:
        body["job_id"] = job_id
    return body


@pytest.mark.e2e
@pytest.mark.req("REQ-F08-001")
def test_post_render_returns_202_and_uuid(client) -> None:
    r = client.post("/v1/renders", json=_payload())
    assert r.status_code == 202, r.text
    body = r.json()
    uuid.UUID(body["job_id"])
    assert body["status"] in ("pending", "succeeded")  # may already be done synchronously


@pytest.mark.e2e
@pytest.mark.req("REQ-F08-001")
@pytest.mark.req("REQ-F08-008")
def test_full_render_round_trip(client) -> None:
    r = client.post("/v1/renders", json=_payload())
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    g = client.get(f"/v1/renders/{job_id}")
    assert g.status_code == 200
    body = g.json()
    assert body["status"] == "succeeded"
    assert body["output_uri"].endswith(f"renders/{job_id}.mp4")


@pytest.mark.e2e
@pytest.mark.req("REQ-F08-010")
def test_idempotent_post_returns_200_with_existing_uri(client, app) -> None:
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    r1 = client.post("/v1/renders", json=_payload(job_id=job_id))
    assert r1.status_code == 202
    runner: FakeRunner = app.state._test_runner
    calls_after_first = len(runner.calls)
    assert calls_after_first == 1

    r2 = client.post("/v1/renders", json=_payload(job_id=job_id))
    assert r2.status_code == 200, r2.text
    assert r2.json()["output_uri"] == r1.json()["output_uri"]
    assert len(runner.calls) == calls_after_first  # no extra ffmpeg invocation


@pytest.mark.e2e
def test_get_unknown_job_returns_404(client) -> None:
    r = client.get(f"/v1/renders/{uuid.uuid4()}")
    assert r.status_code == 404
