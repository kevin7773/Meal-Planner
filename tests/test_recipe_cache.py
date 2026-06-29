from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.eligibility import load_recipes
from planner.recipe_cache import (
    build_recipe_cache,
    load_recipe_cache,
    recipe_cache_is_fresh,
    recipe_cache_path,
)


ROOT = Path(__file__).resolve().parents[1]


class RecipeCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")
        shutil.copytree(ROOT / "assets" / "recipes", self.root / "assets" / "recipes")
        shutil.copytree(ROOT / "inventory", self.root / "inventory")
        (self.root / "planner-data").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_build_writes_cache_document(self) -> None:
        document = build_recipe_cache(self.root)
        path = recipe_cache_path(self.root)

        self.assertTrue(path.exists())
        self.assertEqual(document["schema_version"], 1)
        fajitas = next(
            item for item in document["recipes"] if item["id"] == "FDP-0001"
        )
        self.assertEqual(fajitas["image"]["recipe_id"], "FDP-0001")
        self.assertEqual(
            sorted(item["id"] for item in document["recipes"]),
            sorted(load_recipes(self.root).keys()),
        )

    def test_load_rebuilds_stale_cache_after_recipe_change(self) -> None:
        first = build_recipe_cache(self.root)
        recipe_path = self.root / "recipes" / "chicken-fajitas.md"
        updated = re.sub(
            r'(?m)^name = ".*"$',
            'name = "Updated Chicken Fajitas"',
            recipe_path.read_text(encoding="utf-8"),
            count=1,
        )
        recipe_path.write_text(updated, encoding="utf-8", newline="\n")

        self.assertFalse(recipe_cache_is_fresh(first, root=self.root))
        refreshed = load_recipe_cache(self.root)

        fajitas = next(
            item for item in refreshed["recipes"] if item["id"] == "FDP-0001"
        )
        self.assertEqual(fajitas["name"], "Updated Chicken Fajitas")

    def test_load_recipes_uses_cached_records(self) -> None:
        build_recipe_cache(self.root)
        path = recipe_cache_path(self.root)
        document = json.loads(path.read_text(encoding="utf-8"))
        for recipe in document["recipes"]:
            if recipe["id"] == "FDP-0001":
                recipe["estimated_cost_usd"] = 99
                break
        for source in document["sources"]:
            if source["filename"] == "chicken-fajitas.md":
                break
        path.write_text(
            json.dumps(document, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        recipes = load_recipes(self.root)

        self.assertEqual(recipes["FDP-0001"]["estimated_cost_usd"], 99)


if __name__ == "__main__":
    unittest.main()
