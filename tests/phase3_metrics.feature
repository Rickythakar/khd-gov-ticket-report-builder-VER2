Feature: Phase 3 metrics engine
  As Ricky
  I want the report builder to compute richer operational metrics
  So the workbook can surface SLA, technician, repeat-contact, and resolution insights

  Scenario: The metrics module exposes the planned calculation entrypoints
    Given Phase 3 has started
    When I import the metrics module
    Then the module exposes the metrics functions from the Phase 3 spec

  Scenario: Repeat-contact analysis identifies contacts over threshold
    Given ticket history with one contact appearing at least three times
    When repeat-contact analysis runs with threshold three
    Then the repeated contact appears in the result with the ticket count

  Scenario: First-contact resolution uses time and escalation rules
    Given ticket history with a mix of quick non-escalated and escalated tickets
    When first-contact resolution is computed
    Then only tickets resolved in thirty minutes or less without escalation count toward FCR

  Scenario: Report artifacts include the Phase 3 metrics payload
    Given a validated ticket dataset and settings
    When report artifacts are built
    Then the returned artifacts expose the new Phase 3 metrics fields
