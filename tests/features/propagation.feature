Feature: Propagation Monitoring
  As an amateur radio operator
  I want to see VHF propagation scores and metrics
  So that I can identify band openings

  Scenario: My Station propagation score updates
    Given the test server is running
    And 5 direct-heard RF stations within 100km
    When the propagation meter updates
    Then the My Station score should be above 0
    And the My Station level should not be "none"

  Scenario: Regional propagation score updates
    Given the test server is running
    And 8 RF stations heard via digipeater within 200km
    When the propagation meter updates
    Then the Regional score should be above 0

  Scenario: Band opening alert fires
    Given the test server is running
    And alerts are enabled with threshold 3 stations at 100km
    And 5 direct-heard RF stations beyond 100km
    When the propagation broadcast cycle runs
    Then a "my_station_opening" alert should be triggered
