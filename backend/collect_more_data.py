"""
AirVision Extended Data Collector
Searches across ALL Middle East countries on OpenAQ for maximum data coverage.

Strategy:
    1. Search every ME country for locations with PM2.5/PM10 sensors
    2. Fetch daily data going back as far as possible
    3. Also fetch hourly data and aggregate to daily for stations that have it
    4. Add the best stations to the database under the nearest target city
"""

import httpx
import sqlite3
import time
import math
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from app.config import settings
from app.database import get_db_connection
from app.services.aqi_calculator import calculate_overall_aqi

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": settings.OPENAQ_API_KEY, "Accept": "application/json"}
REQUEST_DELAY = 1.5

# ALL Middle East countries on OpenAQ with their numeric IDs
ME_COUNTRIES = {
    "UAE": 59,
    "Saudi Arabia": 106,
    "Kuwait": 116,
    "Qatar": 105,
    "Oman": 40,
}

# Our target cities with coordinates - expanded list
TARGET_CITIES_EXPANDED = {
    "Dubai":     {"lat": 25.2048, "lon": 55.2708, "country_id": 59},
    "Abu Dhabi": {"lat": 24.4539, "lon": 54.3773, "country_id": 59},
    "Riyadh":    {"lat": 24.7136, "lon": 46.6753, "country_id": 106},
    "Kuwait City": {"lat": 29.3759, "lon": 47.9774, "country_id": 116},
    "Doha":      {"lat": 25.2854, "lon": 51.5310, "country_id": 105},
}

# Pollutants we care about
POLLUTANTS = ["pm25", "pm10", "no2", "o3", "co", "so2"]


def _api_get(endpoint, params=None):
    url = f"{OPENAQ_BASE_URL}{endpoint}"
    time.sleep(REQUEST_DELAY)
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers=HEADERS, params=params)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"    [RATE LIMIT] Waiting 60s...")
                time.sleep(60)
                r = client.get(url, headers=HEADERS, params=params)
                return r.json() if r.status_code == 200 else None
            else:
                print(f"    [ERROR {r.status_code}] {r.text[:200]}")
                return None
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def _haversine_km(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearest_city(lat, lon):
    """Find which of our target cities is closest to a given location."""
    best_city = "Dubai"
    best_dist = float("inf")
    for city, info in TARGET_CITIES_EXPANDED.items():
        d = _haversine_km(lat, lon, info["lat"], info["lon"])
        if d < best_dist:
            best_dist = d
            best_city = city
    return best_city, best_dist


def discover_all_stations():
    """Search ALL Middle East countries for air quality stations."""
    print("=" * 60)
    print("  Discovering ALL Middle East stations on OpenAQ...")
    print("=" * 60)

    all_stations = []

    for country_name, country_id in ME_COUNTRIES.items():
        print(f"\n  Searching {country_name} (ID: {country_id})...")
        page = 1
        country_stations = []

        while True:
            data = _api_get("/locations", {
                "countries_id": country_id,
                "limit": 1000,
                "page": page,
            })

            if not data or not data.get("results"):
                break

            for loc in data["results"]:
                coords = loc.get("coordinates", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is None or lon is None:
                    continue

                sensors = loc.get("sensors", [])
                sensor_params = []
                for s in sensors:
                    p = s.get("parameter", {}).get("name", "").lower()
                    if p in POLLUTANTS:
                        sensor_params.append({
                            "sensor_id": s.get("id"),
                            "parameter": p,
                        })

                if sensor_params:
                    nearest_city, dist = find_nearest_city(lat, lon)
                    country_stations.append({
                        "id": loc["id"],
                        "name": loc.get("name", "Unknown"),
                        "country": country_name,
                        "lat": lat,
                        "lon": lon,
                        "sensors": sensor_params,
                        "param_list": [s["parameter"] for s in sensor_params],
                        "nearest_city": nearest_city,
                        "distance_km": round(dist, 1),
                    })

            meta = data.get("meta", {})
            found = meta.get("found", 0)
            if isinstance(found, str) or page * 1000 >= found:
                break
            page += 1

        print(f"    Found {len(country_stations)} stations with relevant sensors")
        all_stations.extend(country_stations)

    print(f"\n  TOTAL: {len(all_stations)} stations across Middle East")
    return all_stations


def fetch_daily_data(sensor_id, date_from=None, date_to=None):
    """Fetch daily aggregated data. Returns list of {date, value}."""
    records = []
    page = 1
    while True:
        params = {"limit": 1000, "page": page}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        data = _api_get(f"/sensors/{sensor_id}/days", params)
        if not data or not data.get("results"):
            break

        for r in data["results"]:
            value = r.get("value")
            if value is None:
                continue
            period = r.get("period", {})
            dt_from = period.get("datetimeFrom", {})
            if isinstance(dt_from, dict):
                date_str = dt_from.get("local", "")[:10] or dt_from.get("utc", "")[:10]
            elif isinstance(dt_from, str):
                date_str = dt_from[:10]
            else:
                continue
            if date_str and len(date_str) == 10:
                records.append({"date": date_str, "value": float(value)})

        meta = data.get("meta", {})
        found = meta.get("found", 0)
        if isinstance(found, str):
            if len(data["results"]) < 1000:
                break
            page += 1
            continue
        if page * 1000 >= found:
            break
        page += 1

    return records


def fetch_hourly_aggregate_to_daily(sensor_id, date_from=None, date_to=None):
    """
    Fetch hourly data and aggregate to daily averages ourselves.
    This often has more data than the /days endpoint.
    """
    hourly_by_date = defaultdict(list)
    page = 1
    max_pages = 20  # cap to avoid excessive API calls

    while page <= max_pages:
        params = {"limit": 1000, "page": page}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        data = _api_get(f"/sensors/{sensor_id}/hours", params)
        if not data or not data.get("results"):
            break

        for r in data["results"]:
            value = r.get("value")
            if value is None:
                continue
            period = r.get("period", {})
            dt_from = period.get("datetimeFrom", {})
            if isinstance(dt_from, dict):
                date_str = dt_from.get("local", "")[:10] or dt_from.get("utc", "")[:10]
            elif isinstance(dt_from, str):
                date_str = dt_from[:10]
            else:
                continue
            if date_str and len(date_str) == 10:
                hourly_by_date[date_str].append(float(value))

        meta = data.get("meta", {})
        found = meta.get("found", 0)
        if isinstance(found, str):
            if len(data["results"]) < 1000:
                break
            page += 1
            continue
        if page * 1000 >= found:
            break
        page += 1

    # Aggregate to daily averages
    records = []
    for date_str, values in sorted(hourly_by_date.items()):
        if len(values) >= 6:  # only include days with 6+ hours of data
            avg = sum(values) / len(values)
            records.append({"date": date_str, "value": round(avg, 2)})

    return records


def ensure_cities_exist():
    """Make sure all expanded cities exist in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    city_timezones = {
        "Dubai": ("AE", 25.2048, 55.2708, "Asia/Dubai"),
        "Abu Dhabi": ("AE", 24.4539, 54.3773, "Asia/Dubai"),
        "Riyadh": ("SA", 24.7136, 46.6753, "Asia/Riyadh"),
        "Kuwait City": ("KW", 29.3759, 47.9774, "Asia/Kuwait"),
        "Doha": ("QA", 25.2854, 51.5310, "Asia/Qatar"),
    }

    for city_name, (country, lat, lon, tz) in city_timezones.items():
        cursor.execute("""
            INSERT OR IGNORE INTO cities (city_name, country, latitude, longitude, timezone)
            VALUES (?, ?, ?, ?, ?)
        """, (city_name, country, lat, lon, tz))

    conn.commit()
    conn.close()
    print("  Cities table updated (5 cities)")


def collect_extended_data():
    """Main extended collection pipeline."""
    print("=" * 60)
    print("  AirVision EXTENDED Data Collection")
    print("  Searching ALL Middle East countries")
    print("  (This may take 30-45 minutes)")
    print("=" * 60)

    if not settings.OPENAQ_API_KEY or "your-openaq" in settings.OPENAQ_API_KEY:
        print("[ERROR] Set your OpenAQ API key in .env!")
        return

    # Ensure all cities exist in database
    ensure_cities_exist()

    # Step 1: Discover all stations
    all_stations = discover_all_stations()

    if not all_stations:
        print("[ERROR] No stations found!")
        return

    # Step 2: Sort by nearest city and prioritize multi-pollutant stations
    all_stations.sort(key=lambda s: (-len(s["sensors"]), s["distance_km"]))

    # Group by nearest city
    city_stations = defaultdict(list)
    for station in all_stations:
        city = station["nearest_city"]
        if station["distance_km"] <= 200:  # within 200km of a target city
            city_stations[city].append(station)

    print(f"\n{'='*60}")
    print(f"  STATION SUMMARY BY CITY")
    print(f"{'='*60}")
    for city, stations in city_stations.items():
        print(f"  {city}: {len(stations)} stations")
        for s in stations[:5]:
            print(f"    - {s['name']} ({s['country']}, {s['distance_km']}km): {s['param_list']}")

    # Step 3: Collect data
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Go back 5 years for maximum coverage
    date_from = (now - timedelta(days=1825)).strftime("%Y-%m-%dT%H:%M:%SZ")

    total_inserted = 0

    for city_name, stations in city_stations.items():
        print(f"\n{'─'*50}")
        print(f"  Collecting for: {city_name} ({len(stations)} stations)")
        print(f"{'─'*50}")

        cursor.execute("SELECT city_id FROM cities WHERE city_name = ?", (city_name,))
        row = cursor.fetchone()
        if not row:
            print(f"  [SKIP] City not in database")
            continue
        city_id = row[0]

        # Use up to 5 best stations per city
        for station in stations[:5]:
            sid = station["id"]
            sname = station["name"]
            dist = station["distance_km"]
            params = station["param_list"]

            print(f"\n  Station: {sname} (ID:{sid}, {dist}km, {station['country']})")
            print(f"    Pollutants: {params}")

            daily_data = {}

            for sensor_info in station["sensors"]:
                param = sensor_info["parameter"]
                sensor_id = sensor_info["sensor_id"]
                print(f"    Fetching {param} (sensor {sensor_id})...", end=" ")

                # Try /days first
                records = fetch_daily_data(sensor_id, date_from, date_to)

                # If /days returns very little, try /hours aggregated
                if len(records) < 30:
                    print(f"days:{len(records)}", end=" ")
                    hourly_records = fetch_hourly_aggregate_to_daily(sensor_id, date_from, date_to)
                    if len(hourly_records) > len(records):
                        records = hourly_records
                        print(f"→ hours:{len(records)}")
                    else:
                        print(f"→ hours:{len(hourly_records)} (keeping days)")
                else:
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
                    pass  # silently skip duplicates

            conn.commit()
            total_inserted += inserted
            if inserted > 0:
                print(f"    ✓ Inserted {inserted} new records")
            else:
                print(f"    (no new records - already in database)")

    conn.close()

    # Final summary
    conn2 = get_db_connection()
    c2 = conn2.cursor()
    print(f"\n{'='*60}")
    print(f"  EXTENDED COLLECTION COMPLETE")
    print(f"{'='*60}")
    print(f"  New records added: {total_inserted}")
    print()
    c2.execute("""
        SELECT c.city_name, COUNT(*) as records,
               SUM(CASE WHEN pm25 IS NOT NULL THEN 1 ELSE 0 END) as pm25,
               SUM(CASE WHEN pm10 IS NOT NULL THEN 1 ELSE 0 END) as pm10,
               SUM(CASE WHEN no2 IS NOT NULL THEN 1 ELSE 0 END) as no2,
               SUM(CASE WHEN o3 IS NOT NULL THEN 1 ELSE 0 END) as o3,
               SUM(CASE WHEN co IS NOT NULL THEN 1 ELSE 0 END) as co,
               SUM(CASE WHEN so2 IS NOT NULL THEN 1 ELSE 0 END) as so2,
               MIN(aq.timestamp), MAX(aq.timestamp)
        FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        GROUP BY c.city_name
        ORDER BY records DESC
    """)
    for row in c2.fetchall():
        print(f"  {row[0]}: {row[1]} records ({row[8]} to {row[9]})")
        print(f"    PM2.5:{row[2]} PM10:{row[3]} NO2:{row[4]} O3:{row[5]} CO:{row[6]} SO2:{row[7]}")
    c2.execute("SELECT COUNT(*) FROM air_quality_readings")
    total = c2.fetchone()[0]
    print(f"\n  GRAND TOTAL: {total} records")
    conn2.close()
    print(f"{'='*60}")


if __name__ == "__main__":
    collect_extended_data()