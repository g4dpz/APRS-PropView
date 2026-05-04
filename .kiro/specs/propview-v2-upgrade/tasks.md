# Implementation Plan: PropView v2 Upgrade

## Overview

This plan implements targeted, backward-compatible improvements to APRS PropView covering SQLite WAL mode, threshold-based ducting cache invalidation, composite database indexes, configurable WebSocket connection limits, configurable message history limits, and configuration persistence/migration. All changes are additive — no breaking changes to existing behavior.

## Tasks

- [ ] 1. Database optimizations — WAL mode and composite indexes
  - [ ] 1.1 Enable SQLite WAL mode in `Database.initialize()`
    - In `server/database.py`, update the `initialize()` method to execute `PRAGMA journal_mode=WAL` immediately after `aiosqlite.connect()` and before `executescript(SCHEMA)`
    - Log the active journal mode at info level on success
    - Log a warning and continue if WAL mode fails to activate
    - No config changes required — WAL is unconditional
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 1.2 Add composite indexes to the database schema
    - Append two new `CREATE INDEX IF NOT EXISTS` statements to the `SCHEMA` string in `server/database.py`
    - Add `idx_packets_source_timestamp_from` on `packets(source, timestamp, from_call)`
    - Add `idx_path_history_callsign_timestamp` on `path_history(callsign, timestamp)`
    - Preserve all existing indexes without modification
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 1.3 Write unit tests for WAL mode and composite indexes
    - Create `tests/test_database.py`
    - Test that WAL mode is active after `initialize()` by querying `PRAGMA journal_mode`
    - Test that both composite indexes exist after initialization by querying `sqlite_master`
    - Test idempotent re-initialization (call `initialize()` twice, verify no errors)
    - Test that all existing single-column indexes are preserved
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.1, 3.2, 3.3, 3.4_

- [ ] 2. Threshold-based ducting cache invalidation
  - [ ] 2.1 Extract pure threshold decision function and update `WeatherManager.get_ducting()`
    - In `server/weather.py`, add `_last_ducting_pressure` and `_last_ducting_temp` instance variables to `WeatherManager.__init__()`, initialized to `None`
    - Add the pure function `_should_refetch_ducting(prev_pressure, curr_pressure, prev_temp, curr_temp)` at module level
    - Returns `True` if `|pressure_diff| >= 2.0` OR `|temp_diff| >= 3.0`, or if any previous value is `None`
    - Update `get_ducting()` to check thresholds after the time-based cache check: if time has elapsed but thresholds are not met, return cached data and reset the timer
    - When `force=True`, bypass both time and threshold checks
    - Store pressure and temperature from each successful fetch for subsequent comparisons
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 2.2 Write property test for ducting cache threshold decision
    - Update `tests/test_ducting_cache.py` to import `_should_refetch_ducting` from `server.weather` instead of the local `should_refetch` function
    - Update the existing property tests to test the actual implementation function
    - Verify the existing boundary tests still pass against the real function
    - **Property 1: Ducting cache threshold decision is correct**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Configurable WebSocket connection limit
  - [ ] 4.1 Add `max_websocket_connections` to `WebConfig` and update `WebSocketManager`
    - In `server/config.py`, add `max_websocket_connections: int = 20` field to the `WebConfig` dataclass
    - In `server/websocket_manager.py`, change `WebSocketManager.__init__()` to accept a `max_connections: int = 20` parameter
    - Store as `self.max_connections` and use it in `connect()` instead of the `MAX_CONNECTIONS` class constant
    - Remove the `MAX_CONNECTIONS = 20` class constant
    - Reject connections at capacity with close code 1013
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.2 Wire the config value to `WebSocketManager` at startup
    - In `main.py`, update `WebSocketManager()` instantiation to pass `max_connections=config.web.max_websocket_connections`
    - _Requirements: 4.4_

  - [ ]* 4.3 Write property test for WebSocket connection limit enforcement
    - Create `tests/test_websocket_manager.py`
    - Use Hypothesis to generate random `max_connections` values in [1, 100]
    - Verify that exactly N connections are accepted and the (N+1)th is rejected with code 1013
    - **Property 2: WebSocket connection limit enforcement**
    - **Validates: Requirements 4.2**

- [ ] 5. Configurable message history limit
  - [ ] 5.1 Add `max_message_history` to `WebConfig` and update `PacketHandler`
    - In `server/config.py`, add `max_message_history: int = 500` field to the `WebConfig` dataclass
    - In `server/packet_handler.py`, update `PacketHandler.__init__()` to read `config.web.max_message_history` and use it as the `maxlen` for the `_messages` deque
    - Remove the module-level `MAX_MESSAGE_HISTORY = 500` constant
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 5.2 Write property test for message history deque maxlen
    - In `tests/test_packet_handler.py`, add Hypothesis property tests
    - Generate random `max_message_history` values in [1, 10000] and insert M+K messages
    - Verify deque length is exactly M and oldest K messages are evicted
    - **Property 3: Message history deque respects configured maxlen**
    - **Validates: Requirements 5.2**

- [ ] 6. Configuration persistence and migration
  - [ ] 6.1 Update `Config.save()` to write new fields
    - In `server/config.py`, add `region: str = "auto"` and `units: str = "imperial"` fields to `WeatherConfig`
    - Update the `save()` method's `[web]` section to write `max_websocket_connections` and `max_message_history`
    - Update the `save()` method's `[weather]` section to write `region` and `units`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 6.2 Update `DEFAULT_CONFIG` template with commented examples for new fields
    - Add commented examples for `max_websocket_connections`, `max_message_history`, `region`, and `units` to the `DEFAULT_CONFIG` string in `server/config.py`
    - Use commented-out format (e.g., `# max_websocket_connections = 20`) to keep defaults minimal
    - _Requirements: 6.7_

  - [ ]* 6.3 Write property test for config save/load round-trip
    - Create `tests/test_config.py`
    - Use Hypothesis to generate valid Config objects with randomized new field values (`region` in {"auto", "US", "UK", "EU"}, `units` in {"imperial", "metric"}, `max_websocket_connections` in [1, 100], `max_message_history` in [1, 10000])
    - Save to a temp TOML file and load back, verify all field values are identical
    - **Property 4: Config save/load round-trip preserves new fields**
    - **Validates: Requirements 6.5**

  - [ ]* 6.4 Write unit tests for backward compatibility defaults
    - In `tests/test_config.py`, test that loading a config.toml missing all new fields produces correct defaults: `region="auto"`, `units="imperial"`, `max_websocket_connections=20`, `max_message_history=500`
    - Test that the DEFAULT_CONFIG template includes commented examples for all new fields
    - Test that WAL mode and composite indexes apply automatically (covered by task 1.3, cross-reference here)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.7, 6.8, 6.9_

- [ ] 7. Integration wiring and final verification
  - [ ] 7.1 Verify all components are wired together correctly
    - Confirm `main.py` passes `max_connections` to `WebSocketManager`
    - Confirm `PacketHandler` reads `max_message_history` from config
    - Confirm `Database.initialize()` enables WAL and creates composite indexes
    - Confirm `WeatherManager.get_ducting()` uses threshold-based cache invalidation
    - Confirm `Config.save()` writes all new fields
    - Confirm no orphaned constants (`MAX_CONNECTIONS`, `MAX_MESSAGE_HISTORY`) remain
    - _Requirements: 1.4, 2.6, 3.3, 4.4, 5.4, 6.5, 6.8, 6.9_

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples, edge cases, and integration points
- The existing `tests/test_ducting_cache.py` already contains Hypothesis property tests for the threshold logic — task 2.2 updates them to test the actual implementation function
