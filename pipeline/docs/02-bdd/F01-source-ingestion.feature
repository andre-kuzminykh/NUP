Feature: F01 — Source Ingestion (sketch — code in next iteration)

  @REQ-F01-003 @NFR-CC1-S01
  Scenario: All source HTTP requests go through proxy pool
    Given PROXY_POOL is non-empty
    When the ingestion task fetches any source URL
    Then the outbound request uses one of the configured proxies

  @REQ-F01-004 @NFR-CC1-S03
  Scenario: A failing proxy is cooled down after 3 consecutive failures
    Given proxy P1 returns HTTP 429 three times in a row
    Then P1 is marked unhealthy for 10 minutes
    And the next attempt picks a different proxy

  @REQ-F01-006
  Scenario: Articles are deduplicated by canonical link
    Given an article with link "https://Example.com/a?utm_source=foo#x" was ingested
    When the same source returns "https://example.com/a"
    Then the second occurrence is dropped without inserting a row

  @REQ-F01-001
  Scenario Outline: Adapter returns a normalized Article for each source kind
    Given a source of kind "<kind>" with a fixture payload
    When the adapter parses it
    Then the result has fields link, title, source_id, raw_content

    Examples:
      | kind              |
      | rss               |
      | html              |
      | youtube_channel   |
      | linkedin_profile  |
      | x_profile         |
      | telegram_channel  |
