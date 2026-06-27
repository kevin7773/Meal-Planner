from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.dry_run import (
    apply_proposal,
    commit_assignments,
    evaluate_proposal,
    generate_proposals,
    load_recipes,
    selection_explanation,
)
from scripts.menu_status import validate_menu
from scripts.quick_meals import PARENTS_ONLY_REASON
from scripts.weather_context import load_weather_rules


ROOT = Path(__file__).resolve().parents[1]


def file_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


class DryRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        shutil.copytree(ROOT / "recipes", self.root / "recipes")
        shutil.copytree(ROOT / "inventory", self.root / "inventory")
        shutil.copytree(ROOT / "planner-data", self.root / "planner-data")
        shutil.copytree(ROOT / "quick-meals", self.root / "quick-meals")
        (self.root / "preferences").mkdir()
        shutil.copy2(
            ROOT / "preferences" / "meal-history.md",
            self.root / "preferences" / "meal-history.md",
        )
        shutil.copy2(
            ROOT / "preferences" / "weather-rules.json",
            self.root / "preferences" / "weather-rules.json",
        )
        (self.root / "menus").mkdir()
        self.week = dt.date(2026, 6, 29)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def keep_only_original_four_recipes(self) -> None:
        for recipe in load_recipes(self.root).values():
            number = int(recipe["id"].split("-")[1])
            if number > 4:
                Path(recipe["path"]).unlink()

    def test_generate_three_proposals_without_writing_files(self) -> None:
        self.keep_only_original_four_recipes()
        before = file_snapshot(self.root)
        proposals = generate_proposals(self.week, 3, root=self.root)
        after = file_snapshot(self.root)
        self.assertEqual(before, after)
        self.assertEqual(len(proposals), 3)
        self.assertTrue(all(len(proposal["meals"]) == 7 for proposal in proposals))
        signatures = {tuple(proposal["assignments"]) for proposal in proposals}
        self.assertEqual(len(signatures), 3)
        for first_index, first in enumerate(proposals):
            protein_counts = {
                protein: sum(
                    meal["protein"] == protein for meal in first["meals"]
                )
                for protein in {meal["protein"] for meal in first["meals"]}
            }
            self.assertLessEqual(max(protein_counts.values()), 3)
            for second in proposals[first_index + 1 :]:
                overlap = set(first["assignments"]) & set(second["assignments"])
                self.assertLessEqual(len(overlap), 2)
        canonical_ids = {"FDP-0001", "FDP-0002", "FDP-0003", "FDP-0004"}
        self.assertTrue(
            any(
                set(proposal["assignments"]) & canonical_ids
                for proposal in proposals
            )
        )
        for proposal in proposals:
            self.assertTrue(
                any(
                    recipe_id.startswith("IDEA-")
                    for recipe_id in proposal["assignments"]
                )
            )

    def test_proposal_reports_cost_fiber_rotation_and_warnings(self) -> None:
        proposal = generate_proposals(self.week, 1, root=self.root)[0]
        self.assertGreater(proposal["estimated_cost_usd"], 0)
        self.assertGreater(proposal["average_fiber_grams"], 0)
        self.assertGreaterEqual(proposal["average_kid_friendly_score"], 4)
        self.assertGreaterEqual(proposal["rotation_score"], 0)
        self.assertTrue(proposal["warnings"])
        self.assertTrue(proposal["ready_to_commit"])
        self.assertTrue(
            all(meal["kid_friendly_reason"] for meal in proposal["meals"])
        )
        self.assertTrue(
            all(
                meal["selection_explanation"]["reasons"]
                for meal in proposal["meals"]
            )
        )
        self.assertTrue(
            all(
                any(
                    reason.startswith("Inventory coverage:")
                    for reason in meal["selection_explanation"]["reasons"]
                )
                for meal in proposal["meals"]
            )
        )

    def test_selection_explanation_reports_expiring_refrigerated_stock(self) -> None:
        recipe = load_recipes(self.root)["FDP-0041"]
        explanation = selection_explanation(
            recipe,
            day="Friday",
            day_index=4,
            week_of=self.week,
            requirements=recipe["inventory_requirements"],
            recent_ids=set(),
            fixed_assignments={},
            weather_rules=load_weather_rules(self.root),
            weather_category="normal",
            root=self.root,
        )
        self.assertIn("Eggs", explanation["expiring_refrigerated_items"])
        self.assertIn("Recent rotation: no recent repeat", explanation["reasons"])
        self.assertIn("Kid score: 5/5", explanation["reasons"])

    def test_tuesday_method_violation_is_blocking(self) -> None:
        recipes = load_recipes(self.root)
        assignments = ["FDP-0001"] * 7
        proposal = evaluate_proposal(
            self.week,
            assignments,
            recipes,
            root=self.root,
        )
        self.assertTrue(any("Tuesday recipe" in error for error in proposal["errors"]))
        self.assertFalse(proposal["ready_to_commit"])

    def test_parents_only_recipe_gets_a_kids_quick_meal(self) -> None:
        proteins = ["other", "chicken", "chicken", "turkey", "turkey", "beef", "seafood"]
        recipes = {}
        for index, protein in enumerate(proteins):
            recipe_id = f"FDP-99{index:02d}"
            recipes[recipe_id] = {
                "id": recipe_id,
                "name": f"Test Dinner {index}",
                "revision": 1,
                "status": "candidate",
                "protein": protein,
                "meal_scope": "complete-meal",
                "fiber_grams": 8,
                "estimated_cost_usd": 20,
                "kid_friendly_score": 1 if index == 0 else 5,
                "kid_friendly_reason": (
                    PARENTS_ONLY_REASON if index == 0 else "Both children like/love it"
                ),
                "cooking_method": "slow-cooker",
                "cook_time_minutes": 240,
                "seasons": ["summer"],
                "tags": ["summer", protein, "slow-cooker", "mexican-monday"],
                "inventory_requirements": [],
            }
        proposal = evaluate_proposal(
            self.week,
            list(recipes),
            recipes,
            root=self.root,
        )
        self.assertTrue(proposal["ready_to_commit"])
        self.assertIsNotNone(proposal["meals"][0]["kids_quick_meal"])
        self.assertTrue(
            all(meal["kids_quick_meal"] is None for meal in proposal["meals"][1:])
        )
        self.assertEqual(proposal["average_kid_friendly_score"], 5)

    def test_more_than_three_of_one_protein_is_blocking(self) -> None:
        recipes = load_recipes(self.root)
        chicken_ids = [
            recipe["id"]
            for recipe in recipes.values()
            if recipe["protein"] == "chicken"
        ][:4]
        assignments = chicken_ids + ["FDP-0003", "FDP-0007", "FDP-0011"]
        proposal = evaluate_proposal(
            self.week,
            assignments,
            recipes,
            root=self.root,
        )
        self.assertTrue(
            any("Protein chicken appears 4 times" in error for error in proposal["errors"])
        )

    def test_apply_requires_warning_acceptance_then_creates_draft(self) -> None:
        self.keep_only_original_four_recipes()
        proposal = generate_proposals(self.week, 1, root=self.root)[0]
        with self.assertRaisesRegex(ValueError, "explicit acceptance"):
            commit_assignments(
                self.week,
                proposal["assignments"],
                actor="Kevin",
                root=self.root,
            )

        output = commit_assignments(
            self.week,
            proposal["assignments"],
            actor="Kevin",
            accept_warnings=True,
            root=self.root,
            now=dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc),
        )
        self.assertTrue(output.exists())
        self.assertEqual(validate_menu(output), [])
        self.assertIn('status = "draft"', output.read_text(encoding="utf-8"))

    def test_reopened_draft_can_be_replaced(self) -> None:
        output = self.root / "menus" / "2026" / "2026-06-29.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            """+++
week_of = "2026-06-29"
status = "draft"
status_updated_at = "2026-06-27T12:00:00Z"
rebuild_pending = true
+++

# Superseded Menu

## Planning Status History

| Status | Timestamp | Actor | Note |
| --- | --- | --- | --- |
| draft | 2026-06-27T12:00:00Z | Kevin | Rebuild pending |
""",
            encoding="utf-8",
        )
        proposal = generate_proposals(self.week, 1, root=self.root)[0]
        replaced = apply_proposal(
            proposal,
            actor="Kevin",
            accept_warnings=True,
            root=self.root,
        )
        text = replaced.read_text(encoding="utf-8")
        self.assertNotIn("rebuild_pending", text)
        self.assertIn("Selected replacement from dry-run comparison", text)


if __name__ == "__main__":
    unittest.main()
