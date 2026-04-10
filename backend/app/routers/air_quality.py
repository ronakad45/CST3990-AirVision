"""
AirVision Air Quality Router — Fixed
Gets latest value for EACH pollutant separately (not just one row).
Works for cities with any combination of pollutants.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, timezone

from app.database import get_db_connection
from app.services.aqi_calculator import calculate_overall_aqi, get_aqi_category
from app.services.weather import get_weather

router = APIRouter()


@router.get("/current/{city}")
async def get_current_air_quality(city: str):
    """
    Get the latest reading for EACH pollutant separately.
    This combines data from multiple sensors/stations to give the fullest picture.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get city_id
    cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city,))
    city_row = cursor.fetchone()
    if not city_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    city_id = city_row[0]

    # Get latest value for each pollutant separately
# Get the latest row first
    cursor.execute("""
        SELECT timestamp, pm25, pm10, no2, o3, co, so2, aqi
        FROM air_quality_readings WHERE city_id = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (city_id,))
    latest = cursor.fetchone()

    if not latest:
        conn.close()
        raise HTTPException(status_code=404, detail=f"No data for {city}")

    latest_timestamp = latest[0]
    pollutants = {
        "pm25": latest[1], "pm10": latest[2], "no2": latest[3],
        "o3": latest[4], "co": latest[5], "so2": latest[6],
    }

    # Fill missing pollutants from recent rows (same week only)
    for col in ["pm25", "pm10", "no2", "o3", "co", "so2"]:
        if pollutants[col] is None:
            cursor.execute(f"""
                SELECT {col} FROM air_quality_readings
                WHERE city_id = ? AND {col} IS NOT NULL
                AND timestamp >= date(?, '-7 days')
                ORDER BY timestamp DESC LIMIT 1
            """, (city_id, latest_timestamp))
            row = cursor.fetchone()
            if row:
                pollutants[col] = row[0]

    conn.close()

    # Only use PM2.5 and PM10 for AQI (units are reliable: µg/m³)
    # NO2, O3, CO, SO2 shown as info only — units vary between stations
    aqi = calculate_overall_aqi(
        pm25=pollutants.get("pm25"),
        pm10=pollutants.get("pm10"),
    )

    if not pollutants:
        raise HTTPException(status_code=404, detail=f"No data for {city}")

    # Calculate AQI from all available pollutants
    aqi = calculate_overall_aqi(
        pm25=pollutants.get("pm25"),
        pm10=pollutants.get("pm10"),
        no2=pollutants.get("no2"),
        o3=pollutants.get("o3"),
        co=pollutants.get("co"),
        so2=pollutants.get("so2"),
    )
    aqi_info = get_aqi_category(aqi)

    # Determine which pollutant is driving the AQI
    dominant = "pm25"
    if pollutants.get("pm25") is None and pollutants.get("pm10") is not None:
        dominant = "pm10"

    return {
        "city": city,
        "timestamp": latest_timestamp,
        "pm25": pollutants.get("pm25"),
        "pm10": pollutants.get("pm10"),
        "no2": pollutants.get("no2"),
        "o3": pollutants.get("o3"),
        "co": pollutants.get("co"),
        "so2": pollutants.get("so2"),
        "aqi": aqi,
        "category": aqi_info["category"],
        "color": aqi_info["color"],
        "health_advisory": aqi_info["health_advisory"],
        "dominant_pollutant": dominant,
    }


@router.get("/historical/{city}")
async def get_historical_data(city: str, days: int = Query(default=30, ge=1, le=1500)):
    """Get historical data. Returns empty list instead of 404 if no data in range."""
    conn = get_db_connection()
    cursor = conn.cursor()
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT aq.timestamp, aq.pm25, aq.pm10, aq.no2, aq.o3, aq.co, aq.so2, aq.aqi
        FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id
        WHERE c.city_name = ? AND aq.timestamp >= ?
        ORDER BY aq.timestamp ASC
    """, (city, date_from))
    rows = cursor.fetchall()

    # If no data in range, try getting ALL data for this city
    if not rows:
        cursor.execute("""
            SELECT aq.timestamp, aq.pm25, aq.pm10, aq.no2, aq.o3, aq.co, aq.so2, aq.aqi
            FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id
            WHERE c.city_name = ?
            ORDER BY aq.timestamp ASC
        """, (city,))
        rows = cursor.fetchall()

    conn.close()

    if not rows:
        return {
            "city": city, "time_range": f"{days} days",
            "total_readings": 0, "readings": [],
            "average_aqi": 0, "peak_aqi": 0, "min_aqi": 0,
        }

    readings = []
    aqi_values = []
    for row in rows:
        aqi = row[7] if row[7] else calculate_overall_aqi(
            pm25=row[1], pm10=row[2], no2=row[3], o3=row[4], co=row[5], so2=row[6]
        )
        if aqi and aqi > 0:
            aqi_values.append(aqi)
        readings.append({
            "timestamp": row[0], "pm25": row[1], "pm10": row[2],
            "no2": row[3], "o3": row[4], "co": row[5], "so2": row[6], "aqi": aqi,
        })

    return {
        "city": city, "time_range": f"{days} days",
        "total_readings": len(readings), "readings": readings,
        "average_aqi": round(sum(aqi_values) / len(aqi_values), 1) if aqi_values else 0,
        "peak_aqi": max(aqi_values) if aqi_values else 0,
        "min_aqi": min(aqi_values) if aqi_values else 0,
    }


@router.get("/compare")
async def compare_cities(cities: str = Query(...)):
    city_list = [c.strip() for c in cities.split(",")]
    if len(city_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 cities")

    results = []
    for city in city_list:
        try:
            data = await get_current_air_quality(city)
            results.append(data)
        except HTTPException:
            pass

    return {"cities": results}


@router.get("/cities")
async def list_cities():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT city_id, city_name, country, latitude, longitude FROM cities")
    cities = cursor.fetchall()
    results = []
    for city in cities:
        cursor.execute("SELECT aqi, timestamp FROM air_quality_readings WHERE city_id = ? ORDER BY timestamp DESC LIMIT 1", (city[0],))
        latest = cursor.fetchone()
        results.append({
            "city_name": city[1], "country": city[2],
            "latitude": city[3], "longitude": city[4],
            "latest_aqi": latest[0] if latest else None,
            "last_updated": latest[1] if latest else None,
        })
    conn.close()
    return {"cities": results}


@router.get("/weather/{city}")
async def get_city_weather(city: str):
    weather = get_weather(city)
    if not weather:
        raise HTTPException(status_code=503, detail="Weather unavailable")
    weather["city"] = city
    return weather