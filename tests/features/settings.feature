Feature: Settings Configuration
  As an amateur radio operator
  I want to configure PropView through the web UI
  So that I can set up my station details and preferences

  Scenario: European callsign is accepted
    Given the test server is running
    When I enter callsign "2E0XYZ" in settings
    And save the configuration
    Then the callsign should be accepted without error

  Scenario: UK Foundation callsign is accepted
    Given the test server is running
    When I enter callsign "2E0ABC" in settings
    And save the configuration
    Then the callsign should be accepted without error

  Scenario: Invalid callsign is rejected
    Given the test server is running
    When I enter callsign "!!INVALID!!" in settings
    And save the configuration
    Then an error message should appear

  Scenario: Region detection from coordinates
    Given the test server is running
    When I set station coordinates to 51.5074 N, 0.1278 W
    Then the detected region should be "UK"
    And the location placeholder should show "UK Postcode, ICAO, or Place Name"

  Scenario: Callsign validation rejects placeholder
    Given the test server is running
    When I enter callsign "N0CALL" in settings
    And enable the IGate
    And save the configuration
    Then an error about placeholder callsign should appear
