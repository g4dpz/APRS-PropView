"""Alert providers for fetching severe weather alerts from regional APIs.

Provides a unified interface for NWS (US) and Meteoalarm (UK/EU) alert sources.
All providers return normalized alert dicts with a common structure so the
frontend can display alerts from both providers uniformly.
"""

import asyncio
import logging
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("propview.alert_providers")

# CAP XML namespace
CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"

# Atom feed namespace
ATOM_NS = "http://www.w3.org/2005/Atom"


# ── Utility functions ─────────────────────────────────────────────────


def classify_alert_categories(event: str, alert_type: str) -> List[str]:
    """Return coarse map overlay categories for a weather alert.

    Replicates the logic from weather.py's _classify_alert_categories.
    """
    categories: List[str] = []
    event_lower = (event or "").lower()

    if alert_type == "warning":
        categories.append("warnings")
    elif alert_type == "watch":
        categories.append("watches")

    if any(term in event_lower for term in ("flood", "flash flood", "coastal flood")):
        categories.append("flood")
    if any(
        term in event_lower
        for term in ("winter", "snow", "blizzard", "ice", "freeze", "freezing", "sleet")
    ):
        categories.append("winter")
    if "marine" in event_lower:
        categories.append("marine")
    if any(term in event_lower for term in ("fire", "red flag", "heat")):
        categories.append("fire_heat")

    if not categories:
        categories.append("other")

    return list(dict.fromkeys(categories))


def map_meteoalarm_severity(awareness_level: str) -> str:
    """Map a Meteoalarm awareness/severity level to 'warning' or 'watch'.

    - "Extreme" / "Severe" → "warning"
    - "Moderate" / "Minor" / unknown → "watch"
    """
    if awareness_level in ("Extreme", "Severe"):
        return "warning"
    return "watch"


def parse_cap_polygon(polygon_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Convert a CAP polygon string to a GeoJSON Polygon geometry.

    CAP format: "lat1,lon1 lat2,lon2 ..."
    GeoJSON format: {"type": "Polygon", "coordinates": [[[lon1,lat1], ...]]}

    The ring is closed per GeoJSON spec. Already-closed rings are preserved
    without duplicating the closing point.

    Returns None for empty, whitespace-only, None, or fewer than 3 valid points.
    """
    if not polygon_text or not polygon_text.strip():
        return None

    pairs = polygon_text.strip().split()
    coords = []
    for pair in pairs:
        parts = pair.split(",")
        if len(parts) != 2:
            continue
        try:
            lat = float(parts[0])
            lon = float(parts[1])
            coords.append([lon, lat])
        except (ValueError, IndexError):
            continue

    if len(coords) < 3:
        return None

    # Close the ring if not already closed
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    return {"type": "Polygon", "coordinates": [coords]}


def parse_cap_alert(info_element: ET.Element) -> Optional[Dict[str, Any]]:
    """Parse a CAP <info> XML element into a normalized alert dict.

    Returns None if the info element has no event field.
    """

    def _text(tag: str) -> str:
        """Get text content of a child element, or empty string."""
        el = info_element.find(f"{{{CAP_NS}}}{tag}")
        if el is None:
            # Try without namespace (some feeds omit it)
            el = info_element.find(tag)
        return (el.text or "").strip() if el is not None else ""

    event = _text("event")
    if not event:
        return None

    severity = _text("severity")
    urgency = _text("urgency")
    certainty = _text("certainty")
    headline = _text("headline")
    description = _text("description")
    instruction = _text("instruction")
    sender = _text("senderName") or _text("sender")
    effective = _text("effective")
    expires = _text("expires")

    alert_type = map_meteoalarm_severity(severity)

    # Extract area information
    area_desc = ""
    geometry = None
    area_el = info_element.find(f"{{{CAP_NS}}}area")
    if area_el is None:
        area_el = info_element.find("area")
    if area_el is not None:
        ad = area_el.find(f"{{{CAP_NS}}}areaDesc")
        if ad is None:
            ad = area_el.find("areaDesc")
        area_desc = (ad.text or "").strip() if ad is not None else ""

        polygon_el = area_el.find(f"{{{CAP_NS}}}polygon")
        if polygon_el is None:
            polygon_el = area_el.find("polygon")
        if polygon_el is not None:
            geometry = parse_cap_polygon(polygon_el.text)

    return {
        "id": str(uuid.uuid4()),
        "event": event,
        "severity": severity,
        "alert_type": alert_type,
        "certainty": certainty,
        "urgency": urgency,
        "headline": headline,
        "description": description[:6000],
        "instruction": instruction[:3000] if instruction else "",
        "sender": sender,
        "effective": effective,
        "expires": expires,
        "area_desc": area_desc,
        "geometry": geometry,
        "overlay_categories": classify_alert_categories(event, alert_type),
    }


# ── Abstract base class ──────────────────────────────────────────────


class AlertProvider(ABC):
    """Abstract base class for weather alert providers."""

    @abstractmethod
    async def fetch_alerts(
        self, lat: float, lon: float, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch active weather alerts for the given coordinates.

        Returns a list of normalized alert dicts.
        """
        ...  # pragma: no cover


# ── NWS Alert Provider ───────────────────────────────────────────────


class NWSAlertProvider(AlertProvider):
    """US alerts from the National Weather Service API (api.weather.gov)."""

    async def fetch_alerts(
        self, lat: float, lon: float, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch active NWS weather alerts near a location.

        Keyword args forwarded to the underlying fetch:
          - range_miles (int): search radius, default 50
          - scope_mode (str): "point" or "county_zone"
          - scope_zone (str): NWS zone code when scope_mode is "county_zone"
        """
        try:
            # Import here to avoid circular imports
            from server.weather import fetch_nws_alerts

            return await fetch_nws_alerts(
                lat,
                lon,
                range_miles=kwargs.get("range_miles", 50),
                scope_mode=kwargs.get("scope_mode", "point"),
                scope_zone=kwargs.get("scope_zone", ""),
            )
        except Exception as e:
            logger.error(f"NWS alert fetch failed: {e}")
            return []


# ── Meteoalarm Alert Provider ────────────────────────────────────────

# Bounding boxes for Meteoalarm country mapping: (min_lat, max_lat, min_lon, max_lon)
_METEOALARM_COUNTRY_BOXES: Dict[str, Tuple[float, float, float, float]] = {
    "united-kingdom": (49.9, 60.9, -8.2, 1.8),
    "ireland": (51.3, 55.5, -10.5, -5.5),
    "france": (41.3, 51.1, -5.2, 9.6),
    "germany": (47.3, 55.1, 5.9, 15.0),
    "spain": (36.0, 43.8, -9.3, 3.3),
    "portugal": (36.9, 42.2, -9.5, -6.2),
    "italy": (36.6, 47.1, 6.6, 18.5),
    "netherlands": (50.7, 53.6, 3.3, 7.2),
    "belgium": (49.5, 51.5, 2.5, 6.4),
    "luxembourg": (49.4, 50.2, 5.7, 6.5),
    "switzerland": (45.8, 47.8, 5.9, 10.5),
    "austria": (46.4, 49.0, 9.5, 17.2),
    "poland": (49.0, 54.8, 14.1, 24.2),
    "czech-republic": (48.5, 51.1, 12.1, 18.9),
    "slovakia": (47.7, 49.6, 16.8, 22.6),
    "hungary": (45.7, 48.6, 16.1, 22.9),
    "romania": (43.6, 48.3, 20.3, 29.7),
    "bulgaria": (41.2, 44.2, 22.4, 28.6),
    "greece": (34.8, 41.7, 19.4, 29.6),
    "croatia": (42.4, 46.6, 13.5, 19.4),
    "slovenia": (45.4, 46.9, 13.4, 16.6),
    "denmark": (54.6, 57.8, 8.1, 15.2),
    "sweden": (55.3, 69.1, 11.1, 24.2),
    "norway": (58.0, 71.2, 4.6, 31.1),
    "finland": (59.8, 70.1, 20.6, 31.6),
    "estonia": (57.5, 59.7, 21.8, 28.2),
    "latvia": (55.7, 58.1, 20.9, 28.2),
    "lithuania": (53.9, 56.5, 20.9, 26.8),
    "serbia": (42.2, 46.2, 18.8, 23.0),
    "montenegro": (41.8, 43.6, 18.4, 20.4),
    "north-macedonia": (40.9, 42.4, 20.4, 23.0),
    "albania": (39.6, 42.7, 19.3, 21.1),
    "bosnia-herzegovina": (42.6, 45.3, 15.7, 19.6),
    "cyprus": (34.6, 35.7, 32.3, 34.6),
    "malta": (35.8, 36.1, 14.2, 14.6),
    "iceland": (63.3, 66.6, -24.5, -13.5),
}


def _guess_country_from_coords(
    lat: float, lon: float
) -> Optional[str]:
    """Map station coordinates to a Meteoalarm country name using bounding boxes.

    Returns the country name (hyphenated, lowercase) or None if no match.
    """
    for country, (min_lat, max_lat, min_lon, max_lon) in _METEOALARM_COUNTRY_BOXES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return country
    return None


class MeteoalarmAlertProvider(AlertProvider):
    """UK/EU alerts from Meteoalarm Atom/CAP feeds."""

    async def fetch_alerts(
        self, lat: float, lon: float, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Fetch active Meteoalarm alerts for the given coordinates.

        Determines the country feed from coordinates, fetches the Atom feed,
        and parses CAP entries into normalized alert dicts.
        """
        try:
            country = _guess_country_from_coords(lat, lon)
            if not country:
                logger.warning(
                    f"No Meteoalarm country match for ({lat}, {lon}), "
                    "defaulting to united-kingdom"
                )
                country = "united-kingdom"

            feed_url = (
                f"https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{country}"
            )
            alerts = await self._fetch_and_parse_feed(feed_url)

            # Sort: warnings first, then watches
            alerts.sort(key=lambda a: (0 if a["alert_type"] == "warning" else 1))

            return alerts
        except Exception as e:
            logger.error(f"Meteoalarm alert fetch failed: {e}")
            return []

    async def _fetch_and_parse_feed(
        self, feed_url: str
    ) -> List[Dict[str, Any]]:
        """Fetch an Atom feed and parse CAP entries from it."""
        from server.weather import _async_http_get, _sync_http_get

        # Fetch the raw feed XML (not JSON) — use sync HTTP with custom handling
        loop = asyncio.get_running_loop()
        xml_text = await loop.run_in_executor(
            None, self._fetch_feed_xml, feed_url
        )
        if not xml_text:
            return []

        return self._parse_atom_feed(xml_text)

    @staticmethod
    def _fetch_feed_xml(feed_url: str, timeout: int = 30) -> Optional[str]:
        """Fetch raw XML text from a Meteoalarm Atom feed URL."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": "APRSPropView/1.0 (amateur-radio-weather-app)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            logger.warning(f"Meteoalarm feed fetch failed for {feed_url}: {e}")
            return None

    @staticmethod
    def _parse_atom_feed(xml_text: str) -> List[Dict[str, Any]]:
        """Parse an Atom feed containing CAP alert entries."""
        alerts: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse Meteoalarm Atom feed XML: {e}")
            return []

        # Find all <entry> elements in the Atom feed
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            # Look for CAP <info> elements within the entry content
            # Meteoalarm feeds embed CAP alert XML inside <content> or directly
            # Try to find <info> elements with CAP namespace
            for info in entry.iter(f"{{{CAP_NS}}}info"):
                alert = parse_cap_alert(info)
                if alert is not None:
                    # Use the Atom entry ID if available
                    entry_id_el = entry.find(f"{{{ATOM_NS}}}id")
                    if entry_id_el is not None and entry_id_el.text:
                        alert["id"] = entry_id_el.text.strip()
                    alerts.append(alert)

            # Also try without namespace prefix (some feeds vary)
            if not any(True for _ in entry.iter(f"{{{CAP_NS}}}info")):
                for info in entry.iter("info"):
                    alert = parse_cap_alert(info)
                    if alert is not None:
                        entry_id_el = entry.find(f"{{{ATOM_NS}}}id")
                        if entry_id_el is not None and entry_id_el.text:
                            alert["id"] = entry_id_el.text.strip()
                        alerts.append(alert)

        return alerts


# ── Factory ───────────────────────────────────────────────────────────


def get_alert_provider(region: str) -> AlertProvider:
    """Return the correct alert provider for the given region.

    - "US" → NWSAlertProvider
    - "UK" / "EU" → MeteoalarmAlertProvider
    """
    if region == "US":
        return NWSAlertProvider()
    return MeteoalarmAlertProvider()
