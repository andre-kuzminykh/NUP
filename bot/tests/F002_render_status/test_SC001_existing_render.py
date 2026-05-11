"""
Тест SC001 — известный render возвращает status и output_uri.

## Трассируемость
Feature: F002 — Render job status
Scenario: SC001 — Existing render

## BDD
Given: backend имеет render с id=UUID_OK, status=succeeded, output_uri=Y
When:  пользователь отправил `/render_status UUID_OK`
Then:  бот ответил один раз сообщением, содержащим 'succeeded' и Y
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from handler.v1.user.renders.F002.render_status_widget import handle_render_status
from tests.F002_render_status.conftest import UUID_OK


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_id, status, output_uri",
    [
        (UUID_OK, "succeeded", "s3://nup-media/renders/x.mp4"),
    ],
    ids=["succeeded_with_uri"],
)
async def test_returns_status_for_known_job(
    make_message, mock_state, fake_api_factory, job_id, status, output_uri
) -> None:
    # Given
    msg = make_message(f"/render_status {job_id}")
    fake_api = fake_api_factory(
        get_return={"job_id": job_id, "status": status, "output_uri": output_uri}
    )

    # When
    with patch(
        "node.renders.code.render_status_code.RendersAPI",
        return_value=fake_api,
    ):
        await handle_render_status(msg, mock_state)

    # Then
    fake_api.get.assert_awaited_once_with(job_id)
    msg.answer.assert_awaited_once()
    sent_text = msg.answer.call_args.args[0]
    assert status in sent_text
    assert output_uri in sent_text
