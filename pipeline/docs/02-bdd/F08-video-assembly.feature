# language: en
# Each Scenario tag references requirement IDs from docs/03-requirements/functional.md

Feature: F08 — Video Assembly
  As an orchestrator
  I want to submit a render job and get an MP4 URL
  So that downstream publication can post it to Telegram

  Background:
    Given the API is running and DB is migrated
    And MinIO bucket "nup-media" exists

  @REQ-F08-001 @REQ-F08-008
  Scenario: Submit a render job and observe lifecycle
    When I POST /v1/renders with 3 segments and no music
    Then the response status is 202
    And the response body contains a UUID job_id
    And GET /v1/renders/{job_id} eventually returns status "succeeded"
    And the response includes an output_uri pointing to "renders/{job_id}.mp4"

  @REQ-F08-011
  Scenario: FFmpeg builder is a pure function (no I/O)
    Given 2 segments with audio_uri/video_uri/subtitle_text and no music
    When I call FfmpegBuilder.build(segments, music_uri=None)
    Then the result is a list of strings
    And the first element is "ffmpeg"
    And no network or filesystem access happened

  @REQ-F08-002 @REQ-F08-003
  Scenario: Output is portrait 1080x1920 H.264 MP4 with center-cropped segments
    Given a render job with 1 horizontal 1920x1080 source clip
    When the job runs
    Then ffprobe of the output reports width=1080 and height=1920
    And the codec is "h264"
    And the duration is approximately equal to the segment audio duration

  @REQ-F08-004
  Scenario: Voiceover replaces the original video audio
    Given a render job whose source clip has loud original audio
    And a short silent voiceover audio
    When the job runs
    Then the audio track of the output equals the voiceover, not the original

  @REQ-F08-005 @REQ-F08-012
  Scenario Outline: Subtitle chunking by 3 words
    When subtitle text is "<text>"
    Then the chunks are <chunks>

    Examples:
      | text                          | chunks                                   |
      |                               | [""]                                     |
      | hello                         | ["hello"]                                |
      | one two three                 | ["one two three"]                        |
      | one two three four            | ["one two three", "four"]                |
      | a b c d e f g                 | ["a b c", "d e f", "g"]                  |

  @REQ-F08-006
  Scenario: Background music mixed at low volume when music_uri provided
    Given a render job with 2 segments and a music_uri
    When I inspect the built ffmpeg argv
    Then it contains an "-i {music_uri}" input
    And the filter graph mixes music at volume 0.01 across the full timeline

  @REQ-F08-007
  Scenario: Output is uploaded to deterministic key
    Given a successful render of job_id "abc-123"
    Then the S3 key is exactly "renders/abc-123.mp4"

  @REQ-F08-009
  Scenario: FFmpeg failure produces a failed job with error message
    Given the FfmpegRunner is mocked to raise FfmpegError("invalid input")
    When the assemble task runs
    Then the job status becomes "failed"
    And the job error_message contains "invalid input"

  @REQ-F08-010
  Scenario: Idempotent re-submission of a succeeded job
    Given a job_id that already has status "succeeded" and output_uri "renders/x.mp4"
    When I re-submit the same job_id
    Then the response is 200
    And the response body output_uri equals "renders/x.mp4"
    And no FFmpeg invocation happened
