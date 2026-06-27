from __future__ import annotations

import unittest
import datetime as dt

from scripts.build_week_artifacts import custom_override_recipe, shopping_quantity


class BuildWeekArtifactTests(unittest.TestCase):
    def test_discrete_grocery_items_round_up(self) -> None:
        self.assertEqual(shopping_quantity(0.75, "count"), 1)
        self.assertEqual(shopping_quantity(0.1875, "bunch"), 1)

    def test_measured_grocery_items_round_to_practical_increments(self) -> None:
        self.assertEqual(shopping_quantity(0.62, "cup"), 0.75)
        self.assertEqual(shopping_quantity(1.1, "ounce"), 2)

    def test_custom_carryout_override_becomes_a_weekly_meal(self) -> None:
        metadata, body = custom_override_recipe(
            {
                "type": "custom",
                "title": "Chinese Carryout",
                "note": "Extreme-heat carryout night",
            },
            dt.date(2026, 6, 29),
            "Thursday",
            3,
        )
        self.assertEqual(metadata["status"], "override")
        self.assertEqual(metadata["estimated_cost_usd"], 45)
        self.assertIn("Extreme-heat carryout night", body)


if __name__ == "__main__":
    unittest.main()
