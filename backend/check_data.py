from app.database import get_db_connection
conn = get_db_connection()
c = conn.cursor()

print("=== DATA QUALITY CHECK ===\n")

for city in ["Dubai", "Abu Dhabi", "Riyadh"]:
    c.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN pm25 IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN pm10 IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN no2 IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN o3 IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN co IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN so2 IS NOT NULL THEN 1 ELSE 0 END),
               MIN(timestamp), MAX(timestamp)
        FROM air_quality_readings aq
        JOIN cities c ON aq.city_id = c.city_id
        WHERE c.city_name = ?
    """, (city,))
    r = c.fetchone()
    print(f"{city}: {r[0]} records ({r[7]} to {r[8]})")
    print(f"  PM2.5: {r[1]}  PM10: {r[2]}  NO2: {r[3]}  O3: {r[4]}  CO: {r[5]}  SO2: {r[6]}\n")

c.execute("SELECT COUNT(*) FROM (SELECT timestamp, city_id, COUNT(*) as cnt FROM air_quality_readings GROUP BY timestamp, city_id HAVING cnt > 1)")
print(f"Duplicate rows: {c.fetchone()[0]}\n")

print("=== SAMPLE: Dubai (last 5) ===")
c.execute("SELECT timestamp, pm25, pm10, aqi FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id WHERE c.city_name = 'Dubai' ORDER BY timestamp DESC LIMIT 5")
for row in c.fetchall():
    print(f"  {row[0]}  PM2.5={row[1]}  PM10={row[2]}  AQI={row[3]}")

print("\n=== SAMPLE: Abu Dhabi (last 5) ===")
c.execute("SELECT timestamp, pm25, pm10, no2, o3, co, so2, aqi FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id WHERE c.city_name = 'Abu Dhabi' ORDER BY timestamp DESC LIMIT 5")
for row in c.fetchall():
    print(f"  {row[0]}  PM2.5={row[1]}  PM10={row[2]}  NO2={row[3]}  O3={row[4]}  CO={row[5]}  SO2={row[6]}  AQI={row[7]}")

print("\n=== SAMPLE: Riyadh (last 5) ===")
c.execute("SELECT timestamp, pm25, pm10, aqi FROM air_quality_readings aq JOIN cities c ON aq.city_id = c.city_id WHERE c.city_name = 'Riyadh' ORDER BY timestamp DESC LIMIT 5")
for row in c.fetchall():
    print(f"  {row[0]}  PM2.5={row[1]}  PM10={row[2]}  AQI={row[3]}")

conn.close()