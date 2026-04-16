"""
AirVision AQI Calculator
Calculates the Air Quality Index (AQI) from pollutant concentrations
using the US EPA breakpoint methodology.
"""


# EPA AQI Breakpoint Table
# Format: (C_low, C_high, I_low, I_high)
# C = concentration, I = AQI value

AQI_BREAKPOINTS = {
    "pm25": [
        (0.0, 9.0, 0, 50),
        (9.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 125.4, 151, 200),
        (125.5, 225.4, 201, 300),
        (225.5, 325.4, 301, 500),
    ],
    "pm10": [
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 604, 301, 500),
    ],
    "no2": [
        (0, 53, 0, 50),
        (54, 100, 51, 100),
        (101, 360, 101, 150),
        (361, 649, 151, 200),
        (650, 1249, 201, 300),
        (1250, 2049, 301, 500),
    ],
    "o3": [
        (0, 54, 0, 50),
        (55, 70, 51, 100),
        (71, 85, 101, 150),
        (86, 105, 151, 200),
        (106, 200, 201, 300),
        (201, 604, 301, 500),
    ],
    "co": [
        (0.0, 4.4, 0, 50),
        (4.5, 9.4, 51, 100),
        (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200),
        (15.5, 30.4, 201, 300),
        (30.5, 50.4, 301, 500),
    ],
    "so2": [
        (0, 35, 0, 50),
        (36, 75, 51, 100),
        (76, 185, 101, 150),
        (186, 304, 151, 200),
        (305, 604, 201, 300),
        (605, 1004, 301, 500),
    ],
}


def calculate_pollutant_aqi(pollutant: str, concentration: float) -> int:
    """
    Calculate the AQI for a single pollutant given its concentration.
    the pollutant: One of 'pm25', 'pm10', 'no2', 'o3', 'co', 'so2'
    concentration: The measured concentration value
    Returns:
        Integer AQI value (0–500), or -1 if invalid
    """
    if concentration is None or concentration < 0:
        return -1

    breakpoints = AQI_BREAKPOINTS.get(pollutant)
    if not breakpoints:
        return -1

    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= concentration <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (concentration - c_low) + i_low
            return round(aqi)

    # If concentration exceeds all breakpoints, cap at 500
    if concentration > breakpoints[-1][1]:
        return 500

    return -1


def calculate_overall_aqi(pm25=None, pm10=None, no2=None, o3=None, co=None, so2=None) -> int:

    pollutant_values = {
        "pm25": pm25,
        "pm10": pm10,
        "no2": no2,
        "o3": o3,
        "co": co,
        "so2": so2,
    }

    individual_aqis = []
    for pollutant, concentration in pollutant_values.items():
        if concentration is not None and concentration >= 0:
            aqi = calculate_pollutant_aqi(pollutant, concentration)
            if aqi >= 0:
                individual_aqis.append(aqi)

    return max(individual_aqis) if individual_aqis else 0


def get_aqi_category(aqi: int) -> dict:
    """
    Get the AQI category, colour, and health advisory for a given AQI value.

    Args:
        aqi: Integer AQI value (0–500)

    Returns:
        Dictionary with 'category', 'color', and 'health_advisory' keys
    """
    categories = [
        (0, 50, "Good", "#22C55E",
         "Air quality is satisfactory. Enjoy outdoor activities."),
        (51, 100, "Moderate", "#F59E0B",
         "Air quality is acceptable. Sensitive individuals should consider reducing prolonged outdoor exertion."),
        (101, 150, "Unhealthy for Sensitive Groups", "#F97316",
         "Members of sensitive groups may experience health effects. Reduce prolonged outdoor exertion."),
        (151, 200, "Unhealthy", "#EF4444",
         "Everyone may begin to experience health effects. Limit outdoor activity."),
        (201, 300, "Very Unhealthy", "#8B5CF6",
         "Health alert: everyone may experience serious health effects. Avoid outdoor activity."),
        (301, 500, "Hazardous", "#7F1D1D",
         "Health emergency: the entire population is likely to be affected. Stay indoors."),
    ]

    for aqi_low, aqi_high, category, color, advisory in categories:
        if aqi_low <= aqi <= aqi_high:
            return {
                "category": category,
                "color": color,
                "health_advisory": advisory
            }

    return {
        "category": "Unknown",
        "color": "#6B7280",
        "health_advisory": "AQI data is not available."
    }


# ─── Quick test ───
if __name__ == "__main__":
    # Test with sample values
    test_aqi = calculate_overall_aqi(pm25=45.2, pm10=89.1, no2=28.4, o3=52.1, co=0.8, so2=4.2)
    info = get_aqi_category(test_aqi)
    print(f"Test AQI: {test_aqi}")
    print(f"Category: {info['category']}")
    print(f"Color: {info['color']}")
    print(f"Advisory: {info['health_advisory']}")
