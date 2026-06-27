from __future__ import annotations

import datetime as dt
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
