"""Property-based tests for alert providers (server/alert_providers.py).

Feature: uk-eu-internationalization
Properties: 11, 12
Validates: Requirements 11.2, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from server.alert_providers import map_meteoalarm_severity, parse_cap_polygon


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Severity strings: known values plus random text
_known_severities = st.sampled_from(["Extreme", "Severe", "Moderate", "Minor"])
_random_text = st.text(min_size=0, max_size=50)
_severity_strategy = st.one_of(_known_severities, _random_text)

# Valid latitude/longitude floats for CAP polygon coordinates
_lat = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
_lon = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)
_coord_pair = st.tuples(_lat, _lon)


@st.composite
def cap_polygon_string(draw, min_points=3, max_points=20, closed=None):
    """Generate a CAP polygon string from random lat/lon pairs.

    CAP format: "lat1,lon1 lat2,lon2 ..."

    If closed is True, the last point equals the first.
    If closed is False, the last point differs from the first.
    If closed is None, randomly choose.
    """
    n = draw(st.integers(min_value=min_points, max_value=max_points))
    pairs = [draw(_coord_pair) for _ in range(n)]

    if closed is None:
        closed = draw(st.booleans())

    if closed and len(pairs) >= 3:
        # Ensure last point equals first
        pairs.append(pairs[0])
    elif not closed and len(pairs) >= 3:
        # Ensure last point differs from first (if they happen to match, tweak it)
        if pairs[-1] == pairs[0]:
            # Nudge the last point slightly
            lat, lon = pairs[-1]
            pairs[-1] = (lat + 0.001, lon + 0.001)

    text = " ".join(f"{lat},{lon}" for lat, lon in pairs)
    return text, pairs


# ---------------------------------------------------------------------------
# Property 11: Meteoalarm severity mapping always returns warning or watch
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(severity=_severity_strategy)
def test_meteoalarm_severity_always_returns_warning_or_watch(severity):
    """Property 11: For any input string, map_meteoalarm_severity() returns
    either "warning" or "watch". Specifically, "Extreme" and "Severe" map to
    "warning"; all other inputs map to "watch".

    **Validates: Requirements 11.2, 11.4, 11.5**
    """
    result = map_meteoalarm_severity(severity)
    assert result in {"warning", "watch"}, (
        f"Expected 'warning' or 'watch', got {result!r} for input {severity!r}"
    )

    if severity in ("Extreme", "Severe"):
        assert result == "warning", (
            f"Expected 'warning' for {severity!r}, got {result!r}"
        )
    else:
        assert result == "watch", (
            f"Expected 'watch' for {severity!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 12: Valid CAP polygons produce closed GeoJSON with correct
#              coordinate order
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(data=cap_polygon_string(closed=False))
def test_cap_polygon_produces_closed_geojson_with_lon_lat_order(data):
    """Property 12: For any list of 3+ valid lat/lon pairs, parse_cap_polygon()
    returns a GeoJSON Polygon where:
      (a) coordinates are in [lon, lat] order
      (b) the ring is closed (first point equals last point)
      (c) each coordinate is a two-element list of floats

    **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    """
    polygon_text, input_pairs = data
    result = parse_cap_polygon(polygon_text)

    assert result is not None, (
        f"Expected a GeoJSON Polygon for valid input, got None. Input: {polygon_text!r}"
    )
    assert result["type"] == "Polygon"

    coords = result["coordinates"]
    assert len(coords) == 1, "GeoJSON Polygon should have exactly one ring"

    ring = coords[0]

    # (a) Each coordinate is [lon, lat] — verify against input pairs
    # The input pairs are (lat, lon), so ring[i] should be [lon, lat]
    for i, coord in enumerate(ring):
        assert len(coord) == 2, (
            f"Coordinate at index {i} should have 2 elements, got {len(coord)}"
        )
        assert isinstance(coord[0], float), (
            f"Coordinate[{i}][0] (lon) should be float, got {type(coord[0])}"
        )
        assert isinstance(coord[1], float), (
            f"Coordinate[{i}][1] (lat) should be float, got {type(coord[1])}"
        )

    # Verify [lon, lat] order for the non-closing points
    for i in range(min(len(input_pairs), len(ring) - 1)):
        in_lat, in_lon = input_pairs[i]
        assert ring[i] == [in_lon, in_lat], (
            f"Coordinate at index {i} should be [lon={in_lon}, lat={in_lat}], "
            f"got {ring[i]}"
        )

    # (b) Ring is closed
    assert ring[0] == ring[-1], (
        f"Ring should be closed: first={ring[0]}, last={ring[-1]}"
    )


@settings(max_examples=200)
@given(data=cap_polygon_string(closed=True))
def test_cap_polygon_already_closed_no_duplicate(data):
    """Property 12 (already-closed variant): For already-closed input rings,
    the closure is preserved without duplicating the closing point.

    **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    """
    polygon_text, input_pairs = data
    result = parse_cap_polygon(polygon_text)

    assert result is not None, (
        f"Expected a GeoJSON Polygon for valid closed input, got None. Input: {polygon_text!r}"
    )

    ring = result["coordinates"][0]

    # Ring should be closed
    assert ring[0] == ring[-1], (
        f"Ring should be closed: first={ring[0]}, last={ring[-1]}"
    )

    # The number of points in the ring should equal the number of input pairs
    # (since input was already closed, no extra point should be added)
    assert len(ring) == len(input_pairs), (
        f"Already-closed ring should have {len(input_pairs)} points (no duplication), "
        f"got {len(ring)}"
    )


# ===========================================================================
# Unit tests for alert providers (Task 6.4)
# Validates: Requirements 10.1–10.5, 11.1–11.5, 12.1–12.6
# ===========================================================================

import xml.etree.ElementTree as ET

import pytest

from server.alert_providers import (
    get_alert_provider,
    NWSAlertProvider,
    MeteoalarmAlertProvider,
    map_meteoalarm_severity,
    parse_cap_polygon,
    parse_cap_alert,
    classify_alert_categories,
    CAP_NS,
)


# ---------------------------------------------------------------------------
# 1. Factory routing
# ---------------------------------------------------------------------------


class TestGetAlertProvider:
    """Test get_alert_provider() returns the correct provider for each region."""

    def test_us_returns_nws_provider(self):
        """Validates: Requirement 10.2"""
        provider = get_alert_provider("US")
        assert isinstance(provider, NWSAlertProvider)

    def test_uk_returns_meteoalarm_provider(self):
        """Validates: Requirement 10.1"""
        provider = get_alert_provider("UK")
        assert isinstance(provider, MeteoalarmAlertProvider)

    def test_eu_returns_meteoalarm_provider(self):
        """Validates: Requirement 10.1"""
        provider = get_alert_provider("EU")
        assert isinstance(provider, MeteoalarmAlertProvider)


# ---------------------------------------------------------------------------
# 2. Severity mapping known values
# ---------------------------------------------------------------------------


class TestMapMeteoalarmSeverity:
    """Test map_meteoalarm_severity() for known severity levels."""

    @pytest.mark.parametrize(
        "severity, expected",
        [
            ("Extreme", "warning"),
            ("Severe", "warning"),
            ("Moderate", "watch"),
            ("Minor", "watch"),
            ("", "watch"),
        ],
    )
    def test_known_severity_values(self, severity, expected):
        """Validates: Requirements 11.2, 11.4, 11.5"""
        assert map_meteoalarm_severity(severity) == expected


# ---------------------------------------------------------------------------
# 3. CAP polygon edge cases
# ---------------------------------------------------------------------------


class TestParseCapPolygonEdgeCases:
    """Test parse_cap_polygon() returns None for invalid inputs."""

    def test_none_returns_none(self):
        """Validates: Requirement 12.5"""
        assert parse_cap_polygon(None) is None

    def test_empty_string_returns_none(self):
        """Validates: Requirement 12.5"""
        assert parse_cap_polygon("") is None

    def test_whitespace_only_returns_none(self):
        """Validates: Requirement 12.5"""
        assert parse_cap_polygon("   ") is None

    def test_two_points_returns_none(self):
        """Validates: Requirement 12.6"""
        assert parse_cap_polygon("51.5,-0.1 48.8,2.3") is None

    def test_malformed_returns_none(self):
        """Validates: Requirement 12.6"""
        assert parse_cap_polygon("invalid") is None


# ---------------------------------------------------------------------------
# 4. CAP polygon valid case
# ---------------------------------------------------------------------------


class TestParseCapPolygonValid:
    """Test parse_cap_polygon() produces correct GeoJSON for valid input."""

    def test_three_points_produces_closed_geojson(self):
        """Validates: Requirements 12.1, 12.2, 12.3"""
        result = parse_cap_polygon("51.5,-0.1 48.8,2.3 52.5,13.4")
        assert result is not None
        assert result["type"] == "Polygon"

        ring = result["coordinates"][0]
        # 3 input points + 1 closing point = 4
        assert len(ring) == 4

        # Verify [lon, lat] order
        assert ring[0] == [-0.1, 51.5]
        assert ring[1] == [2.3, 48.8]
        assert ring[2] == [13.4, 52.5]

        # Ring is closed
        assert ring[0] == ring[-1]


# ---------------------------------------------------------------------------
# 5. parse_cap_alert with complete info element
# ---------------------------------------------------------------------------


def _build_cap_info_xml(
    event="Severe Thunderstorm Warning",
    severity="Severe",
    headline="Severe Thunderstorm Warning for London",
    area_desc="Greater London",
    polygon="51.5,-0.1 51.6,0.0 51.4,0.1",
    urgency="Immediate",
    certainty="Observed",
    description="A severe thunderstorm has been observed.",
    instruction="Take shelter immediately.",
    sender="Met Office",
    effective="2024-01-15T12:00:00Z",
    expires="2024-01-15T18:00:00Z",
    include_event=True,
):
    """Build a CAP <info> XML element for testing."""
    ns = CAP_NS
    info = ET.Element(f"{{{ns}}}info")

    def _add(tag, text):
        el = ET.SubElement(info, f"{{{ns}}}{tag}")
        el.text = text

    if include_event and event is not None:
        _add("event", event)
    if severity is not None:
        _add("severity", severity)
    if urgency is not None:
        _add("urgency", urgency)
    if certainty is not None:
        _add("certainty", certainty)
    if headline is not None:
        _add("headline", headline)
    if description is not None:
        _add("description", description)
    if instruction is not None:
        _add("instruction", instruction)
    if sender is not None:
        _add("senderName", sender)
    if effective is not None:
        _add("effective", effective)
    if expires is not None:
        _add("expires", expires)

    if area_desc is not None or polygon is not None:
        area_el = ET.SubElement(info, f"{{{ns}}}area")
        if area_desc is not None:
            ad = ET.SubElement(area_el, f"{{{ns}}}areaDesc")
            ad.text = area_desc
        if polygon is not None:
            pg = ET.SubElement(area_el, f"{{{ns}}}polygon")
            pg.text = polygon

    return info


class TestParseCapAlertComplete:
    """Test parse_cap_alert() with a complete info element."""

    def test_complete_info_produces_all_fields(self):
        """Validates: Requirements 11.1, 11.2"""
        info = _build_cap_info_xml()
        result = parse_cap_alert(info)

        assert result is not None
        assert result["event"] == "Severe Thunderstorm Warning"
        assert result["severity"] == "Severe"
        assert result["alert_type"] == "warning"
        assert result["urgency"] == "Immediate"
        assert result["certainty"] == "Observed"
        assert result["headline"] == "Severe Thunderstorm Warning for London"
        assert result["description"] == "A severe thunderstorm has been observed."
        assert result["instruction"] == "Take shelter immediately."
        assert result["sender"] == "Met Office"
        assert result["effective"] == "2024-01-15T12:00:00Z"
        assert result["expires"] == "2024-01-15T18:00:00Z"
        assert result["area_desc"] == "Greater London"
        assert result["geometry"] is not None
        assert result["geometry"]["type"] == "Polygon"
        assert "id" in result
        assert isinstance(result["overlay_categories"], list)


# ---------------------------------------------------------------------------
# 6. parse_cap_alert with missing event
# ---------------------------------------------------------------------------


class TestParseCapAlertMissingEvent:
    """Test parse_cap_alert() returns None when event is missing."""

    def test_missing_event_returns_none(self):
        """Validates: Requirement 11.3"""
        info = _build_cap_info_xml(include_event=False)
        result = parse_cap_alert(info)
        assert result is None


# ---------------------------------------------------------------------------
# 7. classify_alert_categories
# ---------------------------------------------------------------------------


class TestClassifyAlertCategories:
    """Test classify_alert_categories() assigns correct overlay categories."""

    def test_tornado_warning(self):
        cats = classify_alert_categories("Tornado Warning", "warning")
        assert "warnings" in cats

    def test_flood_watch(self):
        cats = classify_alert_categories("Flood Watch", "watch")
        assert "watches" in cats
        assert "flood" in cats

    def test_winter_storm_warning(self):
        cats = classify_alert_categories("Winter Storm Warning", "warning")
        assert "warnings" in cats
        assert "winter" in cats
