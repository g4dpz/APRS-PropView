# Implementation Plan: ML Propagation Service

## Overview

Build a standalone ML-based propagation prediction service (`ml_service/`) that runs as an independent Python/FastAPI process alongside PropView. Implementation proceeds from foundational components (config, feature pipeline, model store) through training and prediction, then API routes, and finally PropView integration. Each component is tested alongside its implementation. The implementation language is Python, matching the existing PropView codebase and the design document.

## Tasks

- [ ] 1. Set up ML Service project structure and configuration
  - [ ] 1.1 Create `ml_service/` directory with `__init__.py`, `main.py`, `requirements.txt`, and `requirements-dev.txt`
    - Create `ml_service/requirements.txt` with: fastapi, uvicorn, xgboost>=2.0, scikit-learn>=1.4, pandas>=2.0, joblib>=1.3, httpx>=0.25, tomli (for Python <3.11)
    - Create `ml_service/requirements-dev.txt` with: pytest>=8.0, pytest-asyncio>=0.23, hypothesis>=6.100
    - Create `ml_service/__init__.py` (empty)
    - Create a minimal `ml_service/main.py` placeholder with `create_app()` and `main()` stubs
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ] 1.2 Implement `ml_service/config.py` with `MLServiceConfig` dataclass
    - Implement `MLServiceConfig` dataclass with fields: `host`, `port`, `propview_db_path`, `model_type`, `retrain_schedule`, `model_store_path`, `min_data_days`, `log_level`, `alignment_window_seconds`
    - Implement `load(path)` static method to parse TOML config file
    - Implement `create_default(path)` static method to write default `config.toml`
    - Implement `validate()` method returning list of error messages for invalid values (port range [1, 65535], model_type in {xgboost, lstm}, retrain_schedule in {daily, weekly}, min_data_days >= 1, log_level in {debug, info, warning, error})
    - If config file does not exist at startup, create default and proceed
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 1.3 Write property tests for configuration (Properties 10, 11)
    - **Property 10: Configuration round-trip preserves values** — Generate random valid `MLServiceConfig` values (host as non-empty string, port in [1, 65535], model_type in {xgboost, lstm}, retrain_schedule in {daily, weekly}, min_data_days >= 1, log_level in {debug, info, warning, error}). Write to TOML, load back, verify equivalence.
    - **Property 11: Configuration validation catches invalid values** — Generate configs with port outside [1, 65535], or invalid model_type, or invalid retrain_schedule, or min_data_days < 1. Verify `validate()` returns non-empty error list.
    - **Validates: Requirements 9.1, 9.3**

  - [ ]* 1.4 Write unit tests for configuration
    - Test default file creation when config file is missing
    - Test all default values are correct
    - Test loading a valid config file
    - Test validation error messages for each invalid field
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement Feature Extraction Pipeline
  - [ ] 3.1 Implement `ml_service/feature_pipeline.py` with `FeatureVector` and `FeaturePipeline`
    - Implement `FeatureVector` dataclass with all 13 feature fields (`hour_of_day`, `day_of_week`, `month`, `ducting_index`, `pressure_trend`, `humidity`, `temp_f`, `rf_station_count`, `max_distance_km`, `avg_distance_km`, `unique_stations_1h`, `dx_spot_rate_1h`, `inversion_detected`), `to_array()`, and `feature_names()` static method
    - Implement `FeaturePipeline.__init__()` accepting `db_path` and `alignment_window_seconds`
    - Implement `_open_readonly()` to open PropView's SQLite DB with `?mode=ro` URI and `PRAGMA query_only = ON`, with exponential backoff retry (1s, 2s, 4s) on locked database, max 3 attempts
    - Implement `extract_training_data(min_days)` that:
      - Queries `propagation_log`, `ducting_log`, `dx_spots` tables
      - Joins rows using timestamp alignment within the configured window
      - Derives time features (hour_of_day, day_of_week, month) from timestamps
      - Computes `dx_spot_rate_1h` from dx_spots count
      - Applies column-specific imputation: median for atmospheric fields (`ducting_index`, `pressure_trend`, `humidity`, `temp_f`), zero for count fields (`rf_station_count`, `max_distance_km`, `avg_distance_km`, `unique_stations_1h`, `dx_spot_rate_1h`, `inversion_detected`), forward-fill for time-series fields
      - Computes `target_score` using same logic as PropView's `compute_historical_score` (weighted combination of station count and max distance, clamped to [0, 100])
      - Returns DataFrame with 13 feature columns + target_score, or None if insufficient data
    - Implement `extract_current_features()` returning the most recent `FeatureVector` or None
    - Implement `get_data_coverage_days()` returning days of data in propagation_log
    - Skip corrupt/unexpected rows with WARNING log, continue processing
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.2 Write property tests for feature pipeline (Properties 1, 2, 3, 4)
    - **Property 1: Feature extraction produces complete feature vectors** — Generate random valid DB rows for propagation_log, ducting_log, dx_spots. Insert into in-memory SQLite. Run `extract_training_data()`. Verify all 13 feature columns + target_score present with no unexpected columns missing.
    - **Property 2: Timestamp alignment joins rows within window and excludes rows outside** — Generate pairs of timestamps with random offsets and a positive alignment window. Verify rows within window are joined, rows outside are treated as missing (subject to imputation).
    - **Property 3: Imputation produces no NaN values and follows column-specific rules** — Generate DataFrames with random NaN patterns. Apply imputation. Verify no NaN remains, atmospheric columns filled with median, count columns filled with zero.
    - **Property 4: Target score is bounded to [0, 100]** — Generate random rf_station_count (>= 0) and max_distance_km (>= 0). Compute target score. Verify result in [0, 100].
    - **Validates: Requirements 2.2, 2.3, 2.4, 3.2**

  - [ ]* 3.3 Write unit tests for feature pipeline
    - Test read-only database connection verification (PRAGMA query_only)
    - Test retry behavior on locked database (mock file lock)
    - Test corrupt row handling (skip and continue)
    - Test imputation with fully missing atmospheric columns
    - Test extract_current_features returns None when DB inaccessible
    - Test get_data_coverage_days with empty and populated tables
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6_

- [ ] 4. Implement Model Store
  - [ ] 4.1 Implement `ml_service/model_store.py` with `ModelMetadata` and `ModelStore`
    - Implement `ModelMetadata` dataclass with: version, model_type, training_timestamp, data_date_range, data_row_count, feature_names, metrics (ValidationMetrics), file_path
    - Implement `ModelStore.__init__(store_path)` creating the directory if needed
    - Implement `save_model(model, metadata, model_type)` — save XGBoost via joblib, LSTM via PyTorch checkpoint, write `model_metadata.json` alongside artifact
    - Implement `load_latest()` — find most recent valid model artifact and metadata, return tuple or None
    - Implement `cleanup(keep=2)` — delete all but the `keep` most recent versions, return list of deleted version strings
    - Implement `get_metadata()` — return metadata for currently loaded model
    - Version format: `YYYYMMDD_HHMMSS` timestamp string
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 4.2 Write property test for model store cleanup (Property 12)
    - **Property 12: Model store cleanup retains exactly the most recent versions** — Generate random lists of n model versions (n >= 0) with distinct timestamps. Call `cleanup(keep=2)`. Verify store contains exactly `min(n, 2)` versions and they are the two most recent.
    - **Validates: Requirements 10.3**

  - [ ]* 4.3 Write unit tests for model store
    - Test load_latest returns None with empty store
    - Test save and load round-trip for XGBoost model
    - Test metadata JSON file creation and content
    - Test cleanup deletes oldest versions, keeps 2 most recent
    - Test degraded state: startup with no model artifact
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Training Pipeline
  - [ ] 6.1 Implement `ml_service/training_pipeline.py` with `ValidationMetrics`, `TrainingResult`, and `TrainingPipeline`
    - Implement `ValidationMetrics` dataclass with rmse, mae, r_squared
    - Implement `TrainingResult` dataclass with success, metrics, model_version, data_rows, data_date_range, duration_seconds, error_message
    - Implement `TrainingPipeline.__init__()` accepting feature_pipeline, model_store, config
    - Implement `train()` async method that:
      - Calls `feature_pipeline.extract_training_data(min_days=config.min_data_days)`
      - Returns failure result if insufficient data
      - Runs `_time_series_split()` with minimum 3 folds
      - Trains model via `_train_xgboost()` or `_train_lstm()` based on config.model_type
      - Validates via `_validate()` computing RMSE, MAE, R²
      - If new RMSE > 1.5× previous model's RMSE, logs warning and retains previous model
      - On success, saves model + metadata to model_store and runs cleanup
      - Executes in thread pool to avoid blocking event loop
    - Implement `_train_xgboost(X_train, y_train)` using XGBRegressor
    - Implement `_train_lstm(X_train, y_train)` using PyTorch (lightweight LSTM)
    - Implement `_validate(model, X_val, y_val)` computing RMSE, MAE, R²
    - Implement `_time_series_split(df, n_splits=3)` using sklearn TimeSeriesSplit, ensuring no future data leakage (max(train_timestamps) < min(val_timestamps) for every fold)
    - On training failure, log at ERROR and retain previous model without overwriting
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.4_

  - [ ]* 6.2 Write property tests for training pipeline (Properties 5, 6, 8)
    - **Property 5: Time-series cross-validation splits have no future data leakage** — Generate sorted timestamp sequences and n_splits >= 3. Apply `_time_series_split()`. Verify `max(train_timestamps) < min(val_timestamps)` for every fold.
    - **Property 6: Validation metrics satisfy mathematical bounds** — Generate random prediction/actual arrays of equal length (>= 1). Compute RMSE, MAE, R². Verify RMSE >= 0, MAE >= 0, R² <= 1, MAE <= RMSE.
    - **Property 8: Model replacement guard rejects degraded models** — Generate random positive RMSE pairs (old_rmse, new_rmse). Verify old model retained when `new_rmse > 1.5 * old_rmse`, new model accepted when `new_rmse <= 1.5 * old_rmse`.
    - **Validates: Requirements 3.3, 3.4, 5.4**

  - [ ]* 6.3 Write unit tests for training pipeline
    - Test XGBoost vs LSTM selection based on config.model_type
    - Test model artifact and metadata file creation after successful training
    - Test insufficient data returns TrainingResult(success=False)
    - Test training failure retains previous model
    - Test validation metrics computation with known inputs
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 7. Implement Prediction Service
  - [ ] 7.1 Implement `ml_service/prediction_service.py` with `HourlyForecast`, `PredictionResponse`, and `PredictionService`
    - Implement `HourlyForecast` dataclass with hours_ahead, predicted_score, opening_probability, timestamp, confidence
    - Implement `PredictionResponse` dataclass with ready, score, opening_probability, confidence, model_version, features_used, forecast, message
    - Implement `PredictionService.__init__()` accepting feature_pipeline, model_store, config
    - Implement `predict(horizon_hours=12)` that:
      - Returns ready=False with message if no trained model available
      - Returns ready=False with data coverage info if < min_data_days
      - Extracts current features via feature_pipeline
      - If DB inaccessible, returns cached prediction or ready=False
      - Runs model inference, clamps score to [0, 100]
      - Computes opening_probability from score (0.0–1.0)
      - Computes confidence from prediction interval width and data recency
      - Generates hourly forecast via `_generate_forecast()`
      - Caches successful prediction
    - Implement `_compute_confidence(prediction_std, data_recency_hours)` returning "low", "medium", or "high"
    - Implement `_generate_forecast(model, base_features, horizon)` that shifts time features forward hour by hour, generates predictions, returns list of HourlyForecast with ascending hours_ahead from 1 to horizon, scores in [0, 100], probabilities in [0.0, 1.0]
    - Implement `get_cached()` returning last successful prediction or None
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 14.1, 14.2, 14.3, 14.4, 15.1_

  - [ ]* 7.2 Write property tests for prediction service (Properties 7, 9, 13)
    - **Property 7: Data threshold determines prediction readiness** — Generate random `days_available` and `min_data_days`. Verify `ready=True` iff `days_available >= min_data_days`, `ready=False` otherwise.
    - **Property 9: Horizon parameter validation accepts [1, 24] and rejects outside** — Generate random integers. Verify [1, 24] accepted, outside rejected with validation error.
    - **Property 13: Forecast structure invariants** — Generate random horizons [1, 24]. Generate forecasts. Verify length equals horizon, all required fields present (`hours_ahead`, `predicted_score`, `opening_probability`, `timestamp`, `confidence`), hours_ahead strictly ascending from 1 to h, predicted_score in [0, 100], opening_probability in [0.0, 1.0].
    - **Validates: Requirements 4.1, 4.2, 6.2, 14.1, 14.2, 14.3, 15.3**

  - [ ]* 7.3 Write unit tests for prediction service
    - Test 503-equivalent response when no model available
    - Test cached result returned on DB failure
    - Test prediction includes features_used and model_version
    - Test confidence computation with known inputs
    - Test forecast generation produces correct number of entries
    - _Requirements: 6.1, 6.4, 6.5, 6.6, 6.7, 14.1, 15.1_

- [ ] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Retrain Scheduler
  - [ ] 9.1 Implement `ml_service/scheduler.py` with `RetrainScheduler`
    - Implement `RetrainScheduler.__init__()` accepting training_pipeline and schedule ("daily" or "weekly")
    - Implement `start()` to launch background asyncio task that triggers training at the configured interval (daily = 24h, weekly = 168h)
    - Implement `stop()` to cancel the background task
    - Implement `is_training` property returning whether a training run is in progress
    - Implement `last_training_time` property returning Unix timestamp of last completed training
    - Implement `next_training_time` property returning Unix timestamp of next scheduled training
    - Retraining runs in background and does not block `/predict` endpoint
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [ ]* 9.2 Write unit tests for retrain scheduler
    - Test daily vs weekly interval calculation
    - Test is_training flag during active training
    - Test last_training_time and next_training_time properties
    - Test stop cancels background task
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [ ] 10. Implement REST API Routes and Wire Up FastAPI App
  - [ ] 10.1 Implement `ml_service/routes.py` with all API endpoints
    - Implement `create_router()` accepting prediction_service, training_pipeline, model_store, scheduler, config
    - `GET /predict?horizon_hours=12`:
      - Accept optional `horizon_hours` query param (1–24, default 12)
      - Return 422 for invalid horizon_hours
      - Return 503 when no model trained
      - Return PredictionResponse JSON on success within 500ms
    - `POST /train`:
      - Return 409 if training already in progress
      - Return 202 with job_id and estimated_duration_seconds
      - Execute training asynchronously
    - `GET /status`:
      - Return 200 always (reflects service health, not model readiness)
      - Include: uptime, model_version, model_ready, last/next training timestamps, data coverage, min threshold, validation metrics
    - `GET /health`:
      - Return 200 with `{"status": "ok"}` when service is running
    - Add global exception handler returning 500 with generic error message, no internal details exposed
    - _Requirements: 6.1, 6.2, 6.3, 6.7, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 15.3, 15.4, 15.5_

  - [ ] 10.2 Wire up `ml_service/main.py` — complete the FastAPI app factory
    - Load config from `ml_service/config.toml` (create default if missing)
    - Validate config at startup, log errors for invalid settings
    - Initialize FeaturePipeline, ModelStore, TrainingPipeline, PredictionService, RetrainScheduler
    - Load latest model from ModelStore at startup (degraded state if none exists)
    - Register routes via `create_router()`
    - Start RetrainScheduler on app startup event
    - Stop RetrainScheduler on app shutdown event
    - Configure logging based on config.log_level
    - Run uvicorn with configured host and port
    - _Requirements: 1.1, 1.2, 1.3, 9.1, 9.4, 10.4, 10.5, 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 10.3 Write unit tests for API routes
    - Test `/health` returns 200 with `{"status": "ok"}`
    - Test `/train` returns 409 when training in progress
    - Test `/train` returns 202 with job_id
    - Test `/status` returns 200 with all required fields (uptime, model_version, model_ready, data_days_available, min_data_days_required, latest_metrics, etc.)
    - Test `/predict` returns features_used and model_version on success
    - Test `/predict` returns 503 when no model available
    - Test `/predict` returns 422 for invalid horizon_hours
    - Test global exception handler returns 500 without internal details
    - _Requirements: 6.1, 6.7, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 15.3, 15.4, 15.5_

- [ ] 11. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. PropView Integration — Config and ML Service Client
  - [ ] 12.1 Add `ml_service_url` field to PropView's `PredictionConfig` in `server/config.py`
    - Add `ml_service_url: str = ""` to the `PredictionConfig` dataclass (note: PropView currently has no `PredictionConfig` — add it or extend the existing config structure)
    - Add `ml_service_url` to the `[prediction]` section in `DEFAULT_CONFIG`
    - Add serialization of `ml_service_url` in `Config.save()` under the `[prediction]` section
    - _Requirements: 11.1, 11.4_

  - [ ] 12.2 Implement `MLServiceClient` and `MLPrediction` in `server/prediction.py`
    - Add `MLPrediction` dataclass with: score, opening_probability, confidence, model_version, forecast, features_used
    - Add `MLServiceClient` class with:
      - `__init__(base_url, timeout=2.0)` — store base URL and timeout
      - `get_prediction(horizon_hours=12)` — async method calling `GET /predict?horizon_hours=...` via httpx.AsyncClient with 2-second timeout, returns `MLPrediction` on success or `None` on any failure (connection refused, timeout, HTTP error, malformed JSON), logs failures at WARNING
      - `close()` — close the underlying httpx client
    - No retries within a single call
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 12.3 Integrate `MLServiceClient` into `PredictionEngine`
    - In `PredictionEngine.__init__()`, create `MLServiceClient` if `config.prediction.ml_service_url` is non-empty
    - In `PredictionEngine.refresh()`, after computing heuristic score:
      - If ml_service_url is configured, call `MLServiceClient.get_prediction()`
      - If ML prediction returned, attach as `ml_prediction` field on `PredictionResult`
      - If ML prediction is None (any failure), set `ml_prediction = None` and use heuristic only
    - Add `ml_prediction` field to `PredictionResult` dataclass (Optional[MLPrediction], default None)
    - Add `source` field to `PredictionResult` dataclass (str: "heuristic", "ml", or "blended")
    - In `PredictionEngine.stop()`, close the MLServiceClient
    - When ml_service_url is empty, skip ML integration entirely — no HTTP calls, no warnings
    - _Requirements: 11.2, 11.3, 12.1, 12.2, 12.3, 12.4, 12.5, 13.4_

- [ ] 13. PropView Integration — API Response Changes
  - [ ] 13.1 Update PropView's `/api/prediction` route to include ML prediction data
    - When `ml_prediction` is available on PredictionResult, include `ml_prediction` object in response JSON with: score, opening_probability, confidence, model_version, forecast array
    - When `ml_prediction` is None, include `ml_prediction: null` in response
    - Add `source` field to response indicating "heuristic", "ml", or "blended"
    - _Requirements: 13.1, 13.2, 13.4_

  - [ ] 13.2 Update PropView's WebSocket prediction push to include ML prediction data
    - Include `ml_prediction` field in WebSocket push message with same structure as REST response
    - _Requirements: 13.3_

  - [ ]* 13.3 Write integration tests for PropView ML integration
    - Test MLServiceClient with mock ML Service: successful response includes ML score
    - Test MLServiceClient with unreachable service: returns None, heuristic-only fallback
    - Test MLServiceClient with slow service (>2s): timeout triggers fallback
    - Test MLServiceClient with HTTP error response: returns None
    - Test `/api/prediction` response includes `ml_prediction` when available
    - Test `/api/prediction` response has `ml_prediction: null` when unavailable
    - Test `/api/prediction` response includes `source` field
    - Test WebSocket push includes `ml_prediction` field
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2, 13.3, 13.4_

- [ ] 14. Implement ML Service Logging
  - [ ] 14.1 Add structured logging throughout the ML Service
    - Configure logging in `main.py` based on `config.log_level`
    - Log training start, completion, and failure at INFO level with duration and validation metrics
    - Log prediction requests at DEBUG level with input feature summary and response time
    - Log database access errors at WARNING level with table and operation details
    - Log model loading events at INFO level with model version and file path
    - Log unhandled exceptions at ERROR level
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [ ] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major component
- Property tests validate the 13 universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The ML Service has zero import dependencies on PropView's `server/` package
- PropView integration is additive — existing heuristic prediction is never removed or degraded
