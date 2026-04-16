
# AirVision Data Preprocessing Service - Fixed for sparse pollutant data

#Key fix: Only creates features from pollutants that actually have data.
# Skips cross-pollutant features for columns that are entirely missing.

import pandas as pd
import numpy as np
from app.database import get_db_connection
from app.config import settings


def load_city_data(city_name: str) -> pd.DataFrame:
    conn = get_db_connection()
    query = """
        SELECT aq.timestamp, aq.pm25, aq.pm10, aq.no2, aq.o3, aq.co, aq.so2, aq.aqi
        FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        WHERE c.city_name = ?
        ORDER BY aq.timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=(city_name,))
    conn.close()

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    print(f"  Loaded {len(df)} records for {city_name} ({df['timestamp'].min().date()} to {df['timestamp'].max().date()})")
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    pollutants = ["pm25", "pm10", "no2", "o3", "co", "so2"]

    for col in pollutants:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df.loc[df[col] < 0, col] = np.nan

    # Remove extreme outliers (1st and 99th percentile)
    for col in pollutants:
        if col in df.columns and df[col].notna().sum() > 10:
            q1 = df[col].quantile(0.01)
            q99 = df[col].quantile(0.99)
            df.loc[(df[col] < q1) | (df[col] > q99), col] = np.nan

    # Forward-fill short gaps, then interpolate
    for col in pollutants:
        if col in df.columns:
            df[col] = df[col].ffill(limit=3)
            df[col] = df[col].interpolate(method="linear", limit=5)

    return df


def engineer_features(df: pd.DataFrame, target_col: str = "pm25") -> pd.DataFrame:
    """
    Create ML features. Only uses pollutants that have actual data (>50% non-null).
    """
    if df.empty or target_col not in df.columns:
        print(f"  [SKIP] Target '{target_col}' not in data")
        return pd.DataFrame()

    # Check if target has enough data
    target_valid = df[target_col].notna().sum()
    if target_valid < 20:
        print(f"  [SKIP] Only {target_valid} valid {target_col} values (need 20+)")
        return pd.DataFrame()

    features = df.copy()

    # TEMPORAL FEATURES 
    if "timestamp" in features.columns:
        features["day_of_week"] = features["timestamp"].dt.dayofweek
        features["month"] = features["timestamp"].dt.month
        features["day_of_year"] = features["timestamp"].dt.dayofyear
        features["is_weekend"] = (features["day_of_week"] >= 5).astype(int)
        features["season"] = features["month"].map(
            {12: 1, 1: 1, 2: 1, 3: 2, 4: 2, 5: 2,
             6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4}
        )

    #  LAGGED TARGET FEATURES
    for lag in range(1, 8):
        features[f"{target_col}_lag_{lag}"] = features[target_col].shift(lag)

    #  ROLLING STATISTICS 
    features[f"{target_col}_roll_mean_3"] = features[target_col].rolling(3).mean()
    features[f"{target_col}_roll_mean_7"] = features[target_col].rolling(7).mean()
    features[f"{target_col}_roll_std_3"] = features[target_col].rolling(3).std()
    features[f"{target_col}_roll_std_7"] = features[target_col].rolling(7).std()

    # RATE OF CHANGE 
    features[f"{target_col}_diff_1"] = features[target_col].diff(1)
    features[f"{target_col}_diff_7"] = features[target_col].diff(7)

    # CROSS-POLLUTANT FEATURES (only for columns with >50% data)
    other_pollutants = ["pm25", "pm10", "no2", "o3", "co", "so2"]
    for col in other_pollutants:
        if col == target_col:
            continue
        if col not in features.columns:
            continue
        # Only include if this pollutant has >50% valid data
        valid_pct = features[col].notna().sum() / len(features)
        if valid_pct < 0.5:
            continue  # Skip this pollutant — not enough data

        features[f"{col}_lag_1"] = features[col].shift(1)
        features[f"{col}_roll_mean_3"] = features[col].rolling(3).mean()

    #  TARGET: next-day value 
    features["target"] = features[target_col].shift(-1)

    # CLEANUP 
    # Drop timestamp (not numeric)
    if "timestamp" in features.columns:
        features = features.drop(columns=["timestamp"])

    # Drop raw pollutant columns (we use lagged/rolled versions)
    drop_cols = [c for c in ["pm25", "pm10", "no2", "o3", "co", "so2", "aqi"]
                 if c in features.columns]
    features = features.drop(columns=drop_cols)

    # Drop rows where TARGET is missing (essential)
    features = features.dropna(subset=["target"])

    # For remaining feature columns, fill NaN with 0
    # This handles edge cases from rolling/lagging at the start of the series
    features = features.fillna(0)

    print(f"  Feature engineering: {features.shape[0]} samples, {features.shape[1]-1} features")
    return features


def prepare_training_data(city_name: str = None, target_col: str = "pm25"):
    """
    Full pipeline: load → clean → engineer → return X, y.
    Only includes cities that have data for the target pollutant.
    """
    if city_name:
        cities = [city_name]
    else:
        cities = list(settings.TARGET_CITIES.keys())

    all_features = []

    for city in cities:
        print(f"\nPreparing data for {city}...")
        df = load_city_data(city)
        if df.empty:
            continue

        # Check if this city has the target pollutant
        target_valid = df[target_col].notna().sum()
        if target_valid < 20:
            print(f"  [SKIP] {city} has only {target_valid} {target_col} records (need 20+)")
            continue

        df = clean_data(df)
        features = engineer_features(df, target_col)

        if not features.empty:
            all_features.append(features)

    if not all_features:
        print("[ERROR] No training data available.")
        return None, None, []

    combined = pd.concat(all_features, ignore_index=True)

    y = combined["target"]
    X = combined.drop(columns=["target"])
    feature_names = X.columns.tolist()

    print(f"\n{'='*50}")
    print(f"  TRAINING DATA READY")
    print(f"{'='*50}")
    print(f"  Total samples: {X.shape[0]}")
    print(f"  Features: {X.shape[1]}")
    print(f"  Target: {target_col} (next-day prediction)")
    print(f"  Target range: {y.min():.1f} – {y.max():.1f}, mean: {y.mean():.1f}")
    print(f"  Feature columns:")
    for f in feature_names:
        print(f"    - {f}")

    return X, y, feature_names


if __name__ == "__main__":
    X, y, features = prepare_training_data()