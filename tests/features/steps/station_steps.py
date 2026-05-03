"""Step definitions for station tracking features.

These steps map domain-specific amateur radio vocabulary to
Playwright browser automation actions against a test server.

NOTE: Full implementation requires Behave + Playwright installation.
These are structured stubs ready for implementation.
"""

# from behave import given, when, then


def step_station_heard_on_rf(context, callsign, distance, bearing):
    """GIVEN station "{callsign}" is heard on RF at {distance}km bearing {bearing}"""
    # Seed the test database with a station record
    pass


def step_station_heard_via_digi(context, callsign, digi, distance):
    """GIVEN station "{callsign}" is heard on RF via digipeater "{digi}" at {distance}km"""
    pass


def step_station_list_refreshes(context):
    """WHEN the station list refreshes"""
    # Wait for WebSocket update or trigger API call
    pass


def step_rf_list_contains(context, callsign):
    """THEN the RF station list should contain "{callsign}" """
    # Check the RF station list DOM element
    pass


def step_map_shows_marker(context, callsign):
    """THEN the map should show a marker for "{callsign}" """
    # Check Leaflet map markers
    pass
