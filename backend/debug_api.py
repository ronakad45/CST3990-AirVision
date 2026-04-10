"""
Quick debug script - tests what data OpenAQ actually has for our sensors.
Run from backend folder: python debug_api.py
"""

import httpx
import json
import time
from app.config import settings

BASE = "https://api.openaq.org/v3"
H = {"X-API-Key": settings.OPENAQ_API_KEY, "Accept": "application/json"}


def get(endpoint, params=None, label=""):
    time.sleep(1.5)
    url = f"{BASE}{endpoint}"
    print(f"\n  [{label}] GET {endpoint}")
    print(f"  Params: {params}")
    try:
        r = httpx.get(url, headers=H, params=params, timeout=30)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            found = data.get("meta", {}).get("found", "?")
            results = data.get("results", [])
            print(f"  Found: {found}, returned: {len(results)}")
            if results:
                print(f"  First result:\n{json.dumps(results[0], indent=2, default=str)[:800]}")
            return data
        else:
            print(f"  Error: {r.text[:300]}")
    except Exception as e:
        print(f"  Exception: {e}")
    return None


print("=" * 60)
print("  OpenAQ API Debug - Testing endpoints for our sensors")
print(f"  API Key: {settings.OPENAQ_API_KEY[:10]}...")
print("=" * 60)

# Known sensor IDs from your previous run
test_sensors = [
    ("Abu Dhabi PM10", 2084160),
    ("Abu Dhabi NO2", 2084237),
    ("Dubai PM2.5 (Business Bay)", 14384841),
    ("Riyadh PM2.5", 1342889),
]

for name, sid in test_sensors:
    print(f"\n{'='*60}")
    print(f"  TESTING: {name} (sensor {sid})")
    print(f"{'='*60}")

    # Test 1: /measurements WITHOUT date filter (what the examples page shows)
    get(f"/sensors/{sid}/measurements", {"limit": 3}, "measurements NO dates")

    # Test 2: /measurements WITH date filter
    get(f"/sensors/{sid}/measurements", {"date_from": "2024-01-01", "date_to": "2025-12-31", "limit": 3}, "measurements WITH dates")

    # Test 3: /days WITHOUT date filter
    get(f"/sensors/{sid}/days", {"limit": 3}, "days NO dates")

    # Test 4: /days WITH date filter
    get(f"/sensors/{sid}/days", {"date_from": "2024-01-01", "date_to": "2025-12-31", "limit": 3}, "days WITH dates")

    # Test 5: /hours WITHOUT date filter
    get(f"/sensors/{sid}/hours", {"limit": 3}, "hours NO dates")

print(f"\n{'='*60}")
print("  DEBUG COMPLETE")
print("="*60)