Feature: Phase 6 export extensions
  As Ricky
  I want the live export layer to ship richer Excel and PDF deliverables
  So the polished Phase 5 dashboard exports SLA and resolution insights instead of only the old summary pack

  Scenario: Internal builder still preserves the hidden technician review sheet
    Given the internal Excel builder
    When I build a workbook directly
    Then the hidden Technician Review sheet is still present

  Scenario: Customer workbook adds the SLA compliance sheet
    Given the customer Excel builder
    When I build a Phase 6 workbook
    Then the workbook includes a visible SLA Compliance sheet
    And the SLA sheet contains targets, compliance, and breach detail sections

  Scenario: Live internal workbook export uses the active mode and settings
    Given the FastAPI server is primed with internal-mode report state
    When I request the workbook export endpoint
    Then the generated workbook includes the hidden Technician Review sheet
    And the generated workbook includes the SLA Compliance sheet

  Scenario: Internal PDF keeps the diagnostics page
    Given an internal Phase 6 PDF snapshot
    When I build the snapshot
    Then it still renders three PDF pages
    And it still draws the Technician Scorecards panel

  Scenario: Customer PDF adds SLA and resolution panels
    Given a customer Phase 6 PDF snapshot
    When I build the snapshot
    Then it draws an SLA Compliance panel
    And it draws a Resolution Time panel
