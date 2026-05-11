# language: en
Feature: F011 — Reels Review Submission
  As an operator
  I want to receive every generated Reels in my private chat for approval
  So that I can catch off-topic or broken videos before they go public

  Background:
    Given a render job that has succeeded with output_uri "s3://nup-media/renders/abc.mp4"
    And the operator chat id is 42
    And the channel id is -1003924811323

  @REQ-F011-001 @REQ-F011-005
  Scenario: Submit creates a pending review and sends video to operator
    When ReviewSubmitter.submit(render_job_id, reviewer_chat_id=42, channel_id=-1003924811323) is called
    Then a ReviewSession is persisted with status="pending_review" and message_id set
    And the Telegram client received send_video(chat_id=42, video=output_uri, reply_markup=keyboard) exactly once

  @REQ-F011-004
  Scenario: Inline keyboard has three callbacks
    When ReviewSubmitter.submit(...) is called
    Then the reply_markup contains three buttons with callback_data:
      | review:approve:{id}  |
      | review:decline:{id}  |
      | review:edit:{id}     |

  @REQ-F011-003
  Scenario: Caption is bilingual RU then EN
    Given the article summary has title_ru, content_ru, title_en, content_en
    When ReviewSubmitter.submit(...) is called
    Then the caption sent to operator starts with title_ru in bold
    And the caption contains a separator and the EN block after the RU block

  @REQ-F011-002
  Scenario: Submit refuses when render is not succeeded
    Given the render job has status "failed"
    When ReviewSubmitter.submit(...) is called
    Then IllegalReviewStateError is raised
    And no Telegram message is sent

  @REQ-F011-006
  Scenario: Re-submit for same render job is idempotent
    Given a ReviewSession already exists for render_job_id X
    When ReviewSubmitter.submit(X, ...) is called again
    Then the existing session is returned
    And no new Telegram message is sent
