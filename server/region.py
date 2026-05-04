"""Region detection from station coordinates using bounding-box geometry.

Classifies station coordinates into one of three operating regions: US, UK, or EU.
Supports manual override via configuration.
"""

from typing import Tuple, List

# Bounding box format: (min_lat, max_lat, min_lon, max_lon)
BoundingBox = Tuple[float, float, float, float]

# US territory bounding boxes
_US_BOXES: List[BoundingBox] = [
    (24.5, 49.4, -125.0, -66.9),   # CONUS (contiguous US)
    (51.2, 71.4, -179.1, -129.9),  # Alaska
    (18.9, 22.2, -160.2, -154.8),  # Hawaii
    (17.6, 18.6, -67.3, -64.5),    # Puerto Rico / US Virgin Islands
    (13.2, 13.7, 144.6, 145.0),    # Guam
    (-14.4, -14.1, -171.1, -168.1),  # American Samoa
]

# UK bounding box
_UK_BOX: BoundingBox = (49.9, 60.9, -8.2, 1.8)

# EU bounding box (broad continental Europe including UK as subset)
_EU_BOX: BoundingBox = (34.0, 71.0, -25.0, 45.0)

# Valid region values for configuration
VALID_REGIONS = {"auto", "US", "UK", "EU"}


def _in_box(lat: float, lon: float, box: BoundingBox) -> bool:
    """Check whether a coordinate pair falls within a bounding box."""
    min_lat, max_lat, min_lon, max_lon = box
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def detect_region(lat: float, lon: float) -> str:
    """Classify station coordinates into a region.

    Checks US boxes first, then UK, then EU. Coordinates outside all
    defined bounding boxes default to "US" for backward compatibility.

    Args:
        lat: Station latitude in decimal degrees.
        lon: Station longitude in decimal degrees.

    Returns:
        One of "US", "UK", or "EU".
    """
    # Check US territories first
    for box in _US_BOXES:
        if _in_box(lat, lon, box):
            return "US"

    # Check UK (geographic subset of EU box, so must come before EU)
    if _in_box(lat, lon, _UK_BOX):
        return "UK"

    # Check broad EU box
    if _in_box(lat, lon, _EU_BOX):
        return "EU"

    # Default to US for coordinates outside all boxes
    return "US"


def get_effective_region(lat: float, lon: float, configured_region: str = "auto") -> str:
    """Determine the effective region, respecting manual overrides.

    If the configured region is a valid manual override ("US", "UK", or "EU"),
    that value is returned directly. Otherwise (including "auto", empty string,
    or any unrecognized value), the function delegates to coordinate-based
    auto-detection.

    Args:
        lat: Station latitude in decimal degrees.
        lon: Station longitude in decimal degrees.
        configured_region: The value from weather.region config. Defaults to "auto".

    Returns:
        One of "US", "UK", or "EU".
    """
    # Manual override: return directly if it's a valid explicit region
    if configured_region in ("US", "UK", "EU"):
        return configured_region

    # For "auto", empty, or unrecognized values, delegate to auto-detection
    return detect_region(lat, lon)
