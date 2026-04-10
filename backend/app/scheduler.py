"""
AirVision Auto-Scheduler
Generates forecasts automatically on startup for all cities.
Each city uses its own database connection to avoid locking.
"""

import os
import json
from datetime import datetime, timezone, timedelta
from app.config import settings
from app.database import get_db_connection
from app.services.aqi_calculator import calculate_overall_aqi, get_aqi_category


def generate_all_forecasts():
    """Generate next-day forecasts for all cities that have PM2.5 data."""
    print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Generating forecasts for all cities...")

    metadata_path = os.path.join(settings.MODEL_DIR, "metadata.json")
    if not os.path.exists(metadata_path):
        print("  [SKIP] No trained models found.")
        return

    forecast_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Get list of cities
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT city_id, city_name FROM cities")
    city_list = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()

    # Process each city with its own connection (avoids database locking)
    for city_id, city_name in city_list:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if forecast already exists for tomorrow
        cursor.execute(
            "SELECT prediction_id FROM predictions WHERE city_id = ? AND forecast_date = ?",
            (city_id, forecast_date)
        )
        if cursor.fetchone():
            conn.close()
            continue

        # Check if city has enough PM2.5 data
        cursor.execute(
            "SELECT COUNT(*) FROM air_quality_readings WHERE city_id = ? AND pm25 IS NOT NULL",
            (city_id,)
        )
        pm25_count = cursor.fetchone()[0]
        conn.close()

        if pm25_count < 7:
            continue

        # Generate forecast
        try:
            from app.ml.predictor import predict_next_day
            result = predict_next_day(city_name)

            # Save to database with fresh connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions
                (city_id, forecast_date, predicted_aqi, predicted_pm25, confidence, model_used, alert_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (city_id, forecast_date, result["predicted_aqi"], result["predicted_pm25"],
                  result["confidence"], result["model_used"], result["alert_level"]))
            conn.commit()
            conn.close()

            print(f"  {city_name}: AQI={result['predicted_aqi']} PM2.5={result['predicted_pm25']} ({result['alert_level']})")

        except Exception as e:
            print(f"  {city_name}: Forecast failed - {str(e)}")

    print("  Forecasts complete.")


def get_latest_forecast(city_name):
    """Get the most recent forecast for a city."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.forecast_date, p.predicted_aqi, p.predicted_pm25, p.confidence,
               p.model_used, p.alert_level, p.created_at
        FROM predictions p
        JOIN cities c ON p.city_id = c.city_id
        WHERE c.city_name = ?
        ORDER BY p.created_at DESC LIMIT 1
    """, (city_name,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    aqi_info = get_aqi_category(int(row[1]))

    return {
        "forecast_date": row[0],
        "predicted_aqi": round(row[1], 1),
        "predicted_pm25": round(row[2], 2),
        "confidence": round(row[3] * 100, 1) if row[3] and row[3] <= 1 else round(row[3], 1) if row[3] else 50.0,
        "model_used": row[4],
        "alert_level": row[5],
        "alert_color": aqi_info["color"],
        "health_advisory": aqi_info["health_advisory"],
        "generated_at": row[6],
    }


def get_multi_day_forecast(city_name, days=5):
    """Generate multi-day forecast by chaining predictions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return []

    cursor.execute("""
        SELECT pm25 FROM air_quality_readings
        WHERE city_id = ? AND pm25 IS NOT NULL
        ORDER BY timestamp DESC LIMIT 7
    """, (row[0],))
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 7:
        return []

    recent_values = [float(r[0]) for r in reversed(rows)]

    # Load model
    try:
        import joblib
        import numpy as np
        import pandas as pd

        metadata_path = os.path.join(settings.MODEL_DIR, "metadata.json")
        if not os.path.exists(metadata_path):
            return []

        with open(metadata_path) as f:
            metadata = json.load(f)

        best_name = metadata.get("best_model", "Linear Regression")
        safe_name = best_name.lower().replace(" ", "_")
        model = joblib.load(os.path.join(settings.MODEL_DIR, f"{safe_name}.joblib"))
        scaler = joblib.load(os.path.join(settings.MODEL_DIR, "scaler.joblib"))
        feature_names = metadata.get("feature_names", [])

    except Exception as e:
        print(f"  Multi-day forecast error: {e}")
        return []

    forecasts = []
    current_values = list(recent_values)

    for day_offset in range(1, days + 1):
        forecast_dt = datetime.now(timezone.utc) + timedelta(days=day_offset)
        forecast_date = forecast_dt.strftime("%Y-%m-%d")

        vals = current_values[-7:]
        features = {}
        features["day_of_week"] = forecast_dt.weekday()
        features["month"] = forecast_dt.month
        features["day_of_year"] = forecast_dt.timetuple().tm_yday
        features["is_weekend"] = 1 if forecast_dt.weekday() >= 5 else 0
        month_to_season = {12:1,1:1,2:1,3:2,4:2,5:2,6:3,7:3,8:3,9:4,10:4,11:4}
        features["season"] = month_to_season.get(forecast_dt.month, 1)

        for lag in range(1, 8):
            idx = len(vals) - lag
            features[f"pm25_lag_{lag}"] = vals[idx] if idx >= 0 else 0

        import pandas as pd
        series = pd.Series(vals)
        features["pm25_roll_mean_3"] = float(series.tail(3).mean())
        features["pm25_roll_mean_7"] = float(series.tail(7).mean())
        features["pm25_roll_std_3"] = float(series.tail(3).std()) if len(vals) >= 3 else 0
        features["pm25_roll_std_7"] = float(series.tail(7).std()) if len(vals) >= 7 else 0
        features["pm25_diff_1"] = vals[-1] - vals[-2] if len(vals) >= 2 else 0
        features["pm25_diff_7"] = vals[-1] - vals[0] if len(vals) >= 7 else 0

        feature_df = pd.DataFrame([features])
        for col in feature_names:
            if col not in feature_df.columns:
                feature_df[col] = 0.0
        feature_df = feature_df[feature_names].fillna(0.0)

        if "linear" in best_name.lower():
            pred = float(model.predict(scaler.transform(feature_df))[0])
        else:
            pred = float(model.predict(feature_df)[0])

        pred = max(0, pred)
        pred_aqi = calculate_overall_aqi(pm25=pred)
        aqi_info = get_aqi_category(pred_aqi)

        base_conf = metadata.get("results", {}).get(best_name, {}).get("r_squared", 0.5)
        confidence = max(0.3, base_conf - (day_offset - 1) * 0.08)

        forecasts.append({
            "day": day_offset,
            "forecast_date": forecast_date,
            "predicted_pm25": round(pred, 2),
            "predicted_aqi": pred_aqi,
            "alert_level": aqi_info["category"],
            "alert_color": aqi_info["color"],
            "confidence": round(confidence * 100, 1),
        })

        current_values.append(pred)

    return forecasts


if __name__ == "__main__":
    generate_all_forecasts()