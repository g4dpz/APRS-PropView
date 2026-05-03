Feature: Weather Display
  As an amateur radio operator
  I want to see current weather conditions and severe weather alerts
  So that I have situational awareness during operations

  Scenario: Weather banner displays conditions
    Given the test server is running
    And weather is enabled with location "SW1A 1AA"
    When the weather data loads
    Then the weather banner should show temperature
    And the weather banner should show wind speed

  Scenario: Metric units display correctly
    Given the test server is running
    And the region is detected as "UK"
    And the unit system is "metric"
    When the weather data loads
    Then temperature should display in Celsius
    And wind speed should display in km/h

  Scenario: Weather alert display
    Given the test server is running
    And a severe weather warning is active
    When the weather data loads
    Then a warning banner should be visible
    And the alert should show severity "warning"

  Scenario: UK postcode location resolution
    Given the test server is running
    When I enter location code "SW1A 1AA"
    And click the lookup button
    Then the location should resolve to coordinates near London
