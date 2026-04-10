"""
AirVision Weather Service
Fetches current weather data from OpenWeather API for target cities.
"""

import httpx
import time
from app.config import settings

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5/weather"


def get_weather(city_name: str) -> dict:
    """
    Fetch current weather for a city from OpenWeather API.
    Returns temperature, humidity, wind, conditions, and icon.
    """
    if not settings.OPENWEATHER_API_KEY or settings.OPENWEATHER_API_KEY == "your-openweather-api-key-here":
        return None

    # Map our city names to OpenWeather-friendly names
    city_map = {
        "Dubai": "Dubai,AE",
        "Abu Dhabi": "Abu Dhabi,AE",
        "Riyadh": "Riyadh,SA",
        "Kuwait City": "Kuwait City,KW",
        "Doha": "Doha,QA",
    }

    query = city_map.get(city_name, city_name)

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(OPENWEATHER_BASE, params={
                "q": query,
                "appid": settings.OPENWEATHER_API_KEY,
                "units": "metric",
            })

            if response.status_code == 200:
                data = response.json()
                weather = data.get("weather", [{}])[0]
                main = data.get("main", {})
                wind = data.get("wind", {})

                return {
                    "temperature": round(main.get("temp", 0), 1),
                    "feels_like": round(main.get("feels_like", 0), 1),
                    "humidity": main.get("humidity", 0),
                    "pressure": main.get("pressure", 0),
                    "wind_speed": round(wind.get("speed", 0), 1),
                    "wind_deg": wind.get("deg", 0),
                    "condition": weather.get("main", "Unknown"),
                    "description": weather.get("description", ""),
                    "icon": weather.get("icon", "01d"),
                    "icon_url": f"https://openweathermap.org/img/wn/{weather.get('icon', '01d')}@2x.png",
                }
            else:
                print(f"  [WEATHER ERROR] {response.status_code}: {response.text[:200]}")
                return None

    except Exception as e:
        print(f"  [WEATHER ERROR] {e}")
        return None
