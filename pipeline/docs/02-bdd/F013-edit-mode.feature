# language: en
Feature: F013 — Reels Edit Mode (Frame-by-frame)
  Status: contract-only in this iteration (skeleton + unit contract tests).

  Background:
    Given a ReviewSession R with status "pending_review" and 3 segments

  @REQ-F013-001
  Scenario: Starting edit mode initializes cursor at 0
    When ReviewEditor.start(R.id) is called
    Then R.status becomes "in_edit"
    And the response payload contains cursor=0, total=3, segment_text of segment[0]

  @REQ-F013-002
  Scenario Outline: Move clamps cursor at edges
    Given R.status is "in_edit" and cursor is <from>
    When ReviewEditor.move(R.id, "<direction>") is called
    Then cursor becomes <to>

    Examples:
      | from | direction | to |
      | 0    | prev      | 0  |
      | 0    | next      | 1  |
      | 2    | next      | 2  |
      | 1    | prev      | 0  |

  @REQ-F013-006
  Scenario: Cancel restores pending_review and clears edit_state
    Given R.status is "in_edit"
    When ReviewEditor.cancel(R.id) is called
    Then R.status becomes "pending_review"
    And R.edit_state is null

  @REQ-F013-007
  Scenario: Response payload shape (contract)
    When any ReviewEditor call returns
    Then the payload contains: cursor, total, segment_text, active_candidate, candidates
