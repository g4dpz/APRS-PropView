"""Unit system management for imperial and metric display units.

Provides immutable UnitSystem configurations, Open-Meteo API parameter
generation, and weather response formatting with unit labels.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class UnitSystem:
    """Immutable unit configuration with API params, display labels, and field name suffixes."""

    # Open-Meteo API parameters
    temperature_unit: str       # "fahrenheit" or "celsius"
    wind_speed_unit: str        # "mph" or "kmh"
    precipitation_unit: str     # "inch" or "mm"

    # Display labels
    temp_label: str             # "°F" or "°C"
    wind_label: str             # "mph" or "km/h"
    precip_label: str           # "in" or "mm"
    distance_label: str         # "miles" or "km"

    # Response field name suffixes
    temp_field: str             # "temperature_f" or "temperature_c"
    wind_field: str             # "wind_speed_mph" or "wind_speed_kmh"
    precip_field: str           # "precipitation_in" or "precipitation_mm"


IMPERIAL = UnitSystem(
    temperature_unit="fahrenheit",
    wind_speed_unit="mph",
    precipitation_unit="inch",
    temp_label="°F",
    wind_label="mph",
    precip_label="in",
    distance_label="miles",
    temp_field="temperature_f",
    wind_field="wind_speed_mph",
    precip_field="precipitation_in",
)

METRIC = UnitSystem(
    temperature_unit="celsius",
    wind_speed_unit="kmh",
    precipitation_unit="mm",
    temp_label="°C",
    wind_label="km/h",
    precip_label="mm",
    distance_label="km",
    temp_field="temperature_c",
    wind_field="wind_speed_kmh",
    precip_field="precipitation_mm",
)


def get_unit_system(units: str) -> UnitSystem:
    """Return METRIC for "metric", IMPERIAL otherwise.

    Defaults to IMPERIAL for None, empty string, or any unrecognized value.
    """
    if isinstance(units, str) and units.strip().lower() == "metric":
        return METRIC
    return IMPERIAL


def open_meteo_unit_params(unit_system: UnitSystem) -> str:
    """Return URL query string fragment for Open-Meteo API unit parameters.

    Example: "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
    """
    return (
        f"&temperature_unit={unit_system.temperature_unit}"
        f"&wind_speed_unit={unit_system.wind_speed_unit}"
        f"&precipitation_unit={unit_system.precipitation_unit}"
    )


def format_weather_response(raw: Dict[str, Any], unit_system: UnitSystem) -> Dict[str, Any]:
    """Add unit labels and named fields to a raw weather response dict.

    1. Copies the raw dict.
    2. Adds a ``unit_labels`` dict with keys "temperature", "wind_speed",
       "precipitation", and "distance".
    3. Adds named fields using the unit system's field names
       (e.g. temperature_c = raw temperature value).
    4. For metric, also includes backward-compatible imperial-named fields
       so existing consumers continue to work.
    5. Returns the enriched dict.
    """
    result = dict(raw)

    # Add unit labels
    result["unit_labels"] = {
        "temperature": unit_system.temp_label,
        "wind_speed": unit_system.wind_label,
        "precipitation": unit_system.precip_label,
        "distance": unit_system.distance_label,
    }

    # Extract raw values (Open-Meteo returns these generic keys in the current dict)
    temp_value = raw.get("temperature_f") if raw.get("temperature_f") is not None else raw.get("temperature_c")
    wind_value = raw.get("wind_speed_mph") if raw.get("wind_speed_mph") is not None else raw.get("wind_speed_kmh")
    precip_value = raw.get("precipitation_in") if raw.get("precipitation_in") is not None else raw.get("precipitation_mm")

    # Add named fields for the active unit system
    if temp_value is not None:
        result[unit_system.temp_field] = temp_value
    if wind_value is not None:
        result[unit_system.wind_field] = wind_value
    if precip_value is not None:
        result[unit_system.precip_field] = precip_value

    # For metric, also include backward-compatible imperial-named fields
    if unit_system is METRIC:
        if temp_value is not None and "temperature_f" not in result:
            result["temperature_f"] = temp_value
        if wind_value is not None and "wind_speed_mph" not in result:
            result["wind_speed_mph"] = wind_value
        if precip_value is not None and "precipitation_in" not in result:
            result["precipitation_in"] = precip_value

    return result
