from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from planner.telemetry import (
    format_recommendation_drift,
    format_recipe_utilization,
    format_telemetry_summary,
    load_telemetry,
    recommendation_drift_summary,
    recipe_utilization_rows,
    record_generation,
    telemetry_summary,
    validate_telemetry,
)


class PlannerTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.week = dt.date(2026, 7, 6)
        self.now = dt.datetime(
            2026,
            7,
            1,
            12,
            0,
            tzinfo=dt.timezone.utc,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def proposal(self) -> dict:
        return {
            "errors": [],
            "season": "summer",
            "estimated_cost_usd": 90,
            "average_fiber_grams": 10,
            "inventory_coverage_score": 80,
            "meals": [
                {
                    "status": "approved",
                    "protein": "chicken",
                    "cooking_method": "blackstone",
                    "cook_time_minutes": 30,
                },
                {
                    "status": "approved",
                    "protein": "turkey",
                    "cooking_method": "grill",
                    "cook_time_minutes": 60,
                },
                {
                    "status": "override",
                    "protein": "vegetarian",
                    "cooking_method": "no-cook",
                    "cook_time_minutes": 0,
                },
            ],
            "planning_trace": {
                "rejected_proposal_attempts": 1,
                "rules_used": ["RULE-HEAT-MINIMUM"],
                "days": [
                    {
                        "day": "Monday",
                        "stages": [
                            {
                                "name": "Mexican Monday filter",
                                "rule_id": "RULE-MEXICAN-MONDAY",
                                "removed": 3,
                            },
                            {
                                "name": "normal weather filter",
                                "rule_id": "RULE-WEATHER",
                                "removed": 1,
                            },
                        ],
                        "candidates": [
                            {
                                "recipe_id": "FDP-0001",
                                "name": "Chicken Fajitas",
                                "rank": 1,
                                "ranking_score": 100,
                                "outcome": "selected",
                                "constraint_reason": None,
                            },
                            {
                                "recipe_id": "FDP-0002",
                                "name": "Turkey Burgers",
                                "rank": 2,
                                "ranking_score": 40,
                                "outcome": "eligible_not_selected",
                                "constraint_reason": None,
                            },
                            {"constraint_reason": "protein_cap"},
                            {"constraint_reason": "option_overlap"},
                            {"constraint_reason": "user_idea_cap"},
                            {"constraint_reason": "duplicate_recipe"},
                        ],
                    }
                ],
            },
        }

    def failure_diagnostics(self) -> dict:
        return {
            "attempts": [
                {
                    "messages": [],
                    "eliminations": [
                        {"reason": "protein_cap", "count": 4},
                    ],
                    "days": [
                        {
                            "day": "Monday",
                            "eligible_count": 0,
                            "weather_excluded_count": 2,
                        }
                    ],
                }
            ]
        }

    def test_records_success_failure_and_aggregate_summary(self) -> None:
        record_generation(
            week_of=self.week,
            requested_proposals=1,
            generation_time_ms=100,
            proposals=[self.proposal()],
            root=self.root,
            now=self.now,
        )
        record_generation(
            week_of=self.week,
            requested_proposals=3,
            generation_time_ms=200,
            failure_diagnostics=self.failure_diagnostics(),
            root=self.root,
            now=self.now + dt.timedelta(minutes=1),
        )

        document = load_telemetry(self.root)
        summary = telemetry_summary(document)
        self.assertEqual(summary["menus_generated"], 1)
        self.assertEqual(summary["generation_runs"], 2)
        self.assertEqual(summary["failed_generation_runs"], 1)
        self.assertEqual(summary["average_generation_time_ms"], 150.0)
        self.assertEqual(summary["average_proposals_rejected"], 1.0)
        self.assertEqual(
            summary["constraint_failures"],
            {
                "protein_cap": 5,
                "weather": 3,
                "mexican_monday": 4,
                "inventory_conflicts": 1,
                "option_overlap": 1,
                "queued_idea_cap": 1,
                "duplicate_recipe": 1,
                "heat_friendly": 0,
            },
        )
        self.assertEqual(len(document["recent_runs"]), 2)
        self.assertEqual(
            document["aggregate"]["rule_usage_by_month"]["2026-07"],
            {
                "RULE-HEAT-MINIMUM": 1,
                "RULE-MEXICAN-MONDAY": 2,
                "RULE-PROTEIN-CAP": 4,
                "RULE-WEATHER": 2,
            },
        )
        self.assertEqual(validate_telemetry(self.root), [])

    def test_recipe_utilization_reports_selection_rate_and_score(self) -> None:
        record_generation(
            week_of=self.week,
            requested_proposals=1,
            generation_time_ms=118,
            proposals=[self.proposal()],
            root=self.root,
            now=self.now,
        )

        rows = recipe_utilization_rows(load_telemetry(self.root))
        by_id = {row["recipe_id"]: row for row in rows}
        self.assertEqual(
            by_id["FDP-0001"],
            {
                "recipe_id": "FDP-0001",
                "name": "Chicken Fajitas",
                "times_eligible": 1,
                "times_selected": 1,
                "selection_rate": 100.0,
                "average_score": 100.0,
            },
        )
        self.assertEqual(by_id["FDP-0002"]["selection_rate"], 0.0)
        self.assertEqual(by_id["FDP-0002"]["average_score"], 40.0)
        rendered = format_recipe_utilization(rows)
        self.assertIn("Recipe Utilization", rendered)
        self.assertIn("Chicken Fajitas", rendered)
        self.assertIn("Turkey Burgers", rendered)
        self.assertLess(
            rendered.index("Turkey Burgers"),
            rendered.index("Chicken Fajitas"),
        )

    def test_recommendation_drift_tracks_mix_and_recent_trend(self) -> None:
        record_generation(
            week_of=self.week,
            requested_proposals=1,
            generation_time_ms=118,
            proposals=[self.proposal()],
            root=self.root,
            now=self.now,
        )

        summary = recommendation_drift_summary(load_telemetry(self.root))
        self.assertEqual(summary["meal_observations"], 2)
        self.assertEqual(
            summary["protein_distribution"],
            {
                "chicken": {"count": 1, "percentage": 50.0},
                "turkey": {"count": 1, "percentage": 50.0},
            },
        )
        self.assertEqual(
            summary["cooking_method_distribution"]["blackstone"],
            {"count": 1, "percentage": 50.0},
        )
        self.assertEqual(
            summary["season_distribution"]["summer"],
            {"count": 2, "percentage": 100.0},
        )
        self.assertEqual(
            summary["blackstone_usage"],
            {"count": 1, "percentage": 50.0},
        )
        self.assertEqual(summary["average_prep_minutes"], 45.0)
        self.assertEqual(summary["average_cost_usd"], 45.0)
        self.assertEqual(summary["average_fiber_grams"], 10.0)
        self.assertEqual(len(summary["recent_runs"]), 1)

        rendered = format_recommendation_drift(summary)
        self.assertIn("Recommendation Drift", rendered)
        self.assertIn("Chicken: 1 (50.0%)", rendered.title())
        self.assertIn("Blackstone usage: 1 (50.0%)", rendered)
        self.assertIn("Average prep: 45.0 minutes", rendered)
        self.assertIn("Recent generation trend", rendered)

    def test_formats_operator_summary(self) -> None:
        summary = telemetry_summary(
            record_generation(
                week_of=self.week,
                requested_proposals=1,
                generation_time_ms=118,
                proposals=[self.proposal()],
                root=self.root,
                now=self.now,
            )
        )

        rendered = format_telemetry_summary(summary)
        self.assertIn("Planner Telemetry", rendered)
        self.assertIn("Menus generated: 1", rendered)
        self.assertIn("Average generation time: 118.0 ms", rendered)
        self.assertIn("Protein cap: 1", rendered)
        self.assertIn("Inventory conflicts: 1", rendered)


if __name__ == "__main__":
    unittest.main()
