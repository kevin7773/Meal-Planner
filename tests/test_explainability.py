from __future__ import annotations

import unittest

from planner.explainability import explain_planning_trace


class ExplainabilityTests(unittest.TestCase):
    def trace(self) -> dict:
        return {
            "days": [
                {
                    "day": "Monday",
                    "selected_recipe_id": "SELECTED",
                    "candidates": [
                        {
                            "recipe_id": "SELECTED",
                            "name": "Selected Fajitas",
                            "outcome": "selected",
                            "rank": 1,
                            "inventory_score": 90,
                            "recent_repeat": False,
                        },
                        {
                            "recipe_id": "RECENT",
                            "name": "Chicken Alfredo",
                            "outcome": "eligible_not_selected",
                            "rank": 2,
                            "inventory_score": 95,
                            "recent_repeat": True,
                        },
                        {
                            "recipe_id": "SOUP",
                            "name": "Turkey Chili",
                            "outcome": "filtered",
                            "stopped_at": "Summer season filter",
                            "stopped_rule_id": "RULE-SEASON",
                        },
                        {
                            "recipe_id": "PROTEIN",
                            "name": "Chicken Fajitas",
                            "outcome": "constraint_rejected",
                            "constraint_reason": "protein_cap",
                            "rank": 3,
                            "inventory_score": 80,
                            "recent_repeat": False,
                        },
                        {
                            "recipe_id": "DEAD-END",
                            "name": "Turkey Burgers",
                            "outcome": "backtracked",
                            "rank": 4,
                            "inventory_score": 70,
                            "recent_repeat": False,
                        },
                    ],
                }
            ]
        }

    def test_recent_rotation_rejection_reason(self) -> None:
        trace = self.trace()
        explain_planning_trace(trace)
        candidates = {
            candidate["recipe_id"]: candidate
            for candidate in trace["days"][0]["candidates"]
        }

        self.assertEqual(candidates["RECENT"]["decision"], "Rejected")
        self.assertEqual(
            candidates["RECENT"]["reason_code"],
            "recent_rotation",
        )
        self.assertIn("Recent rotation", candidates["RECENT"]["reason"])

    def test_static_constraint_and_backtracking_reasons(self) -> None:
        trace = self.trace()
        result = explain_planning_trace(trace)
        candidates = {
            candidate["recipe_id"]: candidate
            for candidate in trace["days"][0]["candidates"]
        }

        self.assertEqual(candidates["SOUP"]["reason_code"], "season")
        self.assertEqual(candidates["PROTEIN"]["reason_code"], "protein_cap")
        self.assertEqual(
            candidates["DEAD-END"]["reason_code"],
            "backtracked_dead_end",
        )
        self.assertEqual(candidates["SELECTED"]["decision"], "Selected")
        self.assertEqual(
            result,
            {
                "score": 100.0,
                "decisions": 5,
                "explained": 5,
                "unexplained": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
