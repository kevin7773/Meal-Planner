from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.recipe_cache import build_recipe_cache
from planner.recipe_images import (
    build_recipe_image_metadata,
    recipe_image_metadata_path,
    record_recipe_image,
)


ROOT = Path(__file__).resolve().parents[1]


class RecipeImageMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")
        shutil.copytree(ROOT / "assets" / "recipes", self.root / "assets" / "recipes")
        (self.root / "planner-data").mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_build_writes_placeholder_image_metadata(self) -> None:
        document = build_recipe_image_metadata(self.root)
        record = document["recipes"]["FDP-0001"]
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(record["source_type"], "placeholder-generated")
        self.assertEqual(record["filename"], "FDP-0001.jpg")

    def test_record_recipe_image_updates_metadata_and_cache(self) -> None:
        build_recipe_image_metadata(self.root)
        target = self.root / "assets" / "recipes" / "FDP-0001.png"
        target.write_bytes((self.root / "assets" / "recipes" / "FDP-0001.jpg").read_bytes())

        record_recipe_image(
            "FDP-0001",
            root=self.root,
            source_type="user-upload",
            source="C:/photos/fajitas.png",
            prompt="Family photo of chicken fajitas",
        )
        cache = build_recipe_cache(self.root)
        document = json.loads(
            recipe_image_metadata_path(self.root).read_text(encoding="utf-8")
        )

        self.assertEqual(
            document["recipes"]["FDP-0001"]["source_type"],
            "user-upload",
        )
        fajitas = next(
            recipe for recipe in cache["recipes"] if recipe["id"] == "FDP-0001"
        )
        self.assertEqual(fajitas["image"]["source_type"], "user-upload")


if __name__ == "__main__":
    unittest.main()
