"""Step definitions for APRS messaging features."""


def step_send_message(context, callsign, text):
    """WHEN I send a message to "{callsign}" with text "{text}" """
    pass


def step_message_arrives(context, callsign, text):
    """GIVEN a message arrives from "{callsign}" with text "{text}" """
    pass


def step_message_log_contains_sent(context, callsign):
    """THEN the message log should contain a sent message to "{callsign}" """
    pass


def step_message_acknowledged(context):
    """THEN the message should show as acknowledged"""
    pass
