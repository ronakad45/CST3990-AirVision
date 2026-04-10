"""
AirVision Forecast Router — Auto-generated forecasts
No manual generation needed. Forecasts are auto-generated on startup and daily.
"""

from fastapi import APIRouter, HTTPException, Query
from app.scheduler import get_latest_forecast, get_multi_day_forecast, generate_all_forecasts
from app.ml.predictor import get_model_comparison

router = APIRouter()


@router.get("/forecast/{city}")
async def get_forecast(city: str):
    """
    Get the latest auto-generated forecast for a city.
    Forecasts are generated automatically — no user action needed.
    """
    # Try to get existing forecast
    forecast = get_latest_forecast(city)

    if not forecast:
        # Generate on-demand if none exists yet
        try:
            generate_all_forecasts()
            forecast = get_latest_forecast(city)
        except Exception:
            pass

    if not forecast:
        raise HTTPException(status_code=404, detail=f"No forecast available for {city}. Insufficient data.")

    forecast["city"] = city
    return forecast


@router.get("/forecast/{city}/multi")
async def get_multi_forecast(
    city: str,
    days: int = Query(default=5, ge=1, le=7)
):
    """
    Get multi-day forecast (1-7 days ahead) for a city.
    Uses model chaining — each day's prediction feeds into the next.
    """
    forecasts = get_multi_day_forecast(city, days)

    if not forecasts:
        raise HTTPException(status_code=404, detail=f"Cannot generate multi-day forecast for {city}.")

    return {
        "city": city,
        "days_ahead": days,
        "forecasts": forecasts,
    }


@router.get("/models/compare")
async def compare_models():
    """Get performance metrics for all trained models."""
    results = get_model_comparison()
    if not results:
        raise HTTPException(status_code=404, detail="No trained models found.")
    return {"models": results}
