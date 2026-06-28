from __future__ import annotations

import datetime as dt
import unittest

from planner.monte_carlo import format_simulation_report, run_simulation


class MonteCarloTests(unittest.TestCase):
    def run_sample(self) -> dict:
        return run_simulation(
            iterations=12,
            seed=17,
            start_week=dt.date(2026, 6, 29),
            horizon_weeks=2,
            ranking_variants=3,
        )

    def test_simulation_aggregates_expected_observation_counts(self) -> None:
        report = self.run_sample()
        results = report["results"]
        meals = results["successful_weeks"] * 7

        self.assertEqual(
            results["successful_weeks"] + results["failed_weeks"],
            12,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in results["protein_distribution"].values()
            ),
            meals,
        )
        self.assertEqual(
            sum(
                item["count"]
                for item in results[
                    "cooking_method_distribution"
                ].values()
            ),
            meals,
        )
        self.assertEqual(
            sum(
                row["times_selected"]
                for row in results["recipe_utilization"]
            ),
            meals,
        )
        self.assertGreater(results["average_grocery_bill_usd"], 0)
        self.assertGreater(results["average_fiber_grams"], 0)
        self.assertGreater(
            results["average_inventory_coverage_score"],
            0,
        )
        self.assertEqual(
            results["final_constraint_violations"]["total"],
            0,
        )
        self.assertGreater(results["recipe_diversity"]["percentage"], 0)

    def test_same_seed_produces_same_statistical_results(self) -> None:
        first = self.run_sample()["results"]
        second = self.run_sample()["results"]
        for result in (first, second):
            result.pop("elapsed_seconds")
            result.pop("weeks_per_second")

        self.assertEqual(first, second)

    def test_report_explains_cost_and_constraint_basis(self) -> None:
        report = self.run_sample()
        rendered = format_simulation_report(report)

        self.assertIn("Planner Monte Carlo Test", rendered)
        self.assertIn("Average estimated grocery bill:", rendered)
        self.assertIn("Average inventory coverage:", rendered)
        self.assertIn("Recipe diversity:", rendered)
        self.assertIn("Final constraint violations: 0", rendered)
        self.assertIn("Protein distribution", rendered)
        self.assertIn("Constraint failures", rendered)
        self.assertIn("Lowest recipe selection rates", rendered)
        self.assertIn("Cost basis:", rendered)
        self.assertIn("Fiber basis:", rendered)
        self.assertIn("Constraint basis:", rendered)

    def test_rejects_invalid_simulation_dimensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "iterations"):
            run_simulation(iterations=0)
        with self.assertRaisesRegex(ValueError, "horizon_weeks"):
            run_simulation(iterations=1, horizon_weeks=0)
        with self.assertRaisesRegex(ValueError, "ranking_variants"):
            run_simulation(iterations=1, ranking_variants=0)
        with self.assertRaisesRegex(ValueError, "search_evaluation_limit"):
            run_simulation(iterations=1, search_evaluation_limit=0)
        with self.assertRaisesRegex(ValueError, "Monday"):
            run_simulation(
                iterations=1,
                start_week=dt.date(2026, 6, 30),
            )


if __name__ == "__main__":
    unittest.main()
