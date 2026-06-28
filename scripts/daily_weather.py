from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEATHER_CODES = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Cloudy",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorms",
    96: "Thunderstorms with hail",
    99: "Severe thunderstorms with hail",
}


def fetch_json(
    url: str,
    *,
    opener=urllib.request.urlopen,
) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FamilyMealPlanner/1.0"},
    )
    with opener(request, timeout=5) as response:
        return json.load(response)


def get_daily_forecast(
    root: Path = ROOT,
    *,
    opener=urllib.request.urlopen,
) -> dict:
    rules = json.loads(
        (root / "preferences" / "weather-rules.json").read_text(
            encoding="utf-8"
        )
    )
    location = str(rules.get("forecast_location", "")).strip()
    if not location:
        raise ValueError("forecast_location is not configured")

    geocode_query = urllib.parse.urlencode(
        {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json",
            "countryCode": "US",
        }
    )
    geocode = fetch_json(
        "https://geocoding-api.open-meteo.com/v1/search?"
        + geocode_query,
        opener=opener,
    )
    results = geocode.get("results", [])
    if not results:
        raise ValueError(f"Weather location was not found: {location}")
    place = results[0]

    forecast_query = urllib.parse.urlencode(
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": (
                "weather_code,temperature_2m_max,"
                "temperature_2m_min,precipitation_probability_max"
            ),
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
            "forecast_days": 1,
        }
    )
    forecast = fetch_json(
        "https://api.open-meteo.com/v1/forecast?" + forecast_query,
        opener=opener,
    )
    daily = forecast["daily"]
    weather_code = int(daily["weather_code"][0])
    return {
        "schema_version": 1,
        "date": daily["time"][0],
        "location": place["name"],
        "region": place.get("admin1", ""),
        "postal_code": location,
        "high_f": round(float(daily["temperature_2m_max"][0])),
        "low_f": round(float(daily["temperature_2m_min"][0])),
        "precipitation_probability": int(
            daily["precipitation_probability_max"][0]
        ),
        "weather_code": weather_code,
        "description": WEATHER_CODES.get(
            weather_code,
            "Variable conditions",
        ),
        "source": "Open-Meteo",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch today's configured meal-planning forecast."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        forecast = get_daily_forecast()
    except (KeyError, OSError, ValueError) as error:
        print(f"Daily weather unavailable: {error}")
        return 1
    if args.json:
        print(json.dumps(forecast))
    else:
        print(
            f"{forecast['location']}: {forecast['description']}, "
            f"{forecast['high_f']}/{forecast['low_f']} F, "
            f"{forecast['precipitation_probability']}% precipitation"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
