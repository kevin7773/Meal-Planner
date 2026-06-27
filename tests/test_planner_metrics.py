from __future__ import annotations

import unittest

from planner.metrics import (
    average_fiber_grams,
    average_kid_friendly_score,
    collect_inventory_requirements,
    estimated_menu_cost,
    estimated_shopping_cost,
    recipe_rotation_score,
)
from planner.quick_meal_planning import (
    public_quick_meal,
    quick_meal_requirements,
)
from planner.side_planning import public_side_suggestions, side_requirements


class PlannerMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.meals = [
            {
                "id": "A",
                "estimated_cost_usd": 10,
                "fiber_grams": 8,
                "kid_friendly_score": 5,
                "cooking_method": "grill",
                "protein": "chicken",
                "inventory_requirements": [{"item_id": "chicken", "quantity": 1}],
            },
            {
                "id": "B",
                "estimated_cost_usd": 20,
                "fiber_grams": 10,
                "kid_friendly_score": 1,
                "cooking_method": "oven",
                "protein": "turkey",
                "inventory_requirements": [{"item_id": "rice", "quantity": 2}],
            },
        ]
        self.sides = {
            "A": [
                {
                    "id": "SIDE-1",
                    "name": "Vegetables",
                    "estimated_cost_usd": 3,
                    "fiber_grams": 2,
                    "kid_friendly_reason": "Familiar vegetables",
                    "requirements": [{"item_id": "vegetables", "quantity": 1}],
                }
            ],
            "B": [],
        }
        self.quick_meals = {
            1: {
                "id": "KQM-1",
                "name": "Quick Dinner",
                "estimated_cost_usd": 6,
                "fiber_grams": 3,
                "kid_friendly_score": 5,
                "requirements": [{"item_id": "quick-dinner", "quantity": 1}],
            }
        }

    def test_cost_fiber_and_kid_metrics(self) -> None:
        self.assertEqual(
            estimated_menu_cost(self.meals, self.sides, self.quick_meals),
            39.0,
        )
        self.assertEqual(average_fiber_grams(self.meals, self.sides), 10.0)
        self.assertEqual(
            average_kid_friendly_score(
                list(enumerate(self.meals)),
                self.quick_meals,
            ),
            5.0,
        )
        self.assertEqual(estimated_shopping_cost(39, 12.5), 26.5)
        self.assertEqual(estimated_shopping_cost(10, 15), 0.0)

    def test_inventory_requirements_include_all_enrichments(self) -> None:
        requirements = collect_inventory_requirements(
            self.meals,
            self.sides,
            self.quick_meals,
        )
        self.assertEqual(
            [item["item_id"] for item in requirements],
            ["chicken", "rice", "vegetables", "quick-dinner"],
        )

    def test_rotation_score_is_pure_and_deterministic(self) -> None:
        scored_meals = [
            {
                "cooking_method": f"method-{index}",
                "protein": ("chicken", "turkey", "seafood")[index % 3],
            }
            for index in range(7)
        ]
        self.assertEqual(
            recipe_rotation_score(
                ["A", "A", "B", "C", "D", "E", "F"],
                scored_meals,
                ["B"],
            ),
            78,
        )

    def test_public_enrichment_payloads_hide_internal_requirements(self) -> None:
        side = public_side_suggestions(self.sides["A"])[0]
        quick_meal = public_quick_meal(self.quick_meals[1])
        self.assertNotIn("requirements", side)
        self.assertNotIn("requirements", quick_meal)
        self.assertEqual(
            side_requirements(self.sides["A"])[0]["item_id"],
            "vegetables",
        )
        self.assertEqual(
            quick_meal_requirements(self.quick_meals[1])[0]["item_id"],
            "quick-dinner",
        )


if __name__ == "__main__":
    unittest.main()
