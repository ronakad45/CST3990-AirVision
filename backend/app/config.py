"""
AirVision Configuration Module
Loads settings from .env file and provides them to the application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


class Settings:
    """Application settings loaded from environment variables."""

    # API Keys
    OPENAQ_API_KEY: str = os.getenv("OPENAQ_API_KEY", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

    # Database
    DATABASE_PATH: str = str(BASE_DIR / "data" / "airvision.db")

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))

    # Target Cities with their OpenAQ location metadata
    # These will be populated dynamically, but we define known cities here
    TARGET_CITIES = {
        "Dubai": {
            "country_code": "AE",
            "latitude": 25.2048,
            "longitude": 55.2708,
            "timezone": "Asia/Dubai"
        },
        "Abu Dhabi": {
            "country_code": "AE",
            "latitude": 24.4539,
            "longitude": 54.3773,
            "timezone": "Asia/Dubai"
        },
        "Riyadh": {
            "country_code": "SA",
            "latitude": 24.7136,
            "longitude": 46.6753,
            "timezone": "Asia/Riyadh"
        },
        "Kuwait City": {
            "country_code": "KW",
            "latitude": 29.3759,
            "longitude": 47.9774,
            "timezone": "Asia/Kuwait"
        },
        "Doha": {
            "country_code": "QA",
            "latitude": 25.2854,
            "longitude": 51.5310,
            "timezone": "Asia/Qatar"
        },
    }

    # AQI Breakpoints (US EPA Standard)
    AQI_CATEGORIES = {
        "Good": {"min": 0, "max": 50, "color": "#22C55E"},
        "Moderate": {"min": 51, "max": 100, "color": "#F59E0B"},
        "Unhealthy for Sensitive Groups": {"min": 101, "max": 150, "color": "#F97316"},
        "Unhealthy": {"min": 151, "max": 200, "color": "#EF4444"},
        "Very Unhealthy": {"min": 201, "max": 300, "color": "#8B5CF6"},
        "Hazardous": {"min": 301, "max": 500, "color": "#7F1D1D"}
    }

    # Pollutant parameters tracked
    POLLUTANT_PARAMETERS = ["pm25", "pm10", "no2", "o3", "co", "so2"]

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # ML Model paths
    MODEL_DIR: str = str(BASE_DIR / "data" / "models")


settings = Settings()
