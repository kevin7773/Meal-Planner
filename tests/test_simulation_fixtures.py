from __future__ import annotations

import collections
import datetime as dt
import unittest
from pathlib import Path

from planner.assignment import constrained_assignments


WEEK = dt.date(2026, 7, 6)


def recipe(
    recipe_id: str,
    *,
    protein: str,
    tags: list[str],
) -> dict:
    return {
        "id": recipe_id,
        "name": f"Fixture {recipe_id}",
        "status": "approved",
        "protein": protein,
        "cooking_method": "no-cook",
        "seasons": ["summer"],
        "tags": tags,
        "inventory_requirements": [],
    }


def weather(category: str, *, excluded_tags: list[str]) -> tuple[dict, dict]:
    return (
        {"category": category},
        {
            "categories": {
                category: {
                    "exclude_tags": excluded_tags,
                    "minimum_heat_friendly_meals": 0,
                }
            },
            "heat_friendly_methods": ["no-cook"],
        },
    )


def assign(
    recipes: dict[str, dict],
    *,
    category: str = "normal",
    excluded_tags: list[str] | None = None,
    inventory_scores: dict[str, int] | None = None,
) -> tuple[list[str] | None, dict]:
    weather_context, weather_rules = weather(
        category,
        excluded_tags=excluded_tags or [],
    )
    diagnostics: dict = {}
    assignments = constrained_assignments(
        WEEK,
        recipes,
        {},
        [],
        collections.Counter(),
        0,
        root=Path("."),
        diagnostics=diagnostics,
        weather_context_override=weather_context,
        weather_rules_override=weather_rules,
        recent_ids_override=set(),
        inventory_scores_override=inventory_scores
        or {recipe_id: 0 for recipe_id in recipes},
        explain_trace=False,
    )
    return assignments, diagnostics


class SimulationFixtureTests(unittest.TestCase):
    def test_no_mexican_monday_candidates(self) -> None:
        recipes = {
            f"NO-MEX-{index}": recipe(
                f"NO-MEX-{index}",
                protein=("chicken", "turkey", "beef", "seafood")[index % 4],
                tags=["family-dinner"],
            )
            for index in range(7)
        }

        assignments, diagnostics = assign(recipes)

        self.assertIsNone(assignments)
        monday = next(
            day for day in diagnostics["days"] if day["day"] == "Monday"
        )
        self.assertEqual(monday["day_rule_eligible_count"], 0)
        self.assertEqual(monday["eligible_count"], 0)

    def test_hot_weather_excludes_every_candidate(self) -> None:
        recipes = {
            f"HOT-{index}": recipe(
                f"HOT-{index}",
                protein=("chicken", "turkey", "beef", "seafood")[index % 4],
                tags=["mexican-monday", "soup"],
            )
            for index in range(7)
        }

        assignments, diagnostics = assign(
            recipes,
            category="hot",
            excluded_tags=["soup"],
        )

        self.assertIsNone(assignments)
        self.assertTrue(
            all(day["eligible_count"] == 0 for day in diagnostics["days"])
        )
        self.assertTrue(
            all(
                day["weather_excluded_count"] == len(recipes)
                for day in diagnostics["days"]
            )
        )

    def test_protein_cap_creates_assignment_dead_end(self) -> None:
        recipes = {
            f"CHICKEN-{index}": recipe(
                f"CHICKEN-{index}",
                protein="chicken",
                tags=["mexican-monday"],
            )
            for index in range(7)
        }

        assignments, diagnostics = assign(recipes)

        self.assertIsNone(assignments)
        protein_eliminations = next(
            item
            for item in diagnostics["eliminations"]
            if item["reason"] == "protein_cap"
        )
        self.assertGreater(protein_eliminations["count"], 0)
        self.assertGreater(
            protein_eliminations["by_protein"]["chicken"],
            0,
        )

    def test_inventory_first_ranking_changes_monday_winner(self) -> None:
        recipes = {
            "MEX-A": recipe(
                "MEX-A",
                protein="chicken",
                tags=["mexican-monday"],
            ),
            "MEX-B": recipe(
                "MEX-B",
                protein="chicken",
                tags=["mexican-monday"],
            ),
        }
        for index, protein in enumerate(
            ("turkey", "turkey", "beef", "beef", "seafood", "seafood")
        ):
            recipe_id = f"OTHER-{index}"
            recipes[recipe_id] = recipe(
                recipe_id,
                protein=protein,
                tags=["family-dinner"],
            )
        scores = {recipe_id: 0 for recipe_id in recipes}

        first, _ = assign(
            recipes,
            inventory_scores={**scores, "MEX-A": 100, "MEX-B": 0},
        )
        second, _ = assign(
            recipes,
            inventory_scores={**scores, "MEX-A": 0, "MEX-B": 100},
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first[0], "MEX-A")
        self.assertEqual(second[0], "MEX-B")


if __name__ == "__main__":
    unittest.main()
