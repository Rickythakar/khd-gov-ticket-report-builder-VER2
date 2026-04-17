Feature: Phase 9 AI-Powered Analysis
  Scenario: AI dependencies and routes are available
    Given the Phase 9 AI integration is implemented
    When I inspect the runtime contract
    Then the Azure OpenAI dependency is declared
    And the AI routes expose run, status, results, summary, and clear actions

  Scenario: AI surfaces stay internal-only
    Given AI is enabled in settings
    When I render the dashboard in customer mode
    Then the AI assist entrypoint is hidden
    When I render the dashboard in internal mode
    Then the AI assist entrypoint is visible

  Scenario: AI analysis stays aligned with the active dataset
    Given cached AI results exist for a prior run
    When the active dataset is cleared or replaced
    Then the stale AI cache is dropped

  Scenario: Exports carry AI output
    Given cached AI results exist for the active internal dataset
    When I build the workbook export
    Then the summary sheet includes an AI-generated executive summary
    And the ticket export includes an AI sentiment column
    When I build the PDF export
    Then the PDF builder receives the cached AI payload
