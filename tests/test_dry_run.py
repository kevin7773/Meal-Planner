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
)
from scripts.menu_status import validate_menu
from scripts.quick_meals import PARENTS_ONLY_REASON


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
        shutil.copytree(ROOT / "quick-meals", self.root / "quick-meals")
        (self.root / "preferences").mkdir()
        shutil.copy2(
            ROOT / "preferences" / "meal-history.md",
            self.root / "preferences" / "meal-history.md",
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
        self.assertTrue(
            all(
                all(recipe_id.startswith("IDEA-") for recipe_id in proposal["assignments"])
                for proposal in proposals
            )
        )

    def test_proposal_reports_cost_fiber_rotation_and_warnings(self) -> None:
        proposal = generate_proposals(self.week, 1, root=self.root)[0]
        self.assertGreater(proposal["estimated_cost_usd"], 0)
        self.assertGreaterEqual(proposal["average_fiber_grams"], 8)
        self.assertGreaterEqual(proposal["average_kid_friendly_score"], 4)
        self.assertGreaterEqual(proposal["rotation_score"], 0)
        self.assertTrue(proposal["warnings"])
        self.assertTrue(proposal["ready_to_commit"])
        self.assertTrue(
            all(meal["kid_friendly_reason"] for meal in proposal["meals"])
        )

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
        parent_recipe = {
            "id": "FDP-9998",
            "name": "Parents' Dinner",
            "revision": 1,
            "status": "candidate",
            "protein": "other",
            "meal_scope": "complete-meal",
            "fiber_grams": 8,
            "estimated_cost_usd": 25,
            "kid_friendly_score": 1,
            "kid_friendly_reason": PARENTS_ONLY_REASON,
            "cooking_method": "slow-cooker",
            "cook_time_minutes": 240,
            "seasons": ["summer"],
            "tags": ["summer", "other", "slow-cooker", "mexican-monday"],
            "inventory_requirements": [],
        }
        proposal = evaluate_proposal(
            self.week,
            [parent_recipe["id"]] * 7,
            {parent_recipe["id"]: parent_recipe},
            root=self.root,
        )
        self.assertTrue(proposal["ready_to_commit"])
        self.assertTrue(
            all(meal["kids_quick_meal"] for meal in proposal["meals"])
        )
        self.assertEqual(proposal["average_kid_friendly_score"], 5)

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
