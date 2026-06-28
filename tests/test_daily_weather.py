from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.daily_weather import get_daily_forecast


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class DailyWeatherTests(unittest.TestCase):
    def test_forecast_uses_configured_location_and_daily_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "preferences").mkdir()
            (root / "preferences" / "weather-rules.json").write_text(
                json.dumps({"forecast_location": "21617"}),
                encoding="utf-8",
            )
            requested_urls = []

            def opener(request, timeout):
                requested_urls.append(request.full_url)
                if "geocoding-api" in request.full_url:
                    payload = {
                        "results": [
                            {
                                "name": "Centreville",
                                "admin1": "Maryland",
                                "latitude": 39.04,
                                "longitude": -76.06,
                            }
                        ]
                    }
                else:
                    payload = {
                        "daily": {
                            "time": ["2026-06-27"],
                            "weather_code": [2],
                            "temperature_2m_max": [91.4],
                            "temperature_2m_min": [72.1],
                            "precipitation_probability_max": [35],
                        }
                    }
                return FakeResponse(json.dumps(payload).encode())

            forecast = get_daily_forecast(root, opener=opener)

        self.assertEqual(forecast["location"], "Centreville")
        self.assertEqual(forecast["high_f"], 91)
        self.assertEqual(forecast["low_f"], 72)
        self.assertEqual(forecast["description"], "Partly cloudy")
        self.assertEqual(forecast["precipitation_probability"], 35)
        self.assertIn("name=21617", requested_urls[0])
        self.assertIn("temperature_unit=fahrenheit", requested_urls[1])


if __name__ == "__main__":
    unittest.main()
