Feature: Phase 4 internal versus customer mode
  As Ricky
  I want the report builder to adapt its UI and exports by audience
  So customer deliverables stay safe while internal reviews retain full diagnostics

  Scenario: Customer mode still computes the full artifacts payload
    Given a validated ticket dataset and customer mode settings
    When report artifacts are built
    Then the returned artifacts still contain the internal-only metrics for downstream export layers

  Scenario: Customer mode hides internal-only review tabs
    Given the app is running in customer mode
    When I upload a valid CSV
    Then the technician and raw-preview tabs are not shown

  Scenario: Internal mode reveals technician and raw-preview tabs
    Given the app is running in internal mode
    When I upload a valid CSV
    Then the technician and raw-preview tabs are shown

  Scenario: Internal workbook export adds a hidden technician review sheet
    Given mode-aware workbook export is available
    When I build a customer workbook and an internal workbook from the same dataset
    Then only the internal workbook contains a hidden "Technician Review" sheet

  Scenario: Internal PDF export adds a third page
    Given customer and internal artifacts exist for the same dataset
    When I build the executive PDF snapshot for each mode
    Then the internal PDF contains one more page than the customer PDF
