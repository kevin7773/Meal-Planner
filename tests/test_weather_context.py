from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.weather_context import (
    is_heat_friendly,
    load_weather_context,
    load_weather_rules,
    validate_weather,
)


ROOT = Path(__file__).resolve().parents[1]


class WeatherContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "preferences", self.root / "preferences")
        shutil.copytree(ROOT / "weather", self.root / "weather")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_weather_configuration_is_valid(self) -> None:
        self.assertEqual(validate_weather(self.root), [])

    def test_weather_rules_reject_unsupported_schema_version(self) -> None:
        path = self.root / "preferences" / "weather-rules.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["schema_version"] = 2
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assertIn(
            "preferences/weather-rules.json: unsupported schema_version 2; "
            "supported version(s): 1",
            validate_weather(self.root),
        )

    def test_weekly_weather_context_requires_schema_version(self) -> None:
        path = self.root / "weather" / "2026" / "2026-06-29.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        del document["schema_version"]
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assertIn(
            "weather/2026/2026-06-29.json: schema_version is required",
            validate_weather(self.root),
        )

    def test_weekly_extreme_heat_context_loads(self) -> None:
        context = load_weather_context(dt.date(2026, 6, 29), self.root)
        self.assertEqual(context["category"], "extreme-heat")

    def test_grill_and_no_cook_are_heat_friendly(self) -> None:
        rules = load_weather_rules(self.root)
        self.assertTrue(
            is_heat_friendly(
                {"cooking_method": "grill", "status": "candidate", "tags": []},
                rules,
            )
        )
        self.assertFalse(
            is_heat_friendly(
                {"cooking_method": "oven", "status": "candidate", "tags": []},
                rules,
            )
        )


if __name__ == "__main__":
    unittest.main()
