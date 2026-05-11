# language: en
Feature: F012 — Review Decision (Approve / Decline)

  Background:
    Given a ReviewSession R with status "pending_review" linked to render_job J
    And J has output_uri "s3://.../abc.mp4"

  @REQ-F012-001 @REQ-F012-005 @REQ-F012-006
  Scenario: Approve publishes to channel and updates state
    When ReviewDecider.approve(R.id) is called
    Then R.status becomes "approved"
    And VideoPublisher.publish is called with chat_id equal to R.channel_id and the same bilingual caption
    And a Publication row is persisted with kind="video", message_id set

  @REQ-F012-002
  Scenario: Decline marks declined without publishing
    When ReviewDecider.decline(R.id) is called
    Then R.status becomes "declined"
    And VideoPublisher.publish is NOT called

  @REQ-F012-003
  Scenario: Approve is idempotent
    Given R.status is already "approved" with publication_message_id M
    When ReviewDecider.approve(R.id) is called again
    Then the response references the same Publication M
    And VideoPublisher.publish is NOT called

  @REQ-F012-007
  Scenario Outline: Illegal transitions are rejected
    Given R.status is "<from>"
    When ReviewDecider.<action>(R.id) is called
    Then IllegalReviewStateError is raised

    Examples:
      | from         | action      |
      | declined     | approve     |
      | approved     | decline     |
      | declined     | start_edit  |
      | approved     | start_edit  |
      | in_edit      | approve     |
