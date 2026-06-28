from __future__ import annotations

import shutil
import tempfile
import unittest
import re
from pathlib import Path

from planner.recipe_editor import (
    find_imported_recipe,
    imported_recipes,
    update_imported_recipe,
)
from scripts.validate_recipes import split_recipe, validate_recipe


ROOT = Path(__file__).resolve().parents[1]


class RecipeEditorTests(unittest.TestCase):
    def make_root(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "recipes").mkdir()
        shutil.copy2(
            ROOT / "recipes" / "10-minute-pasta.md",
            root / "recipes" / "10-minute-pasta.md",
        )
        recipe_path = root / "recipes" / "10-minute-pasta.md"
        recipe_text = recipe_path.read_text(encoding="utf-8")
        recipe_text = re.sub(
            r'(?m)^kid_friendly_reason = ".*"$',
            'kid_friendly_reason = "Legacy freeform reason"',
            recipe_text,
            count=1,
        )
        recipe_text = re.sub(
            r"(?m)^-\s+\*\*Kid-friendly design:\*\*.*$",
            "- **Kid-friendly design:** Legacy freeform reason",
            recipe_text,
            count=1,
        )
        recipe_text = re.sub(
            r'(?m)^meal_scope = ".*"\n',
            "",
            recipe_text,
            count=1,
        )
        recipe_path.write_text(
            recipe_text,
            encoding="utf-8",
            newline="\n",
        )
        shutil.copy2(
            ROOT / "recipes" / "index.md",
            root / "recipes" / "index.md",
        )
        return temporary, root

    def test_lists_only_imported_recipes_and_flags_legacy_reason(self) -> None:
        temporary, root = self.make_root()
        with temporary:
            recipes = imported_recipes(root)

        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["id"], "FDP-0012")
        self.assertFalse(recipes[0]["kid_reason_is_current"])

    def test_update_creates_valid_revision_and_preserves_recipe_body(self) -> None:
        temporary, root = self.make_root()
        with temporary:
            starting_revision = split_recipe(
                root / "recipes" / "10-minute-pasta.md"
            )[0]["revision"]
            revision, path = update_imported_recipe(
                "FDP-0012",
                name="10 Minute Pasta",
                protein="vegetarian",
                meal_scope="complete-meal",
                prep_minutes=5,
                cook_minutes=10,
                fiber_grams=8,
                estimated_cost_usd=6,
                kid_friendly_reason="Both children like/love it",
                cooking_method="stovetop",
                seasons=["spring", "summer", "fall", "winter"],
                change_note="Corrected times and kid reason",
                root=root,
            )
            recipe_id, metadata, body, errors = validate_recipe(path)
            loaded = find_imported_recipe("FDP-0012", root)
            index = (root / "recipes" / "index.md").read_text(
                encoding="utf-8"
            )

        self.assertEqual(errors, [])
        self.assertEqual(recipe_id, "FDP-0012")
        self.assertEqual(revision, starting_revision + 1)
        self.assertEqual(metadata["revision"], starting_revision + 1)
        self.assertEqual(metadata["meal_scope"], "complete-meal")
        self.assertEqual(metadata["cook_time_minutes"], 10)
        self.assertEqual(metadata["kid_friendly_score"], 5)
        self.assertIn("1/4 cup olive oil", body)
        self.assertIn("**Active prep:** 5 minutes", body)
        self.assertIn("Corrected times and kid reason", body)
        self.assertIn("| FDP-0012 | [10 Minute Pasta]", index)
        self.assertEqual(loaded["prep_minutes"], 5)
        self.assertTrue(loaded["kid_reason_is_current"])

    def test_rejects_freeform_kid_reason_without_writing(self) -> None:
        temporary, root = self.make_root()
        with temporary:
            path = root / "recipes" / "10-minute-pasta.md"
            before = path.read_text(encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "current"):
                update_imported_recipe(
                    "FDP-0012",
                    name="10 Minute Pasta",
                    protein="vegetarian",
                    meal_scope="complete-meal",
                    prep_minutes=5,
                    cook_minutes=10,
                    fiber_grams=8,
                    estimated_cost_usd=6,
                    kid_friendly_reason="Kids like pasta",
                    cooking_method="stovetop",
                    seasons=["spring", "summer"],
                    root=root,
                )
            after = path.read_text(encoding="utf-8")

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
