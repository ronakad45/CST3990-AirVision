import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.config import settings
from app.database import get_db_connection
from app.services.aqi_calculator import calculate_overall_aqi, get_aqi_category


def load_model(model_name: str = None):
    """
    Load a trained model from disk. If no name given, load the best model.

    Args:
        model_name: Model identifier ('random_forest', 'xgboost', 'linear_regression')
                    or None to load the best model from metadata.

    Returns:
        Tuple of (model object, scaler object, feature_names list, model_display_name)
    """
    metadata_path = os.path.join(settings.MODEL_DIR, "metadata.json")

    if not os.path.exists(metadata_path):
        raise FileNotFoundError(
            "No trained models found. Run training first: python -m app.ml.trainer"
        )

    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    feature_names = metadata.get("feature_names", [])

    # Determine which model to load
    if model_name:
        safe_name = model_name.lower().replace(" ", "_")
        display_name = model_name
    else:
        best = metadata.get("best_model", "Random Forest")
        safe_name = best.lower().replace(" ", "_")
        display_name = best

    model_path = os.path.join(settings.MODEL_DIR, f"{safe_name}.joblib")
    scaler_path = os.path.join(settings.MODEL_DIR, "scaler.joblib")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None

    return model, scaler, feature_names, display_name


def get_latest_features(city_name: str, feature_names: list) -> pd.DataFrame:
    """
    Build the feature vector from the latest available data for a city.

    Retrieves the most recent readings from the database and constructs
    lagged, rolling, and temporal features matching the training schema.

    Args:
        city_name: Target city name
        feature_names: List of expected feature columns from training

    Returns:
        Single-row DataFrame with features matching training schema
    """
    conn = get_db_connection()

    # Fetch the last 14 days of data to compute lags and rolling features
    query = """
        SELECT aq.timestamp, aq.pm25, aq.pm10, aq.no2, aq.o3, aq.co, aq.so2, aq.aqi
        FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        WHERE c.city_name = ?
        ORDER BY aq.timestamp DESC
        LIMIT 14
    """
    df = pd.read_sql_query(query, conn, params=(city_name,))
    conn.close()

    if df.empty or len(df) < 7:
        raise ValueError(f"Insufficient recent data for {city_name}. Need at least 7 days.")

    # Reverse to chronological order
    df = df.iloc[::-1].reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Build features matching the training pipeline
    target_col = "pm25"
    features = {}

    # Temporal features from the forecast date (tomorrow)
    forecast_dt = datetime.utcnow() + timedelta(days=1)
    features["day_of_week"] = forecast_dt.weekday()
    features["month"] = forecast_dt.month
    features["day_of_year"] = forecast_dt.timetuple().tm_yday
    features["is_weekend"] = 1 if forecast_dt.weekday() >= 5 else 0
    month_to_season = {12: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4}
    features["season"] = month_to_season.get(forecast_dt.month, 1)

    # Lagged PM2.5 values (most recent = lag_1)
    pm25_values = df[target_col].dropna().values
    for lag in range(1, 8):
        idx = len(pm25_values) - lag
        features[f"{target_col}_lag_{lag}"] = float(pm25_values[idx]) if idx >= 0 else np.nan

    # Rolling statistics
    recent = pd.Series(pm25_values)
    features[f"{target_col}_roll_mean_3"] = float(recent.tail(3).mean())
    features[f"{target_col}_roll_mean_7"] = float(recent.tail(7).mean())
    features[f"{target_col}_roll_std_3"] = float(recent.tail(3).std())
    features[f"{target_col}_roll_std_7"] = float(recent.tail(7).std())

    # Rate of change
    if len(pm25_values) >= 2:
        features[f"{target_col}_diff_1"] = float(pm25_values[-1] - pm25_values[-2])
    else:
        features[f"{target_col}_diff_1"] = 0.0

    if len(pm25_values) >= 8:
        features[f"{target_col}_diff_7"] = float(pm25_values[-1] - pm25_values[-8])
    else:
        features[f"{target_col}_diff_7"] = 0.0

    # Cross-pollutant lagged features
    for col in ["pm10", "no2", "o3", "co", "so2"]:
        col_values = df[col].dropna().values
        if len(col_values) > 0:
            features[f"{col}_lag_1"] = float(col_values[-1])
            features[f"{col}_roll_mean_3"] = float(pd.Series(col_values).tail(3).mean())
        else:
            features[f"{col}_lag_1"] = 0.0
            features[f"{col}_roll_mean_3"] = 0.0

    # Create DataFrame and align columns to match training features
    feature_df = pd.DataFrame([features])

    # Ensure all expected columns exist (fill missing with 0)
    for col in feature_names:
        if col not in feature_df.columns:
            feature_df[col] = 0.0

    # Keep only the training features in the correct order
    feature_df = feature_df[feature_names]

    # Fill any NaN
    feature_df = feature_df.fillna(0.0)

    return feature_df


def predict_next_day(city_name: str, model_name: str = None) -> dict:
    """
    Generate a next-day air quality prediction for a city.

    Args:
        city_name: Target city
        model_name: Specific model to use, or None for best model

    Returns:
        Dictionary with prediction results
    """
    model, scaler, feature_names, display_name = load_model(model_name)
    feature_df = get_latest_features(city_name, feature_names)

    # Predict
    if "linear" in display_name.lower() and scaler:
        features_scaled = scaler.transform(feature_df)
        predicted_pm25 = float(model.predict(features_scaled)[0])
    else:
        predicted_pm25 = float(model.predict(feature_df)[0])

    # Ensure non-negative prediction
    predicted_pm25 = max(0.0, predicted_pm25)

    # Calculate predicted AQI from predicted PM2.5
    predicted_aqi = calculate_overall_aqi(pm25=predicted_pm25)
    aqi_info = get_aqi_category(predicted_aqi)

    # Estimate confidence based on model R² and prediction stability
    metadata_path = os.path.join(settings.MODEL_DIR, "metadata.json")
    confidence = 0.75  # default
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            meta = json.load(f)
        model_key = display_name
        if model_key in meta.get("results", {}):
            r2 = meta["results"][model_key].get("r_squared", 0.5)
            confidence = min(0.95, max(0.5, r2))

    # Save prediction to database
    forecast_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city_name,))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            INSERT INTO predictions
            (city_id, forecast_date, predicted_aqi, predicted_pm25, confidence, model_used, alert_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (row[0], forecast_date, predicted_aqi, predicted_pm25, confidence,
              display_name, aqi_info["category"]))
        conn.commit()
    conn.close()

    return {
        "city": city_name,
        "forecast_date": forecast_date,
        "predicted_aqi": round(predicted_aqi, 1),
        "predicted_pm25": round(predicted_pm25, 2),
        "confidence": round(confidence * 100, 1),
        "model_used": display_name,
        "alert_level": aqi_info["category"],
        "alert_color": aqi_info["color"],
        "health_advisory": aqi_info["health_advisory"],
    }


def get_model_comparison() -> list:
    """Retrieve model comparison metrics from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT model_name, rmse, mae, r_squared, training_samples, test_samples, feature_count, trained_at
        FROM model_metrics
        ORDER BY trained_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    # Group by model name, take latest entry
    seen = set()
    results = []
    for row in rows:
        name = row[0]
        if name not in seen:
            seen.add(name)
            results.append({
                "model_name": name,
                "rmse": round(row[1], 4),
                "mae": round(row[2], 4),
                "r_squared": round(row[3], 4),
                "training_samples": row[4],
                "test_samples": row[5],
                "feature_count": row[6],
                "trained_at": row[7],
            })

    return results


# ─── TEST PREDICTION ───
if __name__ == "__main__":
    try:
        result = predict_next_day("Dubai")
        print("\nPrediction Result:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
