Feature: Phase 5 functional dashboard wiring
  As Ricky
  I want the UI overhaul to improve interactivity without changing the single-click workflow
  So the dashboard is easier to review while keeping the export flow stable

  Scenario: Phase 5 dependencies are declared
    Given the project requirements file
    When I review the UI dependencies
    Then Plotly and streamlit-aggrid are included for the dashboard overhaul

  Scenario: Detail tables use the interactive grid renderer
    Given a non-empty dataframe block
    When the detail table renderer runs
    Then it uses AG Grid instead of Streamlit's plain dataframe widget

  Scenario: Distribution charts use Plotly
    Given a populated distribution table
    When the chart renderer runs
    Then it sends a Plotly figure to Streamlit instead of an Altair chart

  Scenario: Customer mode exposes SLA and danger-zone views without raw preview
    Given the app is running in customer mode
    When I upload a valid CSV
    Then the dashboard shows SLA and Danger Zone tabs
    And the raw preview tab stays hidden
