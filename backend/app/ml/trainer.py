import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("[WARNING] XGBoost not installed. Install with: pip install xgboost")

from app.config import settings
from app.database import get_db_connection


def get_models() -> dict:
    """
    Return a dictionary of ML models to train and compare.

    Returns:
        Dictionary with model name as key and sklearn estimator as value
    """
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ),
    }

    if XGBOOST_AVAILABLE:
        models["XGBoost"] = XGBRegressor(
            n_estimators=150,
            max_depth=8,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=0
        )

    return models


def train_and_evaluate(X: pd.DataFrame, y: pd.Series, feature_names: list) -> dict:
    """
    Train all models, evaluate them on a test set, and save the best one.

    Args:
        X: Feature matrix (DataFrame)
        y: Target variable (Series)
        feature_names: List of feature column names

    Returns:
        All records of results with model metrics and best model info
    """
    print("\n" + "=" * 60)
    print("AirVision ML Model Training")
    print("=" * 60)

    # Spliting data: 80% train, 20% test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False  # time-series: no shuffle
    )

    print(f"  Training samples: {len(X_train)}")
    print(f"  Test samples:     {len(X_test)}")
    print(f"  Features:         {len(feature_names)}")
    print(f"  Target range:     {y.min():.1f} – {y.max():.1f}")

    # Fill any remaining NaN values with 0 (from mismatched features across cities)
    X_train = X_train.fillna(0)
    X_test = X_test.fillna(0)

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Ensure model directory exists
    os.makedirs(settings.MODEL_DIR, exist_ok=True)

    models = get_models()
    results = {}
    best_model_name = None
    best_rmse = float("inf")

    conn = get_db_connection()
    cursor = conn.cursor()

    for name, model in models.items():
        print(f"\n{'─' * 50}")
        print(f"  Training: {name}")
        print(f"{'─' * 50}")

        try:
            # Train
            if name == "Linear Regression":
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
            else:
                # Tree-based models don't need scaling but it doesn't hurt
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

            # Evaluate
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            print(f"  RMSE:      {rmse:.4f}")
            print(f"  MAE:       {mae:.4f}")
            print(f"  R² Score:  {r2:.4f}")

            results[name] = {
                "rmse": round(rmse, 4),
                "mae": round(mae, 4),
                "r_squared": round(r2, 4),
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "feature_count": len(feature_names),
            }

            # Save model metrics to database
            cursor.execute("""
                INSERT INTO model_metrics 
                (model_name, rmse, mae, r_squared, training_samples, test_samples, feature_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, rmse, mae, r2, len(X_train), len(X_test), len(feature_names)))

            # Save model file
            safe_name = name.lower().replace(" ", "_")
            model_path = os.path.join(settings.MODEL_DIR, f"{safe_name}.joblib")
            joblib.dump(model, model_path)
            print(f"  Saved:     {model_path}")

            # Track best model
            if rmse < best_rmse:
                best_rmse = rmse
                best_model_name = name

            # Feature importance (for tree-based models)
            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
                feat_imp = sorted(
                    zip(feature_names, importances),
                    key=lambda x: x[1], reverse=True
                )
                print(f"\n  Top 10 Important Features:")
                for fname, imp in feat_imp[:10]:
                    print(f"    {fname:30s} {imp:.4f}")

        except Exception as e:
            print(f"  [ERROR] Training {name} failed: {str(e)}")
            results[name] = {"error": str(e)}

    conn.commit()

    # Save scaler and feature names
    joblib.dump(scaler, os.path.join(settings.MODEL_DIR, "scaler.joblib"))

    metadata = {
        "feature_names": feature_names,
        "best_model": best_model_name,
        "trained_at": datetime.utcnow().isoformat(),
        "results": results,
    }
    with open(os.path.join(settings.MODEL_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    conn.close()

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  MODEL COMPARISON SUMMARY")
    print(f"{'=' * 60}")
    print(f"  {'Model':<25} {'RMSE':>10} {'MAE':>10} {'R²':>10}")
    print(f"  {'─' * 55}")
    for name, metrics in results.items():
        if "error" not in metrics:
            marker = " ★" if name == best_model_name else ""
            print(f"  {name:<25} {metrics['rmse']:>10.4f} {metrics['mae']:>10.4f} {metrics['r_squared']:>10.4f}{marker}")
    print(f"  Models saved to: {settings.MODEL_DIR}")
    print(f"{'=' * 60}")

    return results


def run_training():
    """Full training pipeline: load data - preprocess - train - save."""
    from app.services.preprocessing import prepare_training_data

    X, y, feature_names = prepare_training_data(target_col="pm25")

    if X is None or X.empty:
        print("[ERROR] No training data available. Run data collection first:")
        print("  python -m app.services.data_collector")
        return

    results = train_and_evaluate(X, y, feature_names)
    return results


# ─── RUN DIRECTLY TO TRAIN MODELS ───
if __name__ == "__main__":
    run_training()
    