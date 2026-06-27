from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.side_dishes import suggest_sides, validate_sides


ROOT = Path(__file__).resolve().parents[1]


class SideDishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in ("sides", "inventory", "recipes"):
            shutil.copytree(ROOT / directory, self.root / directory)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_side_library_is_valid(self) -> None:
        self.assertEqual(validate_sides(self.root), [])

    def test_side_library_rejects_non_integer_schema_version(self) -> None:
        path = self.root / "sides" / "side-dishes.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["schema_version"] = "1"
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assertIn(
            "sides/side-dishes.json: schema_version must be an integer",
            validate_sides(self.root),
        )

    def test_entree_receives_two_compatible_suggestions(self) -> None:
        recipe = {
            "name": "Smoked Whole Chicken",
            "meal_scope": "entree",
            "cooking_method": "smoker",
        }
        suggestions = suggest_sides(
            recipe,
            season="summer",
            week_of=dt.date(2026, 7, 6),
            root=self.root,
        )
        self.assertEqual(len(suggestions), 2)
        self.assertTrue(all("summer" in side["seasons"] for side in suggestions))
        self.assertTrue(all(side["kid_friendly_score"] >= 4 for side in suggestions))

    def test_complete_meal_receives_no_suggestions(self) -> None:
        recipe = {
            "name": "Chicken Stir-Fry with Rice",
            "meal_scope": "complete-meal",
            "cooking_method": "stovetop",
        }
        self.assertEqual(
            suggest_sides(
                recipe,
                season="summer",
                week_of=dt.date(2026, 7, 6),
                root=self.root,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
