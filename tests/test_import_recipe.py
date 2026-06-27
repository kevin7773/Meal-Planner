from __future__ import annotations

import shutil
import tempfile
import unittest
import re
from pathlib import Path

from scripts.import_recipe import (
    import_recipe,
    parse_html_recipe,
    preview_source,
    preview_text,
    safe_url,
)
from scripts.inventory import validate_inventory
from scripts.validate_recipes import validate_recipe


ROOT = Path(__file__).resolve().parents[1]
PLAIN_RECIPE = """Simple Chicken Pasta

Ingredients
- 1 pound chicken breast
- 8 ounces whole-wheat pasta
- 1 cup tomato sauce

Directions
1. Cook the pasta.
2. Cook the chicken to 165 F.
3. Stir in the tomato sauce and serve.
"""


class RecipeImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")
        shutil.copytree(ROOT / "inventory", self.root / "inventory")
        existing_numbers = []
        for path in (self.root / "recipes").glob("*.md"):
            match = re.search(
                r'(?m)^id = "FDP-(\d{4})"$',
                path.read_text(encoding="utf-8"),
            )
            if match:
                existing_numbers.append(int(match.group(1)))
        self.expected_id = f"FDP-{max(existing_numbers, default=0) + 1:04d}"
        self.source = self.root / "recipe.txt"
        self.source.write_text(PLAIN_RECIPE, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_text_preview_writes_nothing(self) -> None:
        before = {path.name for path in (self.root / "recipes").glob("*.md")}
        preview = preview_source(str(self.source))
        after = {path.name for path in (self.root / "recipes").glob("*.md")}
        self.assertEqual(before, after)
        self.assertEqual(preview["name"], "Simple Chicken Pasta")
        self.assertEqual(len(preview["ingredients"]), 3)

    def test_pasted_text_preview(self) -> None:
        preview = preview_text(PLAIN_RECIPE)
        self.assertEqual(preview["name"], "Simple Chicken Pasta")
        self.assertEqual(preview["source"], "pasted recipe text")

    def test_slow_cooker_duration_is_inferred_from_directions(self) -> None:
        slow_cooker_recipe = """Slow Cooker Chicken

Ingredients
- 1 pound chicken

Directions
1. Cook on low for 3-4 hours.
"""
        preview = preview_text(slow_cooker_recipe)
        self.assertEqual(preview["cook_minutes"], 180)
        _, path = import_recipe(
            "pasted recipe text",
            source_text=slow_cooker_recipe,
            name="Slow Cooker Chicken",
            protein="chicken",
            cooking_method="slow-cooker",
            fiber_grams=8,
            estimated_cost_usd=15,
            kid_friendly_score=4,
            kid_friendly_reason="Mild familiar chicken",
            seasons=["spring", "summer", "fall", "winter"],
            root=self.root,
        )
        self.assertEqual(validate_recipe(path)[3], [])

    def test_import_creates_candidate_and_requirement_entry(self) -> None:
        recipe_id, path = import_recipe(
            str(self.source),
            name="Simple Chicken Pasta",
            protein="chicken",
            cooking_method="stovetop",
            fiber_grams=9,
            estimated_cost_usd=18,
            kid_friendly_score=5,
            kid_friendly_reason="Familiar pasta with mild tomato sauce",
            seasons=["spring", "summer", "fall", "winter"],
            root=self.root,
        )
        self.assertEqual(recipe_id, self.expected_id)
        self.assertTrue(path.exists())
        self.assertEqual(validate_recipe(path)[3], [])
        self.assertEqual(validate_inventory(self.root), [])

    def test_pasted_text_import_creates_candidate(self) -> None:
        recipe_id, path = import_recipe(
            "pasted recipe text",
            source_text=PLAIN_RECIPE,
            name="Pasted Chicken Pasta",
            protein="chicken",
            cooking_method="stovetop",
            fiber_grams=9,
            estimated_cost_usd=18,
            kid_friendly_score=5,
            kid_friendly_reason="Familiar pasta with mild tomato sauce",
            seasons=["spring", "summer", "fall", "winter"],
            root=self.root,
        )
        self.assertEqual(recipe_id, self.expected_id)
        self.assertIn(
            'source = "pasted recipe text"',
            path.read_text(encoding="utf-8"),
        )

    def test_entree_import_records_meal_scope(self) -> None:
        _, path = import_recipe(
            "pasted recipe text",
            source_text=PLAIN_RECIPE,
            name="Entree Chicken",
            protein="chicken",
            meal_scope="entree",
            cooking_method="stovetop",
            fiber_grams=4,
            estimated_cost_usd=12,
            kid_friendly_score=5,
            kid_friendly_reason="Simple familiar chicken",
            seasons=["spring", "summer", "fall", "winter"],
            root=self.root,
        )
        self.assertIn('meal_scope = "entree"', path.read_text(encoding="utf-8"))

    def test_schema_org_recipe_is_extracted(self) -> None:
        page = """<html><script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Recipe","name":"Test Tacos",
         "recipeYield":"4 servings","cookTime":"PT20M",
         "recipeIngredient":["1 pound chicken"],
         "recipeInstructions":[{"@type":"HowToStep","text":"Cook to 165 F."}]}
        </script></html>"""
        preview = parse_html_recipe(page, "https://example.com/tacos")
        self.assertEqual(preview["name"], "Test Tacos")
        self.assertEqual(preview["cook_minutes"], 20)
        self.assertEqual(preview["directions"], ["Cook to 165 F."])

    def test_private_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "private or non-public"):
            safe_url("http://127.0.0.1/recipe")


if __name__ == "__main__":
    unittest.main()
