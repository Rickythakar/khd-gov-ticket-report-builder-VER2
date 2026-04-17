Feature: Phase 7 multi-month comparison
  As Ricky
  I want the FastAPI dashboard to compare uploaded periods instead of only a single month
  So I can review trends, deltas, and export comparison packs before partner meetings

  Scenario: Existing artifacts already preserve month-level volume
    Given the current report artifact builder
    When I analyze the sample CSV
    Then a monthly trend table is already available as the Phase 7 foundation

  Scenario: Upload flow accepts multiple CSV files
    Given the live FastAPI upload endpoint
    When I inspect the upload contract
    Then it accepts multiple UploadFile inputs for multi-month comparison mode

  Scenario: A new upload replaces the prior comparison set
    Given prior upload state is already in memory
    When I upload a new multi-file comparison set
    Then the previous in-memory upload set is replaced instead of accumulating forever

  Scenario: Metrics module exposes comparison helpers
    Given the metrics module
    When I inspect the Phase 7 trend API
    Then compute_monthly_breakdown and compute_period_deltas are available

  Scenario: Dashboard exposes period selector and trends widget
    Given the dashboard template
    When I review the comparison controls
    Then it renders 1M, QTR, HALF, and YR period selectors
    And it renders a Trends widget surface

  Scenario: Rendered trend chart attributes keep valid JSON payloads
    Given rendered comparison dashboard HTML
    When I inspect the trend SVG data attributes
    Then the label and value payloads remain valid JSON arrays for browser-side chart rendering

  Scenario: Comparison metric cards isolate the primary value from delta text
    Given rendered comparison dashboard HTML
    When I inspect the total tickets metric card
    Then the primary value remains in a dedicated span so the counter animation cannot concatenate the delta text

  Scenario: Workbook export adds a trends sheet
    Given a workbook built from data spanning multiple months
    When I inspect the workbook sheets
    Then a visible Trends sheet is included for comparison exports
