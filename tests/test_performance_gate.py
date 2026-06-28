from __future__ import annotations

import copy
import unittest

from planner.performance_gate import (
    evaluate_performance,
    update_approved_metrics,
    validate_baseline,
)


class PerformanceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = {
            "schema_version": 1,
            "simulation": {
                "iterations": 10_000,
                "seed": 42,
                "start_week": "2026-06-29",
                "horizon_weeks": 52,
                "ranking_variants": 2,
                "search_evaluation_limit": 2_000,
            },
            "approved_metrics": {
                "average_grocery_bill_usd": 100.0,
                "average_fiber_grams": 9.0,
                "average_inventory_coverage_score": 30.0,
                "recipe_diversity_percentage": 35.0,
                "final_constraint_violations": 0,
            },
            "thresholds": {
                "max_grocery_cost_increase_percent": 10.0,
                "minimum_average_fiber_grams": 8.0,
                "minimum_inventory_coverage_score": 25.0,
                "minimum_recipe_diversity_percentage": 28.0,
                "maximum_final_constraint_violations": 0,
            },
        }
        self.current = {
            "average_grocery_bill_usd": 105.0,
            "average_fiber_grams": 8.5,
            "average_inventory_coverage_score": 27.0,
            "recipe_diversity_percentage": 32.0,
            "final_constraint_violations": 0,
        }

    def failed_metrics(self, current: dict) -> set[str]:
        return {
            check["metric"]
            for check in evaluate_performance(current, self.baseline)
            if not check["passed"]
        }

    def test_healthy_metrics_pass(self) -> None:
        self.assertEqual(self.failed_metrics(self.current), set())

    def test_cost_increase_over_ten_percent_fails(self) -> None:
        current = {**self.current, "average_grocery_bill_usd": 110.01}
        self.assertEqual(
            self.failed_metrics(current),
            {"average_grocery_bill_usd"},
        )

    def test_fiber_below_target_fails(self) -> None:
        current = {**self.current, "average_fiber_grams": 7.9}
        self.assertEqual(
            self.failed_metrics(current),
            {"average_fiber_grams"},
        )

    def test_inventory_coverage_below_floor_fails(self) -> None:
        current = {
            **self.current,
            "average_inventory_coverage_score": 24.9,
        }
        self.assertEqual(
            self.failed_metrics(current),
            {"average_inventory_coverage_score"},
        )

    def test_recipe_diversity_below_floor_fails(self) -> None:
        current = {
            **self.current,
            "recipe_diversity_percentage": 27.9,
        }
        self.assertEqual(
            self.failed_metrics(current),
            {"recipe_diversity_percentage"},
        )

    def test_any_final_constraint_violation_fails(self) -> None:
        current = {**self.current, "final_constraint_violations": 1}
        self.assertEqual(
            self.failed_metrics(current),
            {"final_constraint_violations"},
        )

    def test_baseline_validator_rejects_incomplete_policy(self) -> None:
        invalid = copy.deepcopy(self.baseline)
        del invalid["thresholds"]["minimum_average_fiber_grams"]
        with self.assertRaisesRegex(ValueError, "is missing"):
            validate_baseline(invalid)

    def test_baseline_update_requires_review_note(self) -> None:
        report = {
            "results": {
                "average_grocery_bill_usd": 99.0,
                "average_fiber_grams": 9.1,
                "average_inventory_coverage_score": 31.0,
                "recipe_diversity": {"percentage": 36.0},
                "final_constraint_violations": {"total": 0},
            }
        }
        with self.assertRaisesRegex(ValueError, "reason"):
            update_approved_metrics(
                self.baseline,
                report,
                reason=" ",
            )


if __name__ == "__main__":
    unittest.main()
