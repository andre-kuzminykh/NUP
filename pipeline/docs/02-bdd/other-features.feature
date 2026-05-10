Feature: F02–F07, F09, F10 — sketches (full BDD in their own iterations)

  @REQ-F02-002
  Scenario: Summary starts with bold headline
    When the summarizer produces text for an article
    Then the first line matches "*…*" and the second line is empty

  @REQ-F03-001
  Scenario: ≥60s spacing between text publications to same channel
    Given two consecutive publish requests to channel C
    Then the second one waits at least 60 seconds before sending

  @REQ-F04-002
  Scenario: Voiceover length is between 80 and 180 words
    When voiceover is generated
    Then word count is in [80, 180]

  @REQ-F05-001
  Scenario: Segments JSON validates against schema
    When segmenter returns text
    Then it parses as JSON and validates against segments-schema.json

  @REQ-F06-002 @REQ-F06-003
  Scenario: TTS uploads MP3 and saves duration
    When TTS for segment S of reels R completes
    Then S3 contains object "tts/{R}/{S}.mp3"
    And segment row has audio_duration_sec > 0

  @REQ-F07-003
  Scenario: Picker never repeats clip across one Reels
    When 3 segments are picked for the same reels
    Then all selected video_uri values are distinct

  @REQ-F09-003
  Scenario: After successful publication DB row holds video_url, title, caption
    When reels publication finishes
    Then DB columns video_url, title_video_ru, caption_video_ru are non-empty

  @REQ-F10-002
  Scenario: Event bus delivers at least once
    Given a handler crashes once on event "article.summarized"
    Then the event is redelivered and processed
