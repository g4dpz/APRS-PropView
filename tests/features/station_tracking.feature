Feature: Station Tracking
  As an amateur radio operator
  I want to see stations heard on RF and APRS-IS on the map and station lists
  So that I can monitor VHF propagation conditions

  Scenario: Direct-heard RF station appears on map
    Given the test server is running
    And station "W1AW" is heard on RF at 150km bearing 045
    When the station list refreshes
    Then the RF station list should contain "W1AW"
    And the map should show a marker for "W1AW"

  Scenario: Digipeated RF station appears on map
    Given the test server is running
    And station "K3ABC" is heard on RF via digipeater "N0CALL" at 200km
    When the station list refreshes
    Then the RF station list should contain "K3ABC"
    And the station "K3ABC" should show as "Via Digipeater"

  Scenario: APRS-IS station appears on map
    Given the test server is running
    And station "VE3XYZ" is heard on APRS-IS at 500km
    When the station list refreshes
    Then the APRS-IS station list should contain "VE3XYZ"

  Scenario: Station expiry removes old stations
    Given the test server is running
    And station "W1OLD" was last heard 25 hours ago
    When the cleanup cycle runs
    Then the RF station list should not contain "W1OLD"
