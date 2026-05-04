# Implementation Plan: UK/EU Internationalization

## Overview

This plan implements UK/EU internationalization for APRS PropView's weather subsystem. The work is organized into incremental steps: region detection, unit system, geocoding chain, alert providers with CAP parsing, ducting invariance and caching, WeatherManager integration, configuration, and frontend label adaptation. Each step builds on the previous, with property-based and unit tests wired in close to the implementation they validate.

## Tasks

- [x] 1. Implement Region Detector (`server/region.py`)
  - [x] 1.1 Create `server/region.py` with bounding-box constants and `detect_region()` function
    - Define `_US_BOXES` (CONUS, Alaska, Hawaii, PRVI, Guam, Samoa), `_UK_BOX`, `_EU_BOX`, and `VALID_REGIONS`
    - Implement `detect_region(lat, lon)` checking US boxes first, then UK, then EU, defaulting to `"US"`
    - Implement `get_effective_region(lat, lon, configured_region)` with manual override logic
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3_

  - [x]* 1.2 Write property tests for region detection (Properties 1–4)
    - **Property 1: Region detection always returns a valid region**
    - **Validates: Requirements 1.1, 1.5**
    - **Property 2: Coordinates inside a region's bounding box classify to that region**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.6**
    - **Property 3: Manual region override supersedes auto-detection**
    - **Validates: Requirements 2.1**
    - **Property 4: Auto-detection passthrough**
    - **Validates: Requirements 2.2**

  - [x]* 1.3 Write unit tests for region detection
    - Test known-location classification (New York, London, Paris, Tokyo, Antarctica)
    - Test default-to-US for out-of-box coordinates
    - Test manual override with `"US"`, `"UK"`, `"EU"`, `"auto"`, empty string, unrecognized values
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3_

- [x] 2. Implement Unit System (`server/units.py`)
  - [x] 2.1 Create `server/units.py` with `UnitSystem` frozen dataclass and constants
    - Define `UnitSystem` as `@dataclass(frozen=True)` with API params, display labels, and field name suffixes
    - Create `IMPERIAL` and `METRIC` singleton constants
    - Implement `get_unit_system(units)` returning `METRIC` for `"metric"`, `IMPERIAL` otherwise
    - Implement `open_meteo_unit_params(unit_system)` returning URL query string
    - Implement `format_weather_response(raw, unit_system)` adding `unit_labels` dict and named fields
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 2.2 Write property tests for unit system (Properties 5–7)
    - **Property 5: Formatted weather response always includes complete unit labels**
    - **Validates: Requirements 5.1, 5.2**
    - **Property 6: Unit labels match the active unit system**
    - **Validates: Requirements 5.3, 5.4**
    - **Property 7: Metric response includes both metric and backward-compatible fields**
    - **Validates: Requirements 5.5**

  - [x]* 2.3 Write unit tests for unit system
    - Test `get_unit_system` defaults for empty, `None`, and unknown strings
    - Test Open-Meteo parameter generation for imperial and metric
    - Test `format_weather_response` adds correct fields and labels
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Geocoding Chain (extend `server/weather.py`)
  - [x] 4.1 Add UK postcode resolver and Nominatim client to `server/weather.py`
    - Add `_UK_POSTCODE_RE` regex for all standard UK postcode formats (case-insensitive)
    - Implement `_resolve_uk_postcode(postcode)` calling Postcodes.io API
    - Implement `_resolve_nominatim(query)` with 1-second rate limiting, `APRSPropView/1.0` User-Agent, and 80-char display name truncation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 4.2 Extend ICAO resolver with Nominatim fallback
    - Modify `_resolve_icao()` to fall back to `_resolve_nominatim("{ICAO} airport")` when NWS returns no result
    - Normalize ICAO codes to uppercase before resolution
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.3 Update `resolve_location()` with full resolution chain
    - Implement priority chain: UK postcode → US ZIP → ICAO → Nominatim free-text
    - No fallthrough: if matched resolver returns None, overall result is None
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x]* 4.4 Write property tests for geocoding (Properties 8–10)
    - **Property 8: UK postcode regex accepts all valid format variants**
    - **Validates: Requirements 6.2, 6.3, 6.4**
    - **Property 9: ICAO regex accepts any four uppercase letters**
    - **Validates: Requirements 7.4**
    - **Property 10: Nominatim display name truncation**
    - **Validates: Requirements 8.6**

  - [x]* 4.5 Write unit tests for geocoding chain
    - Test format disambiguation: UK postcode not confused with ICAO; ZIP not confused with UK postcode
    - Test resolution chain routing with mocked HTTP
    - Test no-fallthrough behavior
    - Test Nominatim rate limiting and User-Agent header
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Alert Providers (`server/alert_providers.py`)
  - [x] 6.1 Create `server/alert_providers.py` with abstract base and CAP parsing
    - Define `AlertProvider` ABC with `fetch_alerts(lat, lon, **kwargs)` interface
    - Implement `parse_cap_alert(info_element)` extracting event, severity, urgency, certainty, headline, description, area_desc, geometry
    - Implement `parse_cap_polygon(polygon_text)` converting CAP polygon to GeoJSON with closed ring and [lon, lat] order
    - Implement `map_meteoalarm_severity(awareness_level)` mapping to `"warning"` or `"watch"`
    - Implement `classify_alert_categories(event, alert_type)` for overlay categories
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x] 6.2 Implement `NWSAlertProvider` and `MeteoalarmAlertProvider`
    - Implement `NWSAlertProvider` wrapping existing `fetch_nws_alerts()` logic
    - Implement `MeteoalarmAlertProvider` fetching Meteoalarm Atom/CAP feeds with country mapping from coordinates
    - Implement `get_alert_provider(region)` factory returning correct provider
    - Sort returned alerts with warnings before watches
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x]* 6.3 Write property tests for alert providers (Properties 11–12)
    - **Property 11: Meteoalarm severity mapping always returns warning or watch**
    - **Validates: Requirements 11.2, 11.4, 11.5**
    - **Property 12: Valid CAP polygons produce closed GeoJSON with correct coordinate order**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**

  - [x]* 6.4 Write unit tests for alert providers
    - Test factory routing: `get_alert_provider("US")` returns `NWSAlertProvider`, `"UK"`/`"EU"` returns `MeteoalarmAlertProvider`
    - Test CAP XML parsing: complete info element produces all required fields; missing event returns None
    - Test CAP polygon edge cases: empty, None, whitespace-only, fewer than 3 points all return None
    - Test alert sorting: warnings before watches
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [x] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Unit-Invariant Ducting and Threshold Cache
  - [x] 8.1 Update `fetch_ducting_data()` for unit invariance
    - Ensure ducting API requests always use hardcoded `temperature_unit=fahrenheit` and `wind_speed_unit=mph`
    - Verify ducting score computation uses internal Fahrenheit/mb values only
    - Clamp ducting index to [0, 100]
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 8.2 Implement threshold-based ducting cache in `WeatherManager`
    - Store `prev_pressure` and `prev_temp` from each ducting fetch
    - On cache check: skip refetch if pressure Δ < 2.0 mb AND temp Δ < 3.0°F
    - Refetch if either threshold is met or exceeded
    - Force refetch if previous values are None
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [x]* 8.3 Write property tests for ducting (Properties 13–16)
    - **Property 13: Ducting score is unit-invariant and bounded**
    - **Validates: Requirements 13.2, 13.3**
    - **Property 14: Below-threshold atmospheric changes do not trigger ducting refetch**
    - **Validates: Requirements 14.1**
    - **Property 15: Pressure threshold met triggers ducting refetch**
    - **Validates: Requirements 14.2**
    - **Property 16: Temperature threshold met triggers ducting refetch**
    - **Validates: Requirements 14.3**

  - [x]* 8.4 Write unit tests for ducting
    - Test exact threshold boundary values (2.0 mb, 3.0°F), zero change, both thresholds met
    - Test ducting score clamping to [0, 100]
    - Test cache comparison with missing previous data triggers refetch
    - _Requirements: 13.1, 13.2, 13.3, 14.1, 14.2, 14.3, 14.4_

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Integrate WeatherManager with Region, Units, and Alert Providers
  - [x] 10.1 Update `WeatherManager` with region-aware unit selection and alert routing
    - Add `effective_region` property delegating to `get_effective_region()`
    - Add `effective_units` property: explicit config if `"imperial"` or `"metric"`, else auto-select metric for UK/EU and imperial for US
    - Update weather fetch to use `open_meteo_unit_params()` and `format_weather_response()`
    - Include `region` in weather response payload for frontend consumption
    - Invalidate cache on unit system change
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 10.2 Route alert fetching through `get_alert_provider(region)`
    - Replace direct `fetch_nws_alerts()` call with provider-based routing
    - Meteoalarm provider determines country feed URL from station coordinates
    - _Requirements: 10.1, 10.2_

  - [x]* 10.3 Write integration tests for WeatherManager
    - Test auto-selection of units by region: UK/EU → metric, US → imperial
    - Test explicit units override regardless of region
    - Test cache invalidation on unit/location changes
    - Test weather response includes region field
    - Test alert provider routing based on region
    - _Requirements: 4.1, 4.2, 4.3, 10.1, 10.2_

- [x] 11. Update Configuration (`server/config.py`)
  - [x] 11.1 Add `region` and `units` fields to `WeatherConfig`
    - Add `region: str = "auto"` and `units: str = "imperial"` to `WeatherConfig` dataclass
    - Update `DEFAULT_CONFIG` TOML template with new fields
    - Update `Config.save()` to serialize the new fields
    - _Requirements: 2.1, 2.2, 2.3, 3.2, 3.3, 3.4_

  - [x] 11.2 Add region/units settings to the settings API and validation
    - Add validation for `weather.region` (must be `"auto"`, `"US"`, `"UK"`, or `"EU"`)
    - Add validation for `weather.units` (must be `"imperial"` or `"metric"`)
    - Wire new fields through the settings save/load endpoints in `server/app.py`
    - _Requirements: 2.1, 2.2, 2.3, 3.2, 3.3, 3.4_

- [x] 12. Implement Region-Aware Frontend Labels (`static/js/weather.js`)
  - [x] 12.1 Add region-aware label update function to `static/js/weather.js`
    - Implement `updateRegionLabels(region)` to update location input placeholder text
    - US/unset: placeholder references US ZIP codes and ICAO codes
    - UK/EU: placeholder references UK postcodes, ICAO codes, and place names
    - _Requirements: 15.1, 15.2, 15.3_

  - [x] 12.2 Update weather rendering to use `unit_labels` from API response
    - Read `unit_labels` dictionary from weather API response
    - Display correct unit suffixes for temperature, wind speed, and precipitation
    - Fall back to hardcoded imperial suffixes if `unit_labels` is absent
    - Call `updateRegionLabels()` when weather response includes a `region` value
    - _Requirements: 15.3, 15.4_

  - [x] 12.3 Add region/units settings controls to `static/index.html`
    - Add region dropdown (Auto, US, UK, EU) to weather settings section
    - Add units dropdown (Imperial, Metric) to weather settings section
    - Wire dropdowns to settings save/load logic in `static/js/app.js`
    - _Requirements: 2.1, 3.2_

  - [x]* 12.4 Write unit tests for frontend label logic
    - Test US region shows ZIP/ICAO placeholder hints
    - Test UK/EU region shows postcode/ICAO/place name placeholder hints
    - Test unit_labels rendering for imperial and metric
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (16 properties total)
- Unit tests validate specific examples and edge cases
- The implementation language is Python (backend) and JavaScript (frontend), matching the existing codebase
