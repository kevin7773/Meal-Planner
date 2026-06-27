from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.dry_run import generate_proposals
from scripts.recipe_ideas import add_idea, load_ideas, validate_ideas


ROOT = Path(__file__).resolve().parents[1]


class RecipeIdeaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in ("recipes", "inventory", "preferences", "quick-meals", "sides"):
            shutil.copytree(ROOT / directory, self.root / directory)
        (self.root / "ideas").mkdir()
        (self.root / "ideas" / "recipe-ideas.json").write_text(
            json.dumps({"schema_version": 1, "next_id": 1, "ideas": []}) + "\n",
            encoding="utf-8",
        )
        self.expected_id = (
            f"IDEA-USER-{load_ideas(self.root)['next_id']:04d}"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_stir_fry_idea(self) -> str:
        return add_idea(
            "Teriyaki chicken and vegetable stir-fry with rice",
            name="Teriyaki Chicken Vegetable Stir-Fry",
            protein="chicken",
            cooking_method="blackstone",
            fiber_grams=9,
            estimated_cost_usd=23,
            kid_friendly_score=4,
            kid_friendly_reason="Familiar chicken and rice with sauce served separately",
            seasons=["spring", "summer", "fall", "winter"],
            root=self.root,
        )

    def test_adds_stable_queued_idea(self) -> None:
        idea_id = self.add_stir_fry_idea()
        self.assertEqual(idea_id, self.expected_id)
        self.assertEqual(validate_ideas(self.root), [])
        idea = next(
            item
            for item in load_ideas(self.root)["ideas"]
            if item["id"] == idea_id
        )
        self.assertEqual(idea["status"], "queued")

    def test_queued_idea_is_surfaced_in_dry_runs(self) -> None:
        idea_id = self.add_stir_fry_idea()
        proposals = generate_proposals(dt.date(2026, 7, 6), 3, root=self.root)
        self.assertTrue(
            any(idea_id in proposal["assignments"] for proposal in proposals)
        )

    def test_parents_only_idea_is_valid_but_not_family_friendly(self) -> None:
        add_idea(
            "A spicy dinner for the adults",
            name="Spicy Adult Dinner",
            protein="other",
            cooking_method="stovetop",
            fiber_grams=8,
            estimated_cost_usd=20,
            kid_friendly_score=1,
            kid_friendly_reason="Not kid friendly - for the parents only",
            seasons=["fall", "winter"],
            root=self.root,
        )
        self.assertEqual(validate_ideas(self.root), [])


if __name__ == "__main__":
    unittest.main()
