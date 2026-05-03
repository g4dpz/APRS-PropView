Feature: APRS Messaging
  As an amateur radio operator
  I want to send and receive APRS messages
  So that I can communicate with other stations

  Scenario: Send a message
    Given the test server is running
    And APRS-IS is connected
    When I send a message to "W3ADO" with text "Hello 73"
    Then the message log should contain a sent message to "W3ADO"

  Scenario: Receive a message
    Given the test server is running
    And a message arrives from "K3ABC" with text "QSL de K3ABC"
    Then the message log should contain a received message from "K3ABC"
    And the message should show as acknowledged

  Scenario: Message ACK/REJ display
    Given the test server is running
    And I have sent a message to "W3ADO" with ID "42"
    When an ACK arrives from "W3ADO" for message "42"
    Then the sent message should show as acknowledged
