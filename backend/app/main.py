"""
AirVision - Main FastAPI Application
Public access — no login required for dashboard.
Quiz requires name only. Leaderboard tracks scores.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import create_tables, seed_cities, seed_quiz_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("  AirVision API Starting...")
    print("=" * 50)

    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
    os.makedirs(settings.MODEL_DIR, exist_ok=True)

    create_tables()
    seed_cities()
    seed_quiz_data()

    # Auto-collect data if database is empty
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM air_quality_readings")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
            print("  Database empty — collecting data from OpenAQ...")
            from app.services.data_collector import collect_latest_data
            collect_latest_data()
    except Exception as e:
        print(f"  Data collection skipped: {e}")

    # Auto-generate forecasts
    try:
        from app.scheduler import generate_all_forecasts
        generate_all_forecasts()
    except Exception as e:
        print(f"  Auto-forecast skipped: {e}")

    print(f"  Database: {settings.DATABASE_PATH}")
    print(f"  OpenAQ Key: {'configured' if settings.OPENAQ_API_KEY else 'NOT SET'}")
    print(f"  OpenWeather Key: {'configured' if settings.OPENWEATHER_API_KEY and settings.OPENWEATHER_API_KEY != 'your-openweather-api-key-here' else 'NOT SET'}")
    print("=" * 50)
    print("  AirVision API Ready!")
    print("  App: http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print("=" * 50)

    yield
    print("AirVision API shutting down...")


app = FastAPI(
    title="AirVision API",
    description="Urban Air Quality Prediction System for the Middle East",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
from app.routers import air_quality, forecast, quiz
app.include_router(air_quality.router, prefix="/api", tags=["Air Quality"])
app.include_router(forecast.router, prefix="/api", tags=["Forecast"])
app.include_router(quiz.router, prefix="/api", tags=["Quiz & Points"])

# Keep auth router for optional use
try:
    from app.routers import auth
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
except Exception:
    pass


@app.get("/api/info", tags=["Health"])
async def api_info():
    return {
        "name": "AirVision API",
        "version": "1.0.0",
        "status": "running",
        "cities": list(settings.TARGET_CITIES.keys()),
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    from app.database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cities")
        cities = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM air_quality_readings")
        readings = cursor.fetchone()[0]
        conn.close()
        return {"status": "healthy", "cities": cities, "readings": readings}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Serve frontend files (MUST be last — catches all unmatched routes)
import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")