# Requirements Document

## Introduction

This document specifies the UK/EU internationalization feature for APRS PropView. The feature extends the weather subsystem — originally US-only — to support stations located in the United Kingdom and continental Europe. It adds automatic region detection from station coordinates, a metric unit system, multi-format geocoding (UK postcodes, ICAO codes, free-text place names via Nominatim), severe weather alerts from Meteoalarm CAP/Atom feeds, and region-aware frontend labels. The ducting index calculation remains unit-invariant by always fetching internal data in Fahrenheit/mb regardless of display units.

## Glossary

- **Region_Detector**: The module (`server/region.py`) that classifies station coordinates into one of three operating regions (US, UK, EU) using bounding-box geometry.
- **Unit_System**: The module (`server/units.py`) that defines imperial and metric display units and formats weather API responses with the appropriate labels and field names.
- **Geocoder**: The location resolution chain in `server/weather.py` (`resolve_location()`) that converts user-entered location codes into latitude/longitude coordinates.
- **Postcodes_IO_Client**: The async function (`_resolve_uk_postcode()`) that resolves UK postcodes to coordinates via the Postcodes.io API.
- **Nominatim_Client**: The async function (`_resolve_nominatim()`) that resolves free-text location queries to coordinates via the OpenStreetMap Nominatim API.
- **ICAO_Resolver**: The async function (`_resolve_icao()`) that resolves ICAO airport codes to coordinates, trying NWS first and falling back to Nominatim for non-US codes.
- **Meteoalarm_Provider**: The alert provider class (`MeteoalarmAlertProvider` in `server/alert_providers.py`) that fetches severe weather alerts from Meteoalarm Atom/CAP feeds for UK and EU regions.
- **NWS_Provider**: The alert provider class (`NWSAlertProvider`) that fetches severe weather alerts from the US National Weather Service API.
- **Alert_Factory**: The factory function (`get_alert_provider()`) that returns the correct alert provider based on the detected region.
- **CAP_Parser**: The functions (`parse_cap_alert()`, `parse_cap_polygon()`) that parse Common Alerting Protocol XML elements into normalized alert dictionaries and GeoJSON geometry.
- **Weather_Manager**: The class (`WeatherManager` in `server/weather.py`) that orchestrates weather data fetching, caching, unit formatting, and alert retrieval.
- **Ducting_Calculator**: The function (`fetch_ducting_data()`) that computes the VHF tropospheric ducting probability index from atmospheric data.
- **Bounding_Box**: A tuple of (min_lat, max_lat, min_lon, max_lon) used for geographic region classification.
- **UK_Postcode**: A postal code in the format used by Royal Mail, consisting of an outward code (e.g., SW1A, M1, LS18) and an inward code (digit followed by two letters), optionally separated by a space.
- **ICAO_Code**: A four-letter alphanumeric code assigned by the International Civil Aviation Organization to identify airports and weather stations worldwide.

## Requirements

### Requirement 1: Region Detection from Station Coordinates

**User Story:** As a station operator, I want the system to automatically detect whether my station is in the US, UK, or EU based on my configured coordinates, so that the correct alert provider, unit system, and geocoding strategy are selected without manual configuration.

#### Acceptance Criteria

1. THE Region_Detector SHALL classify any latitude/longitude coordinate pair into exactly one of "US", "UK", or "EU"
2. WHEN station coordinates fall within any US Bounding_Box (contiguous US, Alaska, Hawaii, Puerto Rico/USVI, Guam, American Samoa), THE Region_Detector SHALL return "US"
3. WHEN station coordinates fall within the UK Bounding_Box (lat 49.9–60.9, lon -8.2–1.8) and do not fall within any US Bounding_Box, THE Region_Detector SHALL return "UK"
4. WHEN station coordinates fall within the EU Bounding_Box (lat 34.0–71.0, lon -25.0–45.0) and do not fall within any US Bounding_Box or the UK Bounding_Box, THE Region_Detector SHALL return "EU"
5. WHEN station coordinates fall outside all defined Bounding_Boxes, THE Region_Detector SHALL default to "US"
6. THE Region_Detector SHALL check US Bounding_Boxes first, then the UK Bounding_Box, then the EU Bounding_Box, to ensure the UK (a geographic subset of the EU box) is classified correctly

### Requirement 2: Manual Region Override

**User Story:** As a station operator, I want to manually override the detected region via configuration, so that I can force a specific region if auto-detection is incorrect for my location.

#### Acceptance Criteria

1. WHERE the `weather.region` configuration is set to "US", "UK", or "EU", THE Region_Detector SHALL return that value regardless of station coordinates
2. WHERE the `weather.region` configuration is set to "auto", THE Region_Detector SHALL delegate to coordinate-based detection
3. IF the `weather.region` configuration contains an empty string or an unrecognized value, THEN THE Region_Detector SHALL fall back to coordinate-based auto-detection

### Requirement 3: Imperial and Metric Unit Systems

**User Story:** As a UK/EU station operator, I want weather data displayed in metric units (°C, km/h, mm), so that the readings match the conventions used in my region.

#### Acceptance Criteria

1. THE Unit_System SHALL define two unit configurations: imperial (°F, mph, in, miles) and metric (°C, km/h, mm, km)
2. WHEN the `weather.units` configuration is set to "metric", THE Unit_System SHALL select the metric configuration
3. WHEN the `weather.units` configuration is set to "imperial", THE Unit_System SHALL select the imperial configuration
4. IF the `weather.units` configuration contains an empty string or an unrecognized value, THEN THE Unit_System SHALL default to the imperial configuration
5. THE Unit_System SHALL generate Open-Meteo API query parameters matching the selected unit configuration (temperature_unit, wind_speed_unit, precipitation_unit)

### Requirement 4: Auto-Selection of Units by Region

**User Story:** As a station operator, I want the system to automatically choose metric units for UK/EU and imperial for US, so that I get region-appropriate defaults without manual configuration.

#### Acceptance Criteria

1. WHEN the effective region is "UK" or "EU" and no explicit unit override is configured, THE Weather_Manager SHALL select the metric unit configuration
2. WHEN the effective region is "US" and no explicit unit override is configured, THE Weather_Manager SHALL select the imperial unit configuration
3. WHERE the `weather.units` configuration is explicitly set to "imperial" or "metric", THE Weather_Manager SHALL use the configured value regardless of region

### Requirement 5: Weather Response Unit Labels

**User Story:** As a frontend developer, I want every weather API response to include a `unit_labels` dictionary, so that the UI can display the correct unit suffixes without hardcoding them.

#### Acceptance Criteria

1. THE Unit_System SHALL include a `unit_labels` dictionary in every formatted weather response
2. THE `unit_labels` dictionary SHALL contain keys for "temperature", "wind_speed", "precipitation", and "distance"
3. WHEN the imperial configuration is active, THE `unit_labels` SHALL contain "°F", "mph", "in", and "miles"
4. WHEN the metric configuration is active, THE `unit_labels` SHALL contain "°C", "km/h", "mm", and "km"
5. WHEN the metric configuration is active, THE Unit_System SHALL include metric-named response fields (temperature_c, wind_speed_kmh, precipitation_mm) alongside backward-compatible imperial-named fields

### Requirement 6: UK Postcode Geocoding

**User Story:** As a UK station operator, I want to enter my UK postcode as the weather location, so that the system resolves it to coordinates for weather data retrieval.

#### Acceptance Criteria

1. WHEN a location code matches the UK postcode pattern, THE Postcodes_IO_Client SHALL resolve the postcode to latitude, longitude, and a place name via the Postcodes.io API
2. THE Geocoder SHALL accept UK postcodes in all standard formats: A9 9AA, A99 9AA, A9A 9AA, AA9 9AA, AA99 9AA, and AA9A 9AA
3. THE Geocoder SHALL accept UK postcodes with or without a space between the outward and inward codes
4. THE Geocoder SHALL accept UK postcodes in any letter case (case-insensitive matching)
5. IF the Postcodes.io API returns an error or no result for a UK postcode, THEN THE Postcodes_IO_Client SHALL return None

### Requirement 7: ICAO Code Resolution with Nominatim Fallback

**User Story:** As a station operator, I want to enter an ICAO airport code (e.g., EGLL, LFPG) as my weather location, so that the system resolves it to coordinates regardless of whether the station is in the US or abroad.

#### Acceptance Criteria

1. WHEN a location code matches the ICAO pattern (exactly four uppercase letters), THE ICAO_Resolver SHALL first attempt resolution via the NWS stations API
2. WHEN the NWS stations API returns valid coordinates for an ICAO code, THE ICAO_Resolver SHALL use those coordinates
3. IF the NWS stations API does not return valid coordinates for an ICAO code, THEN THE ICAO_Resolver SHALL fall back to resolving via the Nominatim_Client with the query "{ICAO} airport"
4. THE Geocoder SHALL normalize ICAO codes to uppercase before resolution

### Requirement 8: Nominatim Free-Text Geocoding

**User Story:** As a station operator, I want to enter a city name or address as my weather location, so that the system resolves it to coordinates when I do not know a postcode or ICAO code.

#### Acceptance Criteria

1. WHEN a location code does not match any specific format (UK postcode, US ZIP, ICAO), THE Geocoder SHALL resolve the code as free text via the Nominatim_Client
2. THE Nominatim_Client SHALL query the OpenStreetMap Nominatim search API with the user-provided text and return the first result
3. THE Nominatim_Client SHALL enforce a minimum interval of 1 second between consecutive requests to comply with the Nominatim usage policy
4. THE Nominatim_Client SHALL include a descriptive User-Agent header ("APRSPropView/1.0") in all requests
5. IF the Nominatim API returns no results, THEN THE Nominatim_Client SHALL return None
6. WHEN the Nominatim API returns a display_name longer than 80 characters, THE Nominatim_Client SHALL truncate the name to 77 characters followed by "..."

### Requirement 9: Geocoding Resolution Chain

**User Story:** As a station operator, I want the system to automatically detect the format of my location input and route it to the correct geocoding service, so that I can enter a UK postcode, US ZIP, ICAO code, or place name without specifying the format.

#### Acceptance Criteria

1. THE Geocoder SHALL attempt resolution in the following order: UK postcode, US ZIP code, ICAO code, free-text Nominatim
2. WHEN a location code matches the UK postcode pattern, THE Geocoder SHALL route the code to the Postcodes_IO_Client and skip subsequent resolvers
3. WHEN a location code matches the US ZIP pattern (exactly five digits) and does not match the UK postcode pattern, THE Geocoder SHALL route the code to the ZIP resolver
4. WHEN a location code matches the ICAO pattern (four uppercase letters) and does not match earlier patterns, THE Geocoder SHALL route the code to the ICAO_Resolver
5. WHEN a location code does not match any specific pattern, THE Geocoder SHALL route the code to the Nominatim_Client as free text
6. IF the matched resolver returns no result, THEN THE Geocoder SHALL return None (it does not fall through to the next resolver)

### Requirement 10: Meteoalarm Alert Provider

**User Story:** As a UK/EU station operator, I want to receive severe weather alerts from Meteoalarm, so that I am warned about hazardous weather conditions in my area.

#### Acceptance Criteria

1. WHEN the effective region is "UK" or "EU", THE Alert_Factory SHALL return a Meteoalarm_Provider instance
2. WHEN the effective region is "US", THE Alert_Factory SHALL return an NWS_Provider instance
3. THE Meteoalarm_Provider SHALL fetch alerts from the Meteoalarm legacy Atom feed for the country determined from the station coordinates
4. THE Meteoalarm_Provider SHALL determine the country feed URL by mapping station coordinates to a country name using bounding-box geometry
5. THE Meteoalarm_Provider SHALL sort returned alerts with warnings before watches

### Requirement 11: CAP XML Alert Parsing

**User Story:** As a developer, I want Meteoalarm CAP/Atom feed entries parsed into the same normalized alert structure used by NWS alerts, so that the frontend can display alerts from both providers uniformly.

#### Acceptance Criteria

1. THE CAP_Parser SHALL extract event, severity, urgency, certainty, headline, description, area_desc, and geometry from each CAP `<info>` element
2. THE CAP_Parser SHALL map Meteoalarm severity levels to normalized alert types: "Extreme" and "Severe" map to "warning"; "Moderate" and "Minor" map to "watch"
3. IF a CAP `<info>` element has no event field, THEN THE CAP_Parser SHALL return None for that element
4. WHEN a severity level is not recognized, THE CAP_Parser SHALL default the alert type to "watch"
5. FOR ALL valid severity level inputs, THE CAP_Parser SHALL return an alert type that is either "warning" or "watch"

### Requirement 12: CAP Polygon to GeoJSON Conversion

**User Story:** As a frontend developer, I want CAP alert polygons converted to GeoJSON format, so that alert areas can be rendered as map overlays.

#### Acceptance Criteria

1. WHEN a CAP polygon string contains three or more valid coordinate pairs, THE CAP_Parser SHALL convert the polygon to a GeoJSON Polygon geometry object
2. THE CAP_Parser SHALL convert CAP coordinate format (lat,lon space-separated) to GeoJSON coordinate format ([lon, lat] arrays)
3. THE CAP_Parser SHALL close the polygon ring (first point equals last point) per the GeoJSON specification
4. WHEN a CAP polygon string is already closed (first point equals last point), THE CAP_Parser SHALL preserve the closure without duplicating the closing point
5. IF a CAP polygon string is empty, whitespace-only, or None, THEN THE CAP_Parser SHALL return None
6. IF a CAP polygon string contains fewer than three valid coordinate pairs, THEN THE CAP_Parser SHALL return None

### Requirement 13: Unit-Invariant Ducting Index

**User Story:** As a station operator, I want the ducting index to produce identical scores regardless of my display unit setting, so that switching between imperial and metric does not affect the ducting probability assessment.

#### Acceptance Criteria

1. THE Ducting_Calculator SHALL always request atmospheric data from Open-Meteo using Fahrenheit temperature units and mph wind speed units, regardless of the configured display unit system
2. THE Ducting_Calculator SHALL compute the ducting score using internal Fahrenheit/mb values, producing identical results for the same atmospheric conditions regardless of display units
3. THE Ducting_Calculator SHALL produce a ducting index value in the range 0 to 100 inclusive

### Requirement 14: Threshold-Based Ducting Cache

**User Story:** As a system operator, I want the ducting index to skip unnecessary API refetches when atmospheric conditions have not changed meaningfully, so that API usage is minimized without sacrificing accuracy.

#### Acceptance Criteria

1. WHEN the ducting refresh interval has elapsed and the absolute pressure change since the last fetch is less than 2.0 mb AND the absolute temperature change is less than 3.0°F, THE Weather_Manager SHALL return the cached ducting data without making a new API request
2. WHEN the absolute pressure change since the last fetch is 2.0 mb or greater, THE Weather_Manager SHALL fetch fresh ducting data from the API
3. WHEN the absolute temperature change since the last fetch is 3.0°F or greater, THE Weather_Manager SHALL fetch fresh ducting data from the API
4. THE Weather_Manager SHALL store the pressure and temperature values from each ducting fetch for comparison on the next cache check

### Requirement 15: Region-Aware Frontend Labels

**User Story:** As a station operator, I want the UI input placeholders and labels to reflect my detected region, so that I see relevant location format hints (e.g., "UK Postcode, ICAO, or Place Name" instead of "US Zip or ICAO").

#### Acceptance Criteria

1. WHEN the detected region is "US" or unset, THE frontend SHALL display location input placeholder text referencing US ZIP codes and ICAO codes
2. WHEN the detected region is "UK" or "EU", THE frontend SHALL display location input placeholder text referencing UK postcodes, ICAO codes, and place names
3. WHEN a weather API response includes a region value, THE frontend SHALL call the label update function to adapt UI text to the detected region
4. THE frontend SHALL use the `unit_labels` dictionary from weather API responses to display correct unit suffixes for temperature, wind speed, and precipitation values
