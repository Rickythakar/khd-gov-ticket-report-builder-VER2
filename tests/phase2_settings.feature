Feature: Phase 2 settings system
  As Ricky
  I want report defaults to persist between runs
  So I do not have to reconfigure mode, export preferences, and SLA thresholds every time

  Scenario: Missing settings fall back to defaults
    Given no settings.json file exists yet
    When the settings module loads
    Then the default settings are returned

  Scenario: Partial overrides are merged with defaults
    Given a settings.json file only overrides mode and one SLA target
    When the settings module loads
    Then the overridden values are preserved
    And the remaining settings fall back to defaults

  Scenario: Saved settings persist across restarts
    Given a user changes export and noise-filter preferences
    When the settings are saved and the app is restarted
    Then the previously saved preferences are loaded from settings.json
