# Requirements Document

## Introduction

A standalone ML-based propagation prediction service that runs alongside the existing APRS PropView application. The ML_Service is a separate Python/FastAPI project living in its own directory (`ml_service/`) with independent dependencies. It reads PropView's SQLite database to extract historical propagation data, trains time-series models (XGBoost or lightweight LSTM), and exposes REST API endpoints for propagation score prediction (0–100) and opening probability over a 1–24 hour horizon. PropView's existing PredictionEngine integrates with the ML_Service via a configurable HTTP client, falling back gracefully to its heuristic scoring when the ML_Service is unavailable. The ML_Service requires approximately 30 days of accumulated local data before producing useful predictions, retrains periodically (daily or weekly), and stores trained models as local files.

## Glossary

- **ML_Service**: The standalone Python/FastAPI application that trains and serves ML-based propagation predictions, running as a separate process from PropView on a configurable port
- **PropView**: The existing APRS PropView Python/FastAPI application that provides heuristic propagation prediction, station tracking, and related features
- **Prediction_Engine**: The existing module in PropView (`server/prediction.py`) that computes a heuristic 0–100 prediction score from six weighted contributing factors
- **Feature_Pipeline**: The data extraction and transformation component within the ML_Service that reads raw PropView database tables and produces numeric feature vectors suitable for model training and inference
- **Feature_Vector**: A structured set of numeric input values derived from PropView data, including hour of day, day of week, month, ducting index, pressure trend, humidity, wind speed, recent station count, recent max distance, DX spot rate, and solar indices
- **Propagation_Score**: A numeric value from 0 to 100 representing the ML model's predicted likelihood and strength of a VHF band opening
- **Opening_Probability**: A value from 0.0 to 1.0 representing the ML model's estimated probability that a propagation opening will occur within a given future time window
- **Prediction_Horizon**: The forward-looking time range (1 to 24 hours) over which the ML_Service generates predictions
- **Model_Store**: The local directory where the ML_Service persists trained model artifacts (pickle, joblib, or ONNX files) and associated metadata
- **Training_Pipeline**: The component within the ML_Service that orchestrates feature extraction, model fitting, validation, and artifact storage during a training run
- **Retraining_Schedule**: The configurable periodic interval (daily or weekly) at which the ML_Service automatically retrains its model using the latest available data
- **PropView_Database**: The SQLite database file (`propview.db`) containing tables propagation_log, ducting_log, dx_spots, prediction_history, stations, and packets, shared between PropView and the ML_Service via filesystem access
- **Heuristic_Score**: The existing 0–100 prediction score computed by PropView's PredictionEngine using weighted contributing factors without ML
- **ML_Integration_Client**: A thin HTTP client layer added to PropView's PredictionEngine that calls the ML_Service's `/predict` endpoint during each refresh cycle
- **Blended_Score**: An optional combined score that merges the Heuristic_Score and the ML Propagation_Score using a configurable weighting

## Requirements

### Requirement 1: ML Service as a Standalone Application

**User Story:** As a PropView operator, I want the ML prediction service to run as a separate application from PropView, so that I can start, stop, and update it independently without affecting core APRS functionality.

#### Acceptance Criteria

1. THE ML_Service SHALL reside in a dedicated `ml_service/` directory within the PropView repository, with its own `requirements.txt`, entry point, and configuration
2. THE ML_Service SHALL run as an independent Python/FastAPI process on a configurable host and port (default: `127.0.0.1:8100`)
3. THE ML_Service SHALL start and stop independently of the PropView application process
4. THE ML_Service SHALL have no import dependencies on PropView's `server/` package
5. IF the ML_Service process is not running, THEN PropView SHALL continue operating with its existing heuristic prediction without errors or degraded performance

### Requirement 2: Feature Extraction Pipeline

**User Story:** As a PropView operator, I want the ML service to automatically extract training features from my existing PropView database, so that the model learns from my local propagation history without manual data preparation.

#### Acceptance Criteria

1. THE Feature_Pipeline SHALL read the PropView_Database directly via filesystem access using the configured database path
2. THE Feature_Pipeline SHALL extract the following features from the PropView_Database for each time step: hour of day (0–23), day of week (0–6), month (1–12), ducting index, pressure trend, humidity, wind speed, recent RF station count, recent maximum station distance in kilometers, DX spot rate per hour, and solar flux index where available
3. THE Feature_Pipeline SHALL join data across the propagation_log, ducting_log, dx_spots, and stations tables using aligned timestamps with a configurable alignment window (default: 5 minutes)
4. THE Feature_Pipeline SHALL handle missing values by applying column-specific imputation: median for numeric atmospheric fields, zero for count-based fields, and forward-fill for time-series fields
5. IF the PropView_Database file is locked or inaccessible, THEN THE Feature_Pipeline SHALL retry with exponential backoff up to 3 attempts and log the access failure at warning level
6. THE Feature_Pipeline SHALL open the PropView_Database in read-only mode to avoid interfering with PropView's write operations

### Requirement 3: Model Training

**User Story:** As a PropView operator, I want the ML service to train a prediction model from my local data, so that the predictions reflect my specific geographic location and propagation patterns.

#### Acceptance Criteria

1. THE Training_Pipeline SHALL train a time-series prediction model using XGBoost as the default algorithm, with a configurable option to use a lightweight LSTM via PyTorch
2. THE Training_Pipeline SHALL use the Propagation_Score (0–100) as the primary regression target, derived from the propagation_log table's station count and max distance fields using the same scoring logic as PropView's `compute_historical_score` function
3. THE Training_Pipeline SHALL split training data using time-based cross-validation with a minimum of 3 folds, ensuring no future data leaks into training folds
4. THE Training_Pipeline SHALL compute and log validation metrics after each training run: root mean squared error (RMSE), mean absolute error (MAE), and R² score
5. WHEN training completes successfully, THE Training_Pipeline SHALL persist the trained model artifact and a metadata file containing the training timestamp, data date range, row count, feature names, and validation metrics to the Model_Store directory
6. IF training fails due to insufficient data or a runtime error, THEN THE Training_Pipeline SHALL log the failure at error level and retain the previously trained model without overwriting it

### Requirement 4: Minimum Data Threshold

**User Story:** As a PropView operator, I want the ML service to tell me when it has enough data to make useful predictions, so that I know whether to trust the ML output or rely on the heuristic score.

#### Acceptance Criteria

1. THE ML_Service SHALL require a minimum of 30 days of data in the propagation_log table before producing predictions
2. WHEN fewer than 30 days of data are available, THE ML_Service SHALL return a status indicating insufficient data and include the current data coverage in days
3. WHEN fewer than 30 days of data are available, THE `/predict` endpoint SHALL return a response with a `ready` field set to false and a `message` field explaining the data shortfall
4. THE `/status` endpoint SHALL report the number of days of available training data and the minimum required threshold

### Requirement 5: Periodic Retraining

**User Story:** As a PropView operator, I want the ML model to retrain automatically as more data accumulates, so that predictions improve over time and adapt to seasonal changes.

#### Acceptance Criteria

1. THE ML_Service SHALL support configurable retraining schedules: daily (default) or weekly
2. WHEN the Retraining_Schedule triggers, THE Training_Pipeline SHALL extract the latest data from the PropView_Database and retrain the model
3. THE ML_Service SHALL perform retraining in a background task that does not block the `/predict` endpoint from serving predictions using the current model
4. WHEN retraining produces a model with validation RMSE more than 50% worse than the previous model, THE ML_Service SHALL log a warning and retain the previous model
5. THE `/status` endpoint SHALL report the last training timestamp, next scheduled training time, and the most recent validation metrics

### Requirement 6: Prediction Endpoint

**User Story:** As a PropView operator, I want the ML service to provide a REST endpoint that returns the current propagation forecast, so that PropView can incorporate ML predictions into its display.

#### Acceptance Criteria

1. THE ML_Service SHALL expose a `GET /predict` endpoint that returns a Propagation_Score (0–100), Opening_Probability (0.0–1.0), and a time-series forecast for the next 1 to 24 hours
2. THE `/predict` endpoint SHALL accept an optional `horizon_hours` query parameter (1–24, default: 12) controlling the forecast length
3. THE `/predict` endpoint SHALL return predictions within 500 milliseconds under normal operating conditions
4. THE `/predict` response SHALL include a `confidence` field (low, medium, high) based on the model's prediction interval width and data recency
5. THE `/predict` response SHALL include a `features_used` field listing the feature names and their current values used for the prediction
6. THE `/predict` response SHALL include a `model_version` field identifying which trained model produced the prediction
7. IF no trained model is available, THEN THE `/predict` endpoint SHALL return HTTP 503 with a JSON body explaining that the model is not yet trained

### Requirement 7: Training Trigger Endpoint

**User Story:** As a PropView operator, I want to manually trigger model retraining, so that I can force an update after significant data changes or configuration adjustments.

#### Acceptance Criteria

1. THE ML_Service SHALL expose a `POST /train` endpoint that initiates a model training run
2. WHEN a training run is already in progress, THE `/train` endpoint SHALL return HTTP 409 with a message indicating training is already running
3. THE `/train` endpoint SHALL return HTTP 202 with a JSON body containing a training job identifier and estimated duration
4. THE `/train` endpoint SHALL execute training asynchronously so that the response returns immediately without blocking

### Requirement 8: Status Endpoint

**User Story:** As a PropView operator, I want a status endpoint that reports the ML service's health and model information, so that I can verify the service is running and the model is current.

#### Acceptance Criteria

1. THE ML_Service SHALL expose a `GET /status` endpoint that returns the service health, model readiness, and operational metadata
2. THE `/status` response SHALL include: service uptime, model version, last training timestamp, next scheduled training time, training data date range, training data row count, days of data available, minimum data threshold, latest validation metrics (RMSE, MAE, R²), and whether the model is ready to serve predictions
3. WHEN no model has been trained, THE `/status` endpoint SHALL indicate `model_ready: false` and include the reason
4. THE `/status` endpoint SHALL return HTTP 200 regardless of model readiness, reflecting the service's own health

### Requirement 9: ML Service Configuration

**User Story:** As a PropView operator, I want to configure the ML service through a configuration file, so that I can adjust the port, model type, retraining schedule, and database path without modifying code.

#### Acceptance Criteria

1. THE ML_Service SHALL load configuration from a TOML file at `ml_service/config.toml` with sensible defaults for all fields
2. THE ML_Service configuration SHALL include: `host` (default: "127.0.0.1"), `port` (default: 8100), `propview_db_path` (default: "../propview.db"), `model_type` (default: "xgboost", options: "xgboost" or "lstm"), `retrain_schedule` (default: "daily", options: "daily" or "weekly"), `model_store_path` (default: "models/"), `min_data_days` (default: 30), and `log_level` (default: "info")
3. THE ML_Service SHALL validate configuration values at startup and log clear error messages for invalid settings
4. IF the configuration file does not exist at startup, THEN THE ML_Service SHALL create a default configuration file and proceed with default values

### Requirement 10: Model Artifact Storage

**User Story:** As a PropView operator, I want trained models stored as local files with versioning, so that I can inspect model history and roll back to a previous version if needed.

#### Acceptance Criteria

1. THE Model_Store SHALL persist trained model artifacts as joblib files (for XGBoost) or PyTorch checkpoint files (for LSTM) in the configured `model_store_path` directory
2. THE Model_Store SHALL maintain a `model_metadata.json` file alongside each model artifact containing: training timestamp, data date range, row count, feature names, validation metrics, model type, and a version identifier
3. THE Model_Store SHALL retain the two most recent model versions and delete older versions during cleanup
4. WHEN loading a model at startup, THE ML_Service SHALL load the most recent valid model artifact from the Model_Store
5. IF no model artifact exists at startup, THEN THE ML_Service SHALL start in a degraded state where `/predict` returns HTTP 503 and `/status` reports `model_ready: false`

### Requirement 11: PropView Integration — ML Service URL Configuration

**User Story:** As a PropView operator, I want to configure the ML service URL in PropView's settings, so that PropView knows where to reach the ML service for predictions.

#### Acceptance Criteria

1. THE PropView Configuration SHALL provide an `ml_service_url` field in the `[prediction]` TOML section (default: empty string, meaning ML integration is disabled)
2. WHEN `ml_service_url` is set to a non-empty value, THE Prediction_Engine SHALL attempt to call the ML_Service during each refresh cycle
3. WHEN `ml_service_url` is empty or not set, THE Prediction_Engine SHALL skip ML_Service integration entirely and use only the heuristic scoring
4. THE `ml_service_url` field SHALL accept a full URL including protocol, host, and port (e.g., "http://127.0.0.1:8100")

### Requirement 12: PropView Integration — Graceful Fallback

**User Story:** As a PropView operator, I want PropView to fall back to heuristic scoring when the ML service is unavailable, so that I always have a prediction even if the ML service is down.

#### Acceptance Criteria

1. WHEN the ML_Integration_Client calls the ML_Service `/predict` endpoint and receives a successful response, THE Prediction_Engine SHALL include the ML Propagation_Score in the prediction result alongside the Heuristic_Score
2. IF the ML_Service `/predict` endpoint is unreachable (connection refused, timeout, or DNS failure), THEN THE Prediction_Engine SHALL use the Heuristic_Score as the sole prediction and log the ML_Service failure at warning level
3. IF the ML_Service `/predict` endpoint returns an error response (HTTP 4xx or 5xx), THEN THE Prediction_Engine SHALL use the Heuristic_Score as the sole prediction and log the error response at warning level
4. THE ML_Integration_Client SHALL enforce a request timeout of 2 seconds to prevent slow ML_Service responses from delaying the prediction refresh cycle
5. THE Prediction_Engine SHALL not retry failed ML_Service requests within the same refresh cycle

### Requirement 13: PropView Integration — ML Data in API Response

**User Story:** As a PropView frontend, I want ML prediction data included in the existing prediction API response, so that the dashboard can display both heuristic and ML scores side by side.

#### Acceptance Criteria

1. WHEN ML prediction data is available, THE `/api/prediction` response SHALL include an `ml_prediction` object containing the ML Propagation_Score, Opening_Probability, confidence level, model version, and hourly forecast array
2. WHEN ML prediction data is not available, THE `/api/prediction` response SHALL include `ml_prediction: null`
3. THE WebSocket prediction push message SHALL include the `ml_prediction` field with the same structure as the REST API response
4. THE `/api/prediction` response SHALL include a `source` field indicating whether the displayed primary score is "heuristic", "ml", or "blended"

### Requirement 14: Prediction Forecast Format

**User Story:** As a PropView operator, I want the ML forecast to provide hourly predictions over a configurable horizon, so that I can see how propagation conditions are expected to change throughout the day.

#### Acceptance Criteria

1. THE `/predict` response SHALL include a `forecast` array containing one entry per hour for the requested Prediction_Horizon
2. Each forecast entry SHALL include: `hours_ahead` (1–24), `predicted_score` (0–100), `opening_probability` (0.0–1.0), and `timestamp` (ISO 8601 UTC)
3. THE forecast array SHALL be ordered by `hours_ahead` in ascending order
4. WHEN the model has low confidence for a specific hour, THE forecast entry for that hour SHALL include a `confidence` field set to "low"

### Requirement 15: ML Service Error Handling

**User Story:** As a PropView operator, I want the ML service to handle errors gracefully, so that database access issues, training failures, and malformed requests do not crash the service.

#### Acceptance Criteria

1. IF the PropView_Database is unavailable during a prediction request, THEN THE ML_Service SHALL return the last cached prediction result if available, or HTTP 503 if no cached result exists
2. IF the Feature_Pipeline encounters corrupt or unexpected data in the PropView_Database, THEN THE Feature_Pipeline SHALL skip the affected rows, log the issue at warning level, and continue processing remaining data
3. IF a prediction request contains invalid parameters, THEN THE `/predict` endpoint SHALL return HTTP 422 with a JSON body describing the validation error
4. THE ML_Service SHALL log all unhandled exceptions at error level and return HTTP 500 with a generic error message without exposing internal details
5. THE ML_Service SHALL implement a health check at `GET /health` that returns HTTP 200 when the service process is running, independent of model readiness

### Requirement 16: ML Service Logging

**User Story:** As a PropView operator, I want the ML service to produce structured logs, so that I can diagnose training failures, prediction anomalies, and data pipeline issues.

#### Acceptance Criteria

1. THE ML_Service SHALL log training start, completion, and failure events at info level, including duration and validation metrics
2. THE ML_Service SHALL log prediction requests at debug level, including input feature summary and response time
3. THE ML_Service SHALL log database access errors at warning level with the specific table and operation that failed
4. THE ML_Service SHALL log model loading events at info level, including the model version and file path
5. THE ML_Service SHALL support configurable log levels via the `log_level` configuration field

