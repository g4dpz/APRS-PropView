"""Property-based tests for unit system (server/units.py).

Feature: uk-eu-internationalization
Properties: 5, 6, 7
Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from server.units import (
    UnitSystem,
    IMPERIAL,
    METRIC,
    format_weather_response,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Unit system: either IMPERIAL or METRIC
unit_system_strategy = st.sampled_from([IMPERIAL, METRIC])

# Random float values for weather fields
weather_float = st.floats(
    min_value=-100.0, max_value=200.0, allow_nan=False, allow_infinity=False
)

# Raw weather data dict with both imperial and metric field variants
raw_weather_strategy = st.fixed_dictionaries(
    {
        "temperature_f": weather_float,
        "temperature_c": weather_float,
        "wind_speed_mph": weather_float,
        "wind_speed_kmh": weather_float,
        "precipitation_in": weather_float,
        "precipitation_mm": weather_float,
    }
)


# ---------------------------------------------------------------------------
# Property 5: Formatted weather response always includes complete unit labels
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(raw=raw_weather_strategy, unit_system=unit_system_strategy)
def test_format_weather_response_includes_complete_unit_labels(raw, unit_system):
    """Property 5: For any raw weather data dict and for any unit system
    (imperial or metric), format_weather_response(raw, unit_system) includes
    a unit_labels dictionary containing keys "temperature", "wind_speed",
    "precipitation", and "distance".

    **Validates: Requirements 5.1, 5.2**
    """
    result = format_weather_response(raw, unit_system)

    assert "unit_labels" in result, "Response must include 'unit_labels'"
    labels = result["unit_labels"]
    required_keys = {"temperature", "wind_speed", "precipitation", "distance"}
    assert required_keys.issubset(labels.keys()), (
        f"unit_labels missing keys: {required_keys - labels.keys()}"
    )


# ---------------------------------------------------------------------------
# Property 6: Unit labels match the active unit system
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(raw=raw_weather_strategy)
def test_imperial_unit_labels_match(raw):
    """Property 6 (imperial): For any raw weather data formatted with the
    imperial unit system, the unit_labels contain "°F", "mph", "in", "miles".

    **Validates: Requirements 5.3, 5.4**
    """
    result = format_weather_response(raw, IMPERIAL)
    labels = result["unit_labels"]

    assert labels["temperature"] == "°F", f"Expected '°F', got {labels['temperature']!r}"
    assert labels["wind_speed"] == "mph", f"Expected 'mph', got {labels['wind_speed']!r}"
    assert labels["precipitation"] == "in", f"Expected 'in', got {labels['precipitation']!r}"
    assert labels["distance"] == "miles", f"Expected 'miles', got {labels['distance']!r}"


@settings(max_examples=200)
@given(raw=raw_weather_strategy)
def test_metric_unit_labels_match(raw):
    """Property 6 (metric): For any raw weather data formatted with the
    metric unit system, the unit_labels contain "°C", "km/h", "mm", "km".

    **Validates: Requirements 5.3, 5.4**
    """
    result = format_weather_response(raw, METRIC)
    labels = result["unit_labels"]

    assert labels["temperature"] == "°C", f"Expected '°C', got {labels['temperature']!r}"
    assert labels["wind_speed"] == "km/h", f"Expected 'km/h', got {labels['wind_speed']!r}"
    assert labels["precipitation"] == "mm", f"Expected 'mm', got {labels['precipitation']!r}"
    assert labels["distance"] == "km", f"Expected 'km', got {labels['distance']!r}"


# ---------------------------------------------------------------------------
# Property 7: Metric response includes both metric and backward-compatible
#              fields
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(raw=raw_weather_strategy)
def test_metric_response_includes_metric_and_backward_compatible_fields(raw):
    """Property 7: For any raw weather data formatted with the metric unit
    system, the response includes metric-named fields (temperature_c,
    wind_speed_kmh, precipitation_mm) AND backward-compatible imperial-named
    fields (temperature_f, wind_speed_mph, precipitation_in).

    **Validates: Requirements 5.5**
    """
    result = format_weather_response(raw, METRIC)

    # Metric-named fields must be present
    assert "temperature_c" in result, "Metric response must include 'temperature_c'"
    assert "wind_speed_kmh" in result, "Metric response must include 'wind_speed_kmh'"
    assert "precipitation_mm" in result, "Metric response must include 'precipitation_mm'"

    # Backward-compatible imperial-named fields must also be present
    assert "temperature_f" in result, "Metric response must include backward-compatible 'temperature_f'"
    assert "wind_speed_mph" in result, "Metric response must include backward-compatible 'wind_speed_mph'"
    assert "precipitation_in" in result, "Metric response must include backward-compatible 'precipitation_in'"


# ===========================================================================
# Unit tests (example-based) for server/units.py
# Task 2.3 — Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 5.1–5.5
# ===========================================================================

import pytest
from dataclasses import FrozenInstanceError

from server.units import (
    get_unit_system,
    open_meteo_unit_params,
)


# ---------------------------------------------------------------------------
# get_unit_system — explicit values and defaults
# ---------------------------------------------------------------------------

class TestGetUnitSystem:
    """Tests for get_unit_system() selection logic.

    Validates: Requirements 3.2, 3.3, 3.4
    """

    def test_metric_returns_metric(self):
        assert get_unit_system("metric") is METRIC

    def test_imperial_returns_imperial(self):
        assert get_unit_system("imperial") is IMPERIAL

    @pytest.mark.parametrize("value", ["METRIC", "Metric", "mEtRiC"])
    def test_case_insensitive_metric(self, value):
        assert get_unit_system(value) is METRIC

    def test_empty_string_defaults_to_imperial(self):
        assert get_unit_system("") is IMPERIAL

    def test_none_defaults_to_imperial(self):
        assert get_unit_system(None) is IMPERIAL

    @pytest.mark.parametrize("value", ["unknown", "meters", "fahrenheit", "  ", "0"])
    def test_unrecognized_defaults_to_imperial(self, value):
        assert get_unit_system(value) is IMPERIAL


# ---------------------------------------------------------------------------
# open_meteo_unit_params — API query string generation
# ---------------------------------------------------------------------------

class TestOpenMeteoUnitParams:
    """Tests for Open-Meteo API parameter generation.

    Validates: Requirements 3.5
    """

    def test_imperial_params(self):
        params = open_meteo_unit_params(IMPERIAL)
        assert "&temperature_unit=fahrenheit" in params
        assert "&wind_speed_unit=mph" in params
        assert "&precipitation_unit=inch" in params

    def test_metric_params(self):
        params = open_meteo_unit_params(METRIC)
        assert "&temperature_unit=celsius" in params
        assert "&wind_speed_unit=kmh" in params
        assert "&precipitation_unit=mm" in params


# ---------------------------------------------------------------------------
# format_weather_response — unit labels and named fields
# ---------------------------------------------------------------------------

class TestFormatWeatherResponse:
    """Tests for format_weather_response() enrichment.

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
    """

    def test_imperial_unit_labels(self):
        raw = {"temperature_f": 72.0, "wind_speed_mph": 10.0, "precipitation_in": 0.5}
        result = format_weather_response(raw, IMPERIAL)
        labels = result["unit_labels"]
        assert labels == {
            "temperature": "°F",
            "wind_speed": "mph",
            "precipitation": "in",
            "distance": "miles",
        }

    def test_metric_unit_labels(self):
        raw = {"temperature_c": 22.0, "wind_speed_kmh": 16.0, "precipitation_mm": 12.0}
        result = format_weather_response(raw, METRIC)
        labels = result["unit_labels"]
        assert labels == {
            "temperature": "°C",
            "wind_speed": "km/h",
            "precipitation": "mm",
            "distance": "km",
        }

    def test_empty_raw_dict_still_adds_unit_labels(self):
        result = format_weather_response({}, IMPERIAL)
        assert "unit_labels" in result
        assert result["unit_labels"]["temperature"] == "°F"

        result_metric = format_weather_response({}, METRIC)
        assert "unit_labels" in result_metric
        assert result_metric["unit_labels"]["temperature"] == "°C"


# ---------------------------------------------------------------------------
# UnitSystem frozen immutability
# ---------------------------------------------------------------------------

class TestUnitSystemFrozen:
    """UnitSystem is a frozen dataclass — fields cannot be mutated.

    Validates: Requirement 3.1 (immutable unit configurations)
    """

    def test_imperial_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            IMPERIAL.temperature_unit = "celsius"

    def test_metric_is_frozen(self):
        with pytest.raises(FrozenInstanceError):
            METRIC.temp_label = "°F"
