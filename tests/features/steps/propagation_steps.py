"""Step definitions for propagation monitoring features."""


def step_direct_heard_stations(context, count, distance):
    """GIVEN {count} direct-heard RF stations within {distance}km"""
    pass


def step_propagation_meter_updates(context):
    """WHEN the propagation meter updates"""
    pass


def step_my_station_score_above(context, threshold):
    """THEN the My Station score should be above {threshold}"""
    pass


def step_alert_triggered(context, alert_type):
    """THEN a "{alert_type}" alert should be triggered"""
    pass
