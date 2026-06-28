from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import patch

from planner.simulation import (
    SELECTED_RECIPE_SOURCES,
    format_simulation_report,
    run_simulation,
    selected_recipe_source,
    underutilized_high_scoring_recipes,
)


class SimulationTests(unittest.TestCase):
    def run_sample(self) -> dict:
        return run_simulation(
            iterations=12,
            seed=17,
            start_week=dt.date(2026, 6, 29),
            horizon_weeks=2,
            ranking_variants=3,
        )

    @staticmethod
    def deterministic_metrics(report: dict) -> dict:
        metrics = report["results"].copy()
        metrics.pop("elapsed_seconds")
        metrics.pop("weeks_per_second")
        return metrics

    def test_legacy_module_reexports_simulation_api(self) -> None:
        from planner.monte_carlo import (
            format_simulation_report as legacy_format,
        )
        from planner.monte_carlo import run_simulation as legacy_run

        self.assertIs(legacy_run, run_simulation)
        self.assertIs(legacy_format, format_simulation_report)

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
        sources = results["selected_recipe_source_distribution"]
        self.assertEqual(tuple(sources), SELECTED_RECIPE_SOURCES)
        self.assertEqual(
            sum(item["count"] for item in sources.values()),
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
        self.assertGreater(results["average_recipe_cost_usd"], 0)
        self.assertEqual(
            results["average_recipe_cost_usd"],
            results["average_grocery_bill_usd"],
        )
        self.assertGreater(results["average_fiber_grams"], 0)
        self.assertGreater(
            results["average_inventory_coverage_score"],
            0,
        )
        self.assertGreater(results["recipe_diversity"]["percentage"], 0)

    def test_selected_recipe_source_classification(self) -> None:
        cases = (
            ({"id": "A", "status": "approved"}, "approved"),
            ({"id": "B", "status": "candidate"}, "candidate"),
            (
                {
                    "id": "C",
                    "status": "proposed",
                    "source": "generated-idea",
                },
                "generated-idea",
            ),
            (
                {
                    "id": "D",
                    "status": "proposed",
                    "source": "user-idea",
                },
                "user-idea",
            ),
            (
                {
                    "id": "E",
                    "status": "override",
                    "source": "meal-override",
                },
                "override",
            ),
        )

        for recipe, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(selected_recipe_source(recipe), expected)

    def test_unknown_selected_recipe_source_fails_loudly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cannot classify"):
            selected_recipe_source({"id": "UNKNOWN", "status": "proposed"})

    def test_underutilized_high_scoring_filter(self) -> None:
        rows = [
            {
                "recipe_id": "MATCH",
                "name": "Strong but Blocked",
                "times_eligible": 100,
                "times_selected": 10,
                "selection_rate": 10.0,
                "average_score": 90.0,
            },
            {
                "recipe_id": "LOW-SCORE",
                "name": "Low Score",
                "times_eligible": 100,
                "times_selected": 5,
                "selection_rate": 5.0,
                "average_score": 70.0,
            },
            {
                "recipe_id": "OFTEN-SELECTED",
                "name": "Often Selected",
                "times_eligible": 100,
                "times_selected": 25,
                "selection_rate": 25.0,
                "average_score": 95.0,
            },
            {
                "recipe_id": "TOO-FEW",
                "name": "Too Few Observations",
                "times_eligible": 4,
                "times_selected": 0,
                "selection_rate": 0.0,
                "average_score": 100.0,
            },
        ]

        matches = underutilized_high_scoring_recipes(
            rows,
            minimum_eligible_observations=5,
        )

        self.assertEqual(
            [row["recipe_id"] for row in matches],
            ["MATCH"],
        )

    def test_same_seed_and_baseline_produce_identical_metrics(self) -> None:
        first = self.deterministic_metrics(self.run_sample())
        second = self.deterministic_metrics(self.run_sample())

        self.assertEqual(first, second)

    def test_different_seed_changes_scenario_distribution(self) -> None:
        first = self.run_sample()["results"]["weather_scenarios"]
        second = run_simulation(
            iterations=12,
            seed=18,
            start_week=dt.date(2026, 6, 29),
            horizon_weeks=2,
            ranking_variants=3,
        )["results"]["weather_scenarios"]

        self.assertNotEqual(first, second)

    def test_single_iteration_completes(self) -> None:
        report = run_simulation(
            iterations=1,
            seed=17,
            start_week=dt.date(2026, 6, 29),
            horizon_weeks=1,
            ranking_variants=1,
        )
        results = report["results"]

        self.assertEqual(report["simulation"]["iterations"], 1)
        self.assertEqual(
            results["successful_weeks"] + results["failed_weeks"],
            1,
        )

    def test_search_limit_failure_is_counted(self) -> None:
        results = run_simulation(
            iterations=1,
            seed=17,
            start_week=dt.date(2026, 6, 29),
            horizon_weeks=1,
            ranking_variants=1,
            search_evaluation_limit=1,
        )["results"]

        self.assertEqual(results["successful_weeks"], 0)
        self.assertEqual(results["failed_weeks"], 1)
        self.assertEqual(
            results["constraint_failures"]["search_limit"],
            1,
        )

    def test_normal_repo_data_has_no_final_constraint_violations(self) -> None:
        violations = self.run_sample()["results"][
            "final_constraint_violations"
        ]

        self.assertEqual(violations["total"], 0)
        self.assertEqual(violations["by_rule"], {})

    def test_report_explains_cost_and_constraint_basis(self) -> None:
        report = self.run_sample()
        rendered = format_simulation_report(report)

        self.assertIn("Planner Simulation", rendered)
        self.assertIn("Average estimated recipe cost:", rendered)
        self.assertIn("Average inventory coverage:", rendered)
        self.assertIn("Recipe diversity:", rendered)
        self.assertIn("Final constraint violations: 0", rendered)
        self.assertIn("Selected recipe sources", rendered)
        self.assertIn("generated-idea:", rendered)
        self.assertIn("user-idea:", rendered)
        self.assertIn("override:", rendered)
        self.assertIn("Protein distribution", rendered)
        self.assertIn("Constraint failures", rendered)
        self.assertIn("Underutilized high-scoring recipes", rendered)
        self.assertIn("Lowest recipe selection rates", rendered)
        self.assertIn("Cost basis:", rendered)
        self.assertIn("Fiber basis:", rendered)
        self.assertIn("Constraint basis:", rendered)

    def test_report_accepts_legacy_grocery_cost_field(self) -> None:
        report = self.run_sample()
        legacy_cost = report["results"].pop("average_recipe_cost_usd")
        report["results"].pop("underutilized_high_scoring_recipes")

        rendered = format_simulation_report(report)

        self.assertIn(
            f"Average estimated recipe cost: ${legacy_cost:.2f}",
            rendered,
        )
        self.assertIn("Underutilized high-scoring recipes", rendered)

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

    def test_progress_reports_failed_iterations(self) -> None:
        updates: list[tuple[int, int]] = []

        with patch(
            "planner.simulation.constrained_assignments",
            return_value=None,
        ):
            report = run_simulation(
                iterations=3,
                seed=17,
                start_week=dt.date(2026, 6, 29),
                horizon_weeks=1,
                ranking_variants=1,
                progress=lambda completed, total: updates.append(
                    (completed, total)
                ),
            )

        self.assertEqual(report["results"]["failed_weeks"], 3)
        self.assertEqual(updates, [(1, 3), (2, 3), (3, 3)])


if __name__ == "__main__":
    unittest.main()
