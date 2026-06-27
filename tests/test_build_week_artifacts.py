from __future__ import annotations

import unittest

from scripts.build_week_artifacts import shopping_quantity


class BuildWeekArtifactTests(unittest.TestCase):
    def test_discrete_grocery_items_round_up(self) -> None:
        self.assertEqual(shopping_quantity(0.75, "count"), 1)
        self.assertEqual(shopping_quantity(0.1875, "bunch"), 1)

    def test_measured_grocery_items_round_to_practical_increments(self) -> None:
        self.assertEqual(shopping_quantity(0.62, "cup"), 0.75)
        self.assertEqual(shopping_quantity(1.1, "ounce"), 2)


if __name__ == "__main__":
    unittest.main()
