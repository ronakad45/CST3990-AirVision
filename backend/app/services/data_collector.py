"""
AirVision Data Collector - FINAL VERSION

Confirmed API response format for /v3/sensors/{id}/days:
{
  "value": 38.2,              ← daily average (FLOAT, not dict!)
  "period": {
    "datetimeFrom": {
      "utc": "2023-12-31T20:00:00Z",
      "local": "2024-01-01T00:00:00+04:00"
    }
  },
  "summary": {"avg": 38.2, "min": 30.0, "max": 50.0, ...}
}

Country IDs: UAE=59, Saudi Arabia=106
Max radius: 25000m
"""

import httpx
import sqlite3
import time
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings
from app.database import get_db_connection
from app.services.aqi_calculator import calculate_overall_aqi

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": settings.OPENAQ_API_KEY, "Accept": "application/json"}
REQUEST_DELAY = 1.5
COUNTRY_IDS = {"AE": 59, "SA": 106}


def _api_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to OpenAQ with rate limiting."""
    url = f"{OPENAQ_BASE_URL}{endpoint}"
    time.sleep(REQUEST_DELAY)
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers=HEADERS, params=params)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"  [RATE LIMIT] Waiting 60s...")
                time.sleep(60)
                r = client.get(url, headers=HEADERS, params=params)
                return r.json() if r.status_code == 200 else None
            else:
                print(f"  [ERROR {r.status_code}] {r.text[:200]}")
                return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def _haversine_km(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ─── LOCATION DISCOVERY ───

def find_locations(city_name, country_code, lat, lon):
    """Find monitoring stations near a city."""
    print(f"  Searching near {city_name}...")

    # Try coordinates search first (25km max radius)
    data = _api_get("/locations", {"coordinates": f"{lat},{lon}", "radius": 25000, "limit": 20})
    if data and data.get("results"):
        locs = _parse_locations(data["results"], lat, lon)
        print(f"  Found {len(locs)} stations via coordinates")
        return locs

    # Fallback: country-wide search
    cid = COUNTRY_IDS.get(country_code)
    if cid:
        data = _api_get("/locations", {"countries_id": cid, "limit": 100})
        if data and data.get("results"):
            locs = _parse_locations(data["results"], lat, lon)
            locs = [l for l in locs if l["distance_km"] <= 100]
            print(f"  Found {len(locs)} stations via country search")
            return locs

    print(f"  No stations found for {city_name}")
    return []


def _parse_locations(results, target_lat, target_lon):
    locs = []
    for r in results:
        c = r.get("coordinates", {})
        lat, lon = c.get("latitude"), c.get("longitude")
        if lat is None or lon is None:
            continue
        locs.append({
            "id": r["id"],
            "name": r.get("name", "Unknown"),
            "sensors": r.get("sensors", []),
            "distance_km": round(_haversine_km(target_lat, target_lon, lat, lon), 1),
        })
    locs.sort(key=lambda x: x["distance_km"])
    return locs


# ─── SENSOR DISCOVERY ───

def get_sensors(location_id):
    """Get pollutant sensors at a location."""
    data = _api_get(f"/locations/{location_id}/sensors")
    sensors = []
    if data and "results" in data:
        for s in data["results"]:
            p = s.get("parameter", {})
            name = p.get("name", "").lower()
            if name in settings.POLLUTANT_PARAMETERS:
                sensors.append({
                    "sensor_id": s["id"],
                    "parameter": name,
                    "units": p.get("units", ""),
                })
    return sensors


# ─── DATA FETCHING ───

def fetch_daily_data(sensor_id, date_from=None, date_to=None):
    """
    Fetch daily aggregated data from /sensors/{id}/days.
    
    CONFIRMED response format:
        result["value"]  → float (daily average)
        result["period"]["datetimeFrom"]["local"]  → "2024-01-01T00:00:00+04:00"
    """
    all_records = []
    page = 1

    while True:
        params = {"limit": 1000, "page": page}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        data = _api_get(f"/sensors/{sensor_id}/days", params)

        if not data or "results" not in data:
            break

        results = data["results"]
        if not results:
            break

        for r in results:
            # VALUE: top-level float (confirmed from debug output)
            value = r.get("value")
            if value is None:
                continue

            # DATE: extract from period.datetimeFrom.local (use local date)
            period = r.get("period", {})
            dt_from = period.get("datetimeFrom", {})

            if isinstance(dt_from, dict):
                # Prefer local date (matches the actual calendar day)
                date_str = dt_from.get("local", "")[:10]
                if not date_str:
                    date_str = dt_from.get("utc", "")[:10]
            elif isinstance(dt_from, str):
                date_str = dt_from[:10]
            else:
                continue

            if date_str and len(date_str) == 10:
                all_records.append({
                    "date": date_str,
                    "value": float(value),
                })

        # Check for more pages
        meta = data.get("meta", {})
        found = meta.get("found", 0)
        if isinstance(found, str):
            # API sometimes returns ">3" for found
            if page == 1 and len(results) == 1000:
                page += 1
                continue
            break
        if page * 1000 >= found:
            break
        page += 1

    return all_records


# ─── MAIN COLLECTION ───

def collect_historical_data(days_back: int = 365):
    """Fetch historical daily AQ data for all target cities."""
    print("=" * 60)
    print("  AirVision Data Collection")
    print("  (May take 10-15 min due to API rate limits)")
    print("=" * 60)

    if not settings.OPENAQ_API_KEY or "your-openaq" in settings.OPENAQ_API_KEY:
        print("[ERROR] Set your OpenAQ API key in .env file!")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"  Range: {date_from[:10]} to {date_to[:10]}")

    total_inserted = 0

    for city_name, city_info in settings.TARGET_CITIES.items():
        print(f"\n{'─'*50}")
        print(f"  {city_name}")
        print(f"{'─'*50}")

        cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city_name,))
        row = cursor.fetchone()
        if not row:
            continue
        city_id = row[0]

        locations = find_locations(city_name, city_info["country_code"],
                                   city_info["latitude"], city_info["longitude"])
        if not locations:
            continue

        # Use up to 3 closest stations
        for loc in locations[:3]:
            print(f"\n  Station: {loc['name']} (ID:{loc['id']}, {loc['distance_km']}km)")

            sensors = get_sensors(loc["id"])
            print(f"    Sensors: {[s['parameter'] for s in sensors]}")
            if not sensors:
                continue

            # Collect daily data per pollutant
            daily_data = {}  # {date: {param: value}}

            for sensor in sensors:
                param = sensor["parameter"]
                sid = sensor["sensor_id"]
                print(f"    Fetching {param} (sensor {sid})...", end=" ")

                records = fetch_daily_data(sid, date_from, date_to)
                print(f"→ {len(records)} days")

                for rec in records:
                    d = rec["date"]
                    if d not in daily_data:
                        daily_data[d] = {}
                    if param not in daily_data[d]:
                        daily_data[d][param] = rec["value"]

            # Insert into database
            inserted = 0
            for date_str, pollutants in sorted(daily_data.items()):
                pm25 = pollutants.get("pm25")
                pm10 = pollutants.get("pm10")
                no2 = pollutants.get("no2")
                o3 = pollutants.get("o3")
                co = pollutants.get("co")
                so2 = pollutants.get("so2")
                aqi = calculate_overall_aqi(pm25=pm25, pm10=pm10, no2=no2, o3=o3, co=co, so2=so2)

                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO air_quality_readings
                        (city_id, timestamp, pm25, pm10, no2, o3, co, so2, aqi, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'openaq')
                    """, (city_id, date_str, pm25, pm10, no2, o3, co, so2,
                          aqi if aqi > 0 else None))
                    if cursor.rowcount > 0:
                        inserted += 1
                except sqlite3.Error as e:
                    print(f"    [DB ERROR] {e}")

            conn.commit()
            total_inserted += inserted
            print(f"    ✓ Inserted {inserted} records")

    conn.close()

    # Summary
    conn2 = get_db_connection()
    c2 = conn2.cursor()
    print(f"\n{'='*60}")
    print(f"  COLLECTION SUMMARY")
    print(f"{'='*60}")
    c2.execute("""
        SELECT c.city_name, COUNT(*), MIN(aq.timestamp), MAX(aq.timestamp)
        FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id
        GROUP BY c.city_name
    """)
    for row in c2.fetchall():
        print(f"  {row[0]}: {row[1]} records ({row[2]} → {row[3]})")
    c2.execute("SELECT COUNT(*) FROM air_quality_readings")
    print(f"  TOTAL: {c2.fetchone()[0]} records in database")
    conn2.close()
    print(f"{'='*60}")


def collect_latest_data():
    """Fetch latest readings for dashboard display."""
    conn = get_db_connection()
    cursor = conn.cursor()
    for city_name, city_info in settings.TARGET_CITIES.items():
        cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city_name,))
        row = cursor.fetchone()
        if not row:
            continue
        city_id = row[0]
        locations = find_locations(city_name, city_info["country_code"],
                                   city_info["latitude"], city_info["longitude"])
        if not locations:
            continue
        # Get latest from the location
        data = _api_get(f"/locations/{locations[0]['id']}/latest")
        readings = {}
        if data and "results" in data:
            for result in data["results"]:
                for sensor in result.get("sensors", []):
                    p = sensor.get("parameter", {})
                    pname = p.get("name", "").lower()
                    latest = sensor.get("latest", {})
                    val = latest.get("value")
                    if pname in settings.POLLUTANT_PARAMETERS and val is not None:
                        readings[pname] = val
        if readings:
            pm25, pm10, no2 = readings.get("pm25"), readings.get("pm10"), readings.get("no2")
            o3, co, so2 = readings.get("o3"), readings.get("co"), readings.get("so2")
            aqi = calculate_overall_aqi(pm25=pm25, pm10=pm10, no2=no2, o3=o3, co=co, so2=so2)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT OR REPLACE INTO air_quality_readings
                (city_id, timestamp, pm25, pm10, no2, o3, co, so2, aqi, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'openaq_latest')
            """, (city_id, ts, pm25, pm10, no2, o3, co, so2, aqi if aqi > 0 else None))
            print(f"  {city_name}: AQI={aqi}, PM2.5={pm25}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    collect_historical_data(days_back=365)