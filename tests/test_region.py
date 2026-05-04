"""Property-based tests for region detection (server/region.py).

Feature: uk-eu-internationalization
Properties: 1, 2, 3, 4
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from server.region import detect_region, get_effective_region, _US_BOXES, _UK_BOX, _EU_BOX, _in_box


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Any valid latitude/longitude on the globe
lat_strategy = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
lon_strategy = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)


def coords_in_box(box):
    """Strategy that generates (lat, lon) pairs inside a bounding box."""
    min_lat, max_lat, min_lon, max_lon = box
    return st.tuples(
        st.floats(min_value=min_lat, max_value=max_lat, allow_nan=False, allow_infinity=False),
        st.floats(min_value=min_lon, max_value=max_lon, allow_nan=False, allow_infinity=False),
    )


# Manual region choices
manual_region_strategy = st.sampled_from(["US", "UK", "EU"])


# ---------------------------------------------------------------------------
# Property 1: Region detection always returns a valid region
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(lat=lat_strategy, lon=lon_strategy)
def test_detect_region_always_returns_valid_region(lat, lon):
    """Property 1: For any lat in [-90, 90] and lon in [-180, 180],
    detect_region() returns one of "US", "UK", "EU".

    **Validates: Requirements 1.1, 1.5**
    """
    result = detect_region(lat, lon)
    assert result in {"US", "UK", "EU"}, f"Got unexpected region: {result!r}"


# ---------------------------------------------------------------------------
# Property 2: Coordinates inside a region's bounding box classify to that
#              region
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(data=st.data())
def test_us_box_coordinates_classify_as_us(data):
    """Property 2 (US part): Any coordinate inside a US bounding box
    classifies as "US".

    **Validates: Requirements 1.2, 1.3, 1.4, 1.6**
    """
    box = data.draw(st.sampled_from(_US_BOXES))
    lat, lon = data.draw(coords_in_box(box))
    assert detect_region(lat, lon) == "US"


@settings(max_examples=200)
@given(data=st.data())
def test_uk_box_coordinates_not_in_us_classify_as_uk(data):
    """Property 2 (UK part): Any coordinate inside the UK box that is NOT
    inside any US box classifies as "UK".

    **Validates: Requirements 1.2, 1.3, 1.4, 1.6**
    """
    lat, lon = data.draw(coords_in_box(_UK_BOX))
    # Exclude points that also fall inside a US box
    assume(not any(_in_box(lat, lon, us_box) for us_box in _US_BOXES))
    assert detect_region(lat, lon) == "UK"


@settings(max_examples=200)
@given(data=st.data())
def test_eu_box_coordinates_not_in_us_or_uk_classify_as_eu(data):
    """Property 2 (EU part): Any coordinate inside the EU box that is NOT
    inside any US box or the UK box classifies as "EU".

    **Validates: Requirements 1.2, 1.3, 1.4, 1.6**
    """
    lat, lon = data.draw(coords_in_box(_EU_BOX))
    # Exclude points that also fall inside a US box or the UK box
    assume(not any(_in_box(lat, lon, us_box) for us_box in _US_BOXES))
    assume(not _in_box(lat, lon, _UK_BOX))
    assert detect_region(lat, lon) == "EU"


# ---------------------------------------------------------------------------
# Property 3: Manual region override supersedes auto-detection
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(lat=lat_strategy, lon=lon_strategy, manual=manual_region_strategy)
def test_manual_override_supersedes_auto_detection(lat, lon, manual):
    """Property 3: For any coordinates and manual region in {"US", "UK", "EU"},
    get_effective_region() returns the manual value.

    **Validates: Requirements 2.1**
    """
    result = get_effective_region(lat, lon, manual)
    assert result == manual, (
        f"Expected manual override {manual!r}, got {result!r} for ({lat}, {lon})"
    )


# ---------------------------------------------------------------------------
# Property 4: Auto-detection passthrough
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(lat=lat_strategy, lon=lon_strategy)
def test_auto_detection_passthrough(lat, lon):
    """Property 4: For any lat/lon, get_effective_region(lat, lon, "auto")
    returns the same as detect_region(lat, lon).

    **Validates: Requirements 2.2**
    """
    auto_result = get_effective_region(lat, lon, "auto")
    direct_result = detect_region(lat, lon)
    assert auto_result == direct_result, (
        f"Auto passthrough mismatch: get_effective_region returned {auto_result!r}, "
        f"detect_region returned {direct_result!r} for ({lat}, {lon})"
    )


# ===========================================================================
# Unit Tests — Known-location classification and manual override
# ===========================================================================

import pytest


# ---------------------------------------------------------------------------
# Known-location classification (detect_region)
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat, lon, expected, label",
    [
        # US locations
        (40.7128, -74.0060, "US", "New York"),
        (34.0522, -118.2437, "US", "Los Angeles"),
        (61.2181, -149.9003, "US", "Anchorage (Alaska)"),
        (21.3069, -157.8583, "US", "Honolulu (Hawaii)"),
        # UK locations
        (51.5074, -0.1278, "UK", "London"),
        (55.9533, -3.1883, "UK", "Edinburgh"),
        # EU locations
        (48.8566, 2.3522, "EU", "Paris"),
        (52.5200, 13.4050, "EU", "Berlin"),
        (40.4168, -3.7038, "EU", "Madrid"),
    ],
)
def test_detect_region_known_locations(lat, lon, expected, label):
    """Known city coordinates classify to the correct region."""
    assert detect_region(lat, lon) == expected, f"{label} should be {expected}"


# ---------------------------------------------------------------------------
# Default-to-US for coordinates outside all bounding boxes
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat, lon, label",
    [
        (35.6762, 139.6503, "Tokyo"),
        (-75.0, 0.0, "Antarctica"),
        (0.0, -170.0, "Central Pacific"),
    ],
)
def test_detect_region_defaults_to_us(lat, lon, label):
    """Coordinates outside all defined bounding boxes default to 'US'."""
    assert detect_region(lat, lon) == "US", f"{label} should default to US"


# ---------------------------------------------------------------------------
# Manual override via get_effective_region
# Validates: Requirements 2.1, 2.2, 2.3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat, lon, configured, expected, description",
    [
        # Explicit overrides supersede auto-detection
        (51.5, -0.1, "US", "US", "override UK coords to US"),
        (40.7, -74.0, "UK", "UK", "override US coords to UK"),
        (40.7, -74.0, "EU", "EU", "override US coords to EU"),
        # "auto" delegates to coordinate-based detection
        (51.5, -0.1, "auto", "UK", "auto-detect for London coords"),
        # Empty string falls back to auto-detection
        (51.5, -0.1, "", "UK", "empty string falls back to auto"),
        # Unrecognized value falls back to auto-detection
        (51.5, -0.1, "invalid", "UK", "unrecognized value falls back to auto"),
    ],
)
def test_get_effective_region_override(lat, lon, configured, expected, description):
    """Manual override and fallback behavior of get_effective_region."""
    result = get_effective_region(lat, lon, configured)
    assert result == expected, f"{description}: expected {expected}, got {result}"
