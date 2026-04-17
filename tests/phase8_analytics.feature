Feature: Phase 8 advanced internal analytics
  As Ricky
  I want deeper internal-only analytics over ticket complexity, workload, and issue patterns
  So I can coach the team and spot operational risk without leaving the local dashboard

  Scenario: Existing internal artifacts already provide a technician-review foundation
    Given the current internal artifact builder
    When I analyze the sample CSV in internal mode
    Then technician review metrics are already available as the Phase 8 foundation

  Scenario: Analytics module exists with the planned pure-logic functions
    Given the Phase 8 analytics module path
    When I inspect the internal analytics API
    Then analytics.py exists and exposes the planned logic functions

  Scenario: Metrics module re-exports Phase 8 analytics helpers
    Given the metrics module
    When I inspect the Phase 8 integration surface
    Then complexity, keyword, workload, and heatmap helpers are available from metrics.py

  Scenario: Report artifacts are extended with analytics payloads
    Given the ReportArtifacts dataclass
    When I inspect the internal analytics fields
    Then analytics payload fields exist for dashboard serialization

  Scenario: Internal dashboard template exposes the analytics widget
    Given the dashboard template
    When I review the internal analytics surface
    Then it renders an Analytics widget with complexity, keyword, workload, and peak-load tabs

  Scenario: Server serialization exposes analytics data to the template
    Given internal-mode report artifacts
    When I serialize them for the FastAPI dashboard
    Then the payload includes analytics data for the internal widget
