from __future__ import annotations

import argparse
import unittest

from planner.metrics import (
    scale_recipe_for_diners,
    scale_sides_for_diners,
    validate_planned_diners,
)
from scripts.planner_cli import parse_diners


class DinerMetricTests(unittest.TestCase):
    def test_recipe_cost_and_requirements_scale_from_servings(self) -> None:
        recipe = {
            "servings": 4,
            "estimated_cost_usd": 20,
            "inventory_requirements": [
                {"item_id": "chicken-breast", "quantity": 2}
            ],
        }

        scaled = scale_recipe_for_diners(recipe, 6)

        self.assertEqual(scaled["estimated_cost_usd"], 30)
        self.assertEqual(
            scaled["inventory_requirements"][0]["quantity"],
            3,
        )

    def test_side_cost_and_requirements_scale_from_four_diners(self) -> None:
        sides = [
            {
                "estimated_cost_usd": 4,
                "requirements": [
                    {"item_id": "fresh-corn", "quantity": 4}
                ],
            }
        ]

        scaled = scale_sides_for_diners(sides, 2)

        self.assertEqual(scaled[0]["estimated_cost_usd"], 2)
        self.assertEqual(scaled[0]["requirements"][0]["quantity"], 2)

    def test_diner_schedule_requires_seven_values_in_range(self) -> None:
        self.assertEqual(validate_planned_diners(None), [4] * 7)
        with self.assertRaisesRegex(ValueError, "seven integers"):
            validate_planned_diners([4] * 6)
        with self.assertRaisesRegex(ValueError, "seven integers"):
            validate_planned_diners([4, 4, 4, 4, 4, 4, 21])

        self.assertEqual(parse_diners("6,4,3,2,5,8,4"), [6, 4, 3, 2, 5, 8, 4])
        with self.assertRaisesRegex(
            argparse.ArgumentTypeError,
            "seven values",
        ):
            parse_diners("4,4,4")


if __name__ == "__main__":
    unittest.main()
