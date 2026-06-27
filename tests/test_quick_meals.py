from __future__ import annotations

import datetime as dt
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.quick_meals import (
    PARENTS_ONLY_REASON,
    suggest_quick_meal,
    validate_quick_meals,
)


ROOT = Path(__file__).resolve().parents[1]


class QuickMealTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "quick-meals", self.root / "quick-meals")
        shutil.copytree(ROOT / "inventory", self.root / "inventory")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_quick_meal_library_is_valid(self) -> None:
        self.assertEqual(validate_quick_meals(self.root), [])

    def test_parents_only_recipe_gets_a_rotating_kid_meal(self) -> None:
        recipe = {
            "id": "FDP-0099",
            "kid_friendly_reason": PARENTS_ONLY_REASON,
        }
        first = suggest_quick_meal(
            recipe,
            week_of=dt.date(2026, 6, 29),
            day_index=2,
            root=self.root,
        )
        second = suggest_quick_meal(
            recipe,
            week_of=dt.date(2026, 7, 6),
            day_index=2,
            root=self.root,
        )
        self.assertIsNotNone(first)
        self.assertNotEqual(first["id"], second["id"])

    def test_family_recipe_does_not_get_a_quick_meal(self) -> None:
        self.assertIsNone(
            suggest_quick_meal(
                {"id": "FDP-0001", "kid_friendly_reason": "Gray Loves It"},
                week_of=dt.date(2026, 6, 29),
                day_index=0,
                root=self.root,
            )
        )

