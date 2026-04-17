Feature: Phase 1 foundation improvements
  As Ricky
  I want the report builder flow to be single-pass and safe
  So the workbook and PDF exports do not require recovery clicks or trust raw CSV HTML

  Scenario: Uploading a CSV triggers analysis immediately
    Given a valid ticket export CSV
    When I upload the CSV
    Then the dashboard analysis is ready without clicking Analyze Workbook

  Scenario: The export workflow has one primary action
    Given the app is open
    When I look at the primary controls
    Then I see a single Export action instead of separate Analyze and Generate buttons

  Scenario: Enabling the executive PDF snapshot does not require a second click
    Given a valid ticket export CSV has already been analyzed
    When I enable the executive PDF snapshot option
    Then the PDF snapshot bytes are already cached in session state
    And the executive PDF download is ready on that same flow

  Scenario: CSV-derived strings are escaped before HTML rendering
    Given a title, partner name, date range, or observation contains HTML
    When the app renders hero and status bands
    Then the rendered markup contains escaped values instead of raw HTML
