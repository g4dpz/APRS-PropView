Feature: Analytics Dashboard
  As an amateur radio operator
  I want to view propagation analytics
  So that I can understand VHF band conditions over time

  Scenario: Longest path leaderboard loads
    Given the test server is running
    And RF stations have been heard at various distances
    When I view the analytics dashboard
    Then the longest path leaderboard should show stations ranked by distance

  Scenario: Propagation heatmap displays
    Given the test server is running
    And propagation data has been logged for 24 hours
    When I view the heatmap section
    Then a 24-hour heatmap grid should be visible

  Scenario: Station reliability scores display
    Given the test server is running
    And stations have been heard with varying consistency
    When I view the reliability section
    Then stations should be graded A through F
