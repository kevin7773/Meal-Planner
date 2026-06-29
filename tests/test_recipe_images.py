from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validate_recipes import split_recipe


ROOT = Path(__file__).resolve().parents[1]


class RecipeImageTests(unittest.TestCase):
    def test_every_recipe_has_a_valid_placeholder_image(self) -> None:
        images = ROOT / "assets" / "recipes"
        excluded = {"README.md", "index.md", "_template.md"}

        for recipe_path in sorted((ROOT / "recipes").glob("*.md")):
            if recipe_path.name in excluded:
                continue
            metadata, _ = split_recipe(recipe_path)
            image_path = images / f"{metadata['id']}.jpg"

            with self.subTest(recipe_id=metadata["id"]):
                self.assertTrue(image_path.is_file())
                self.assertGreater(image_path.stat().st_size, 10_000)
                content = image_path.read_bytes()
                self.assertTrue(content.startswith(b"\xff\xd8"))
                self.assertTrue(content.endswith(b"\xff\xd9"))


if __name__ == "__main__":
    unittest.main()
