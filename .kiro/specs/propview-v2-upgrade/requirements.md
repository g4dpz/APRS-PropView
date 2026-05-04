# Requirements Document

## Introduction

APRS PropView has several performance and configurability improvements available as easy wins. This specification covers targeted, backward-compatible improvements to SQLite performance, weather API efficiency, analytics query speed, and operational configurability.

Note: UK/EU region support (region detection, Meteoalarm alerts, multi-format geocoding, metric units, callsign validation, and region-aware UI) is specified separately in the uk-eu-internationalization spec.

## Glossary

- **Database**: The `Database` class in `server/database.py` that manages the SQLite connection and all table operations via `aiosqlite`
- **WAL_Mode**: SQLite Write-Ahead Logging journal mode, which allows concurrent readers and a single writer without blocking
- **AnalyticsEngine**: The `AnalyticsEngine` class in `server/analytics.py` that runs aggregation queries joining `packets`, `stations`, and `path_history` tables
- **Composite_Index**: A SQLite index spanning multiple columns, optimized for queries that filter or sort on those columns together
- **Config**: The root `Config` dataclass in `server/config.py` that loads all configuration sections from `config.toml`
- **WebSocketManager**: The `WebSocketManager` class in `server/websocket_manager.py` that manages browser WebSocket connections and broadcasts real-time updates
- **PacketHandler**: The `PacketHandler` class in `server/packet_handler.py` that routes packets between RF, APRS-IS, digipeater, IGate, and the station tracker
- **Cache_Threshold**: A minimum change in a weather measurement (pressure or temperature) required to trigger a fresh API fetch, as opposed to purely time-based expiration
- **Ducting_Index**: A computed 0–100 score estimating VHF tropospheric ducting probability, derived from pressure, temperature, humidity, and wind data
- **WeatherManager**: The existing orchestrator in `server/weather.py` that coordinates weather data fetching, caching, and delivery to the frontend
- **Open_Meteo**: The free global weather API already used by PropView for current conditions and ducting index data

---

## Part A: Codebase Optimizations

### Requirement 1: Enable SQLite WAL Mode

**User Story:** As an operator running APRS PropView, I want the SQLite database to use WAL journal mode, so that analytics queries do not block packet logging and vice versa.

#### Acceptance Criteria

1. WHEN the Database initializes a connection, THE Database SHALL execute `PRAGMA journal_mode=WAL` before any other database operations
2. WHEN WAL mode is successfully enabled, THE Database SHALL log the active journal mode at the info level
3. IF the `PRAGMA journal_mode=WAL` command fails to set WAL mode, THEN THE Database SHALL log a warning and continue operation with the default journal mode
4. THE Database SHALL enable WAL mode without requiring any changes to `config.toml` or user intervention

### Requirement 2: Threshold-Based Ducting Cache Invalidation

**User Story:** As an operator, I want the ducting index to skip unnecessary API refetches when atmospheric conditions have not meaningfully changed, so that Open-Meteo API calls are reduced.

#### Acceptance Criteria

1. WHEN the ducting cache refresh interval has elapsed AND the previous pressure reading differs from the current pressure reading by less than 2 mb AND the previous temperature reading differs from the current temperature reading by less than 3°F, THE WeatherManager SHALL return the cached ducting data without making an API call
2. WHEN the ducting cache refresh interval has elapsed AND the previous pressure reading differs from the current pressure reading by 2 mb or more, THE WeatherManager SHALL fetch fresh ducting data from the Open-Meteo API
3. WHEN the ducting cache refresh interval has elapsed AND the previous temperature reading differs from the current temperature reading by 3°F or more, THE WeatherManager SHALL fetch fresh ducting data from the Open-Meteo API
4. WHEN a forced refresh is requested via the `force=True` parameter, THE WeatherManager SHALL fetch fresh ducting data regardless of threshold checks
5. WHEN no previous ducting data exists in the cache, THE WeatherManager SHALL fetch fresh ducting data from the Open-Meteo API
6. THE WeatherManager SHALL store the pressure and temperature values from each successful ducting fetch for use in subsequent threshold comparisons

### Requirement 3: Composite Database Indexes for Analytics Queries

**User Story:** As an operator viewing analytics dashboards, I want heatmap and historical queries to execute faster, so that the web UI remains responsive under load.

#### Acceptance Criteria

1. THE Database SHALL create a composite index on `packets(source, timestamp, from_call)` during schema initialization
2. THE Database SHALL create a composite index on `path_history(callsign, timestamp)` during schema initialization
3. THE Database SHALL use `CREATE INDEX IF NOT EXISTS` for all new composite indexes to ensure safe re-execution on existing databases
4. THE Database SHALL preserve all existing indexes without modification

### Requirement 4: Configurable WebSocket Connection Limit

**User Story:** As an operator, I want to configure the maximum number of simultaneous WebSocket connections, so that I can tune resource usage for my hardware.

#### Acceptance Criteria

1. THE Config SHALL support a `max_websocket_connections` field in the `[web]` section of `config.toml` with a default value of 20
2. WHEN a new WebSocket connection is attempted AND the number of active connections equals or exceeds the configured `max_websocket_connections` value, THE WebSocketManager SHALL reject the connection with close code 1013
3. WHEN `max_websocket_connections` is not present in `config.toml`, THE WebSocketManager SHALL use the default value of 20
4. THE WebSocketManager SHALL read the connection limit from the Config at initialization rather than using a hardcoded class constant

### Requirement 5: Configurable Message History Limit

**User Story:** As an operator, I want to configure the maximum number of APRS messages kept in memory, so that I can balance memory usage against message recall depth.

#### Acceptance Criteria

1. THE Config SHALL support a `max_message_history` field in the `[web]` section of `config.toml` with a default value of 500
2. WHEN the PacketHandler is initialized, THE PacketHandler SHALL create the message history deque with a `maxlen` equal to the configured `max_message_history` value
3. WHEN `max_message_history` is not present in `config.toml`, THE PacketHandler SHALL use the default value of 500
4. THE PacketHandler SHALL read the message history limit from the Config at initialization rather than using a hardcoded module-level constant

---

## Part B: Backward Compatibility

### Requirement 6: Configuration Persistence and Migration

**User Story:** As an existing operator upgrading APRS PropView, I want my current configuration to continue working without changes and all optimizations to apply automatically.

#### Acceptance Criteria

1. WHEN the `region` field is absent from `config.toml`, THE Config loader SHALL default to "auto" region detection
2. WHEN the `units` field is absent from `config.toml`, THE Config loader SHALL default to "imperial" for US region and "metric" for UK/EU regions
3. WHEN an existing `config.toml` lacks the `max_websocket_connections` field, THE Config SHALL use the default value of 20
4. WHEN an existing `config.toml` lacks the `max_message_history` field, THE Config SHALL use the default value of 500
5. THE Config save method SHALL write the new `region`, `units`, `max_websocket_connections`, and `max_message_history` fields to `config.toml` in their respective sections
6. WHEN an existing configuration with only a US ZIP code as `location_code` is loaded, THE Weather_Manager SHALL continue to resolve the location using the existing Zippopotam API without any user action required
7. THE default `config.toml` template SHALL include commented examples showing all new fields with their allowed values
8. THE Database SHALL apply WAL mode and new composite indexes automatically on startup without requiring manual migration steps
9. THE WeatherManager SHALL apply threshold-based cache invalidation automatically without requiring new configuration fields
