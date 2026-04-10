import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from app.config import settings
from app.database import get_db_connection

SEQUENCE_LENGTH = 7


def load_and_clean_pm25() -> np.ndarray:
    """
    Load PM2.5 data from all cities, clean it thoroughly, return sorted array.
    """
    conn = get_db_connection()
    query = """
        SELECT aq.timestamp, aq.pm25, c.city_name
        FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        WHERE aq.pm25 IS NOT NULL
        ORDER BY aq.timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return np.array([])

    df["pm25"] = pd.to_numeric(df["pm25"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    print(f"  Raw data: {len(df)} records")
    print(f"  Raw PM2.5 range: {df['pm25'].min():.1f} to {df['pm25'].max():.1f}")

    # ─── CLEANING STEP 1: Remove negatives (error codes like -999) ───
    before = len(df)
    df = df[df["pm25"] > 0]
    removed = before - len(df)
    if removed > 0:
        print(f"  Removed {removed} negative/zero values")

    # ─── CLEANING STEP 2: Remove extreme outliers ───
    # PM2.5 above 200 µg/m³ is extremely rare in Gulf cities
    # These are likely sensor errors or dust storm spikes that would skew the model
    before = len(df)
    q99 = df["pm25"].quantile(0.99)
    upper_limit = min(q99, 200)  # cap at 200 or 99th percentile
    df = df[df["pm25"] <= upper_limit]
    removed = before - len(df)
    if removed > 0:
        print(f"  Removed {removed} extreme outliers (>{upper_limit:.0f} µg/m³)")

    # ─── CLEANING STEP 3: Remove low outliers ───
    before = len(df)
    df = df[df["pm25"] >= 1.0]  # below 1 µg/m³ is likely sensor error
    removed = before - len(df)
    if removed > 0:
        print(f"  Removed {removed} suspiciously low values (<1 µg/m³)")

    # ─── CLEANING STEP 4: Sort and deduplicate ───
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="last")

    values = df["pm25"].values
    print(f"  Cleaned data: {len(values)} records")
    print(f"  Cleaned PM2.5 range: {values.min():.1f} to {values.max():.1f} µg/m³")
    print(f"  Mean: {values.mean():.1f}, Std: {values.std():.1f}")

    return values


def create_sequences(data, seq_length=SEQUENCE_LENGTH):
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i:i + seq_length])
        y.append(data[i + seq_length])
    return np.array(X), np.array(y)


def build_lstm_model(seq_length=SEQUENCE_LENGTH):
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout

    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(seq_length, 1)),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dense(1)
    ])

    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def train_lstm(epochs=50, batch_size=16):
    import joblib

    print("\n" + "=" * 60)
    print("  Training LSTM (RNN) Model")
    print("=" * 60)

    # Load and clean data
    values = load_and_clean_pm25()
    if len(values) < 50:
        print("  [ERROR] Not enough clean PM2.5 data (need 50+)")
        return None

    # Scale to [0, 1]
    values_reshaped = values.reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(values_reshaped).flatten()

    # Verify scaling
    print(f"  Scaled range: {scaled.min():.4f} to {scaled.max():.4f}")

    # Create sequences
    X, y = create_sequences(scaled, SEQUENCE_LENGTH)
    X = X.reshape(X.shape[0], X.shape[1], 1)

    print(f"  Total sequences: {len(X)}")
    print(f"  Sequence: {SEQUENCE_LENGTH} days → predict day {SEQUENCE_LENGTH + 1}")

    # Split 80/20 (preserve time order)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    # Build and train
    model = build_lstm_model(SEQUENCE_LENGTH)
    model.summary()

    print(f"\n  Training for {epochs} epochs...")
    from tensorflow.keras.callbacks import EarlyStopping

    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=10,
        restore_best_weights=True,
        verbose=1
    )

    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.1,
        callbacks=[early_stop],
        verbose=1
    )

    # Predict
    y_pred_scaled = model.predict(X_test, verbose=0).flatten()

    # Inverse scale back to µg/m³
    y_test_real = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    y_pred_real = scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()

    # Clip predictions to valid range
    y_pred_real = np.clip(y_pred_real, 0, 300)

    # Evaluate
    rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_real))
    mae = mean_absolute_error(y_test_real, y_pred_real)
    r2 = r2_score(y_test_real, y_pred_real)

    print(f"\n{'─' * 50}")
    print(f"  LSTM Results:")
    print(f"  RMSE:     {rmse:.4f}")
    print(f"  MAE:      {mae:.4f}")
    print(f"  R² Score: {r2:.4f}")
    print(f"{'─' * 50}")

    # Show some sample predictions vs actuals
    print(f"\n  Sample Predictions (last 10):")
    print(f"  {'Actual':>10}  {'Predicted':>10}  {'Error':>10}")
    for i in range(-10, 0):
        actual = y_test_real[i]
        pred = y_pred_real[i]
        err = abs(actual - pred)
        print(f"  {actual:>10.1f}  {pred:>10.1f}  {err:>10.1f}")

    # Save
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    model_path = os.path.join(settings.MODEL_DIR, "lstm_model.keras")
    scaler_path = os.path.join(settings.MODEL_DIR, "lstm_scaler.joblib")

    model.save(model_path)
    joblib.dump(scaler, scaler_path)
    print(f"\n  Model saved: {model_path}")
    print(f"  Scaler saved: {scaler_path}")

    # Save metrics to database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO model_metrics
        (model_name, rmse, mae, r_squared, training_samples, test_samples, feature_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("LSTM (RNN)", rmse, mae, r2, len(X_train), len(X_test), SEQUENCE_LENGTH))
    conn.commit()
    conn.close()

    return {
        "model_name": "LSTM (RNN)",
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "r_squared": round(r2, 4),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "epochs": epochs,
    }


def predict_lstm(city_name: str) -> dict:
    import joblib

    model_path = os.path.join(settings.MODEL_DIR, "lstm_model.keras")
    scaler_path = os.path.join(settings.MODEL_DIR, "lstm_scaler.joblib")

    if not os.path.exists(model_path):
        raise FileNotFoundError("LSTM model not trained. Run: python -m app.ml.rnn_model")

    from tensorflow.keras.models import load_model
    model = load_model(model_path)
    scaler = joblib.load(scaler_path)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT aq.pm25 FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        WHERE c.city_name = ? AND aq.pm25 IS NOT NULL AND aq.pm25 > 0
        ORDER BY aq.timestamp DESC
        LIMIT ?
    """, (city_name, SEQUENCE_LENGTH))
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < SEQUENCE_LENGTH:
        raise ValueError(f"Need {SEQUENCE_LENGTH} days of data, only have {len(rows)}")

    recent = np.array([float(r[0]) for r in reversed(rows)]).reshape(-1, 1)
    scaled = scaler.transform(recent).flatten()
    X_input = scaled.reshape(1, SEQUENCE_LENGTH, 1)

    pred_scaled = model.predict(X_input, verbose=0).flatten()[0]
    pred_pm25 = float(scaler.inverse_transform([[pred_scaled]])[0][0])
    pred_pm25 = max(0.0, min(pred_pm25, 300.0))  # clip to valid range

    from app.services.aqi_calculator import calculate_overall_aqi, get_aqi_category
    pred_aqi = calculate_overall_aqi(pm25=pred_pm25)
    aqi_info = get_aqi_category(pred_aqi)

    return {
        "predicted_pm25": round(pred_pm25, 2),
        "predicted_aqi": pred_aqi,
        "category": aqi_info["category"],
        "color": aqi_info["color"],
        "model": "LSTM (RNN)",
        "sequence_length": SEQUENCE_LENGTH,
        "input_days": [float(r[0]) for r in reversed(rows)],
    }


if __name__ == "__main__":
    result = train_lstm(epochs=100, batch_size=16)
    if result:
        print(f"\n{'='*60}")
        print(f"  LSTM Training Complete!")
        print(f"  RMSE: {result['rmse']} | MAE: {result['mae']} | R²: {result['r_squared']}")
        print(f"{'='*60}")

        print("\n  Testing prediction for Dubai...")
        try:
            pred = predict_lstm("Dubai")
            print(f"  Predicted PM2.5: {pred['predicted_pm25']} µg/m³")
            print(f"  Predicted AQI: {pred['predicted_aqi']} ({pred['category']})")
            print(f"  Input (last 7 days): {pred['input_days']}")
        except Exception as e:
            print(f"  Prediction error: {e}")

        print("\n  Testing prediction for Kuwait City...")
        try:
            pred = predict_lstm("Kuwait City")
            print(f"  Predicted PM2.5: {pred['predicted_pm25']} µg/m³")
            print(f"  Predicted AQI: {pred['predicted_aqi']} ({pred['category']})")
        except Exception as e:
            print(f"  Prediction error: {e}")