from __future__ import annotations

import collections
import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.assignment import constrained_assignments
from planner.proposal import ProposalGenerationError, generate_proposals


ROOT = Path(__file__).resolve().parents[1]


def recipe(
    recipe_id: str,
    *,
    protein: str = "chicken",
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": recipe_id,
        "name": f"Diagnostic Recipe {recipe_id}",
        "status": "approved",
        "protein": protein,
        "cooking_method": "no-cook",
        "seasons": ["summer"],
        "tags": tags or ["mexican-monday"],
        "inventory_requirements": [],
    }


class AssignmentDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "preferences").mkdir()
        shutil.copy2(
            ROOT / "preferences" / "weather-rules.json",
            self.root / "preferences" / "weather-rules.json",
        )
        (self.root / "preferences" / "meal-history.md").write_text(
            "# Meal History\n",
            encoding="utf-8",
        )
        self.week = dt.date(2026, 7, 6)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_assignment(self, recipes: dict[str, dict]) -> dict:
        diagnostics: dict = {}
        assignments = constrained_assignments(
            self.week,
            recipes,
            {},
            [],
            collections.Counter(),
            0,
            root=self.root,
            diagnostics=diagnostics,
        )
        self.assertIsNone(assignments)
        return diagnostics

    def test_reports_day_emptied_by_weather_exclusions(self) -> None:
        path = self.root / "preferences" / "weather-rules.json"
        rules = json.loads(path.read_text(encoding="utf-8"))
        rules["categories"]["normal"]["exclude_tags"] = ["soup"]
        path.write_text(json.dumps(rules), encoding="utf-8")
        recipes = {
            "FDP-9001": recipe("FDP-9001", tags=["mexican-monday", "soup"])
        }

        diagnostics = self.run_assignment(recipes)

        self.assertIn(
            "Thursday failed: 0 eligible recipes after weather exclusions "
            "(1 excluded).",
            diagnostics["messages"],
        )
        thursday = next(
            day for day in diagnostics["days"] if day["day"] == "Thursday"
        )
        self.assertEqual(thursday["weather_excluded_count"], 1)
        self.assertEqual(thursday["eligible_count"], 0)

    def test_reports_unique_recipes_eliminated_by_protein_cap(self) -> None:
        recipes = {
            f"FDP-90{index:02d}": recipe(f"FDP-90{index:02d}")
            for index in range(1, 8)
        }

        diagnostics = self.run_assignment(recipes)

        protein_detail = next(
            item
            for item in diagnostics["eliminations"]
            if item["reason"] == "protein_cap"
        )
        self.assertGreaterEqual(protein_detail["by_protein"]["chicken"], 4)
        self.assertTrue(
            any(
                message.startswith("Protein cap eliminated")
                for message in diagnostics["messages"]
            )
        )

    def test_recent_candidates_are_context_not_false_eliminations(self) -> None:
        recipes = {
            "FDP-9101": recipe("FDP-9101"),
            "FDP-9102": recipe("FDP-9102"),
        }
        (self.root / "preferences" / "meal-history.md").write_text(
            "# Meal History\n\n"
            "## Week of 2026-06-29\n"
            "- FDP-9101\n"
            "- FDP-9102\n",
            encoding="utf-8",
        )

        diagnostics = self.run_assignment(recipes)

        self.assertIn(
            "Monday context: 2 eligible Mexican recipes, both recently used; "
            "rotation is a scoring preference, not a hard exclusion.",
            diagnostics["messages"],
        )

    def test_generation_error_carries_structured_diagnostics(self) -> None:
        (self.root / "recipes").mkdir()
        path = self.root / "preferences" / "weather-rules.json"
        rules = json.loads(path.read_text(encoding="utf-8"))
        rules["categories"]["normal"]["exclude_tags"] = [
            "chicken",
            "turkey",
            "seafood",
        ]
        path.write_text(json.dumps(rules), encoding="utf-8")

        with self.assertRaises(ProposalGenerationError) as raised:
            generate_proposals(self.week, 1, root=self.root)

        error = raised.exception
        self.assertEqual(error.diagnostics["option_number"], 1)
        self.assertEqual(len(error.diagnostics["attempts"]), 1)
        self.assertIn("Failure diagnostics:", str(error))
        self.assertIn("Monday failed:", str(error))


if __name__ == "__main__":
    unittest.main()
