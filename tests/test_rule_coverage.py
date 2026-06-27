from __future__ import annotations

import collections
import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.assignment import constrained_assignments
from planner.rules import (
    format_rule_coverage,
    load_rules,
    rule_coverage_summary,
    validate_rules,
)
from planner.tracing import dynamic_decision_trace, static_day_trace


ROOT = Path(__file__).resolve().parents[1]


def trace_recipe(
    recipe_id: str,
    *,
    protein: str = "chicken",
    method: str = "no-cook",
    tags: list[str] | None = None,
    seasons: list[str] | None = None,
    status: str = "approved",
    source: str | None = None,
    day: str | None = None,
) -> dict:
    return {
        "id": recipe_id,
        "name": f"Rule Recipe {recipe_id}",
        "status": status,
        "protein": protein,
        "cooking_method": method,
        "seasons": seasons or ["summer"],
        "tags": tags or ["mexican-monday"],
        "source": source,
        "day": day,
        "inventory_requirements": [],
    }


class RuleCoverageTests(unittest.TestCase):
    def test_static_rule_ids_and_filters(self) -> None:
        recipes = {
            "ACTIVE": trace_recipe("ACTIVE"),
            "RETIRED": trace_recipe("RETIRED", status="retired"),
            "WRONG-DAY": trace_recipe(
                "WRONG-DAY",
                source="generated-idea",
                day="Friday",
            ),
            "NOT-MEXICAN": trace_recipe(
                "NOT-MEXICAN",
                tags=["family-dinner"],
            ),
            "WINTER": trace_recipe("WINTER", seasons=["winter"]),
            "SOUP": trace_recipe(
                "SOUP",
                tags=["mexican-monday", "soup"],
            ),
        }
        _, monday = static_day_trace(
            recipes,
            day="Monday",
            season="summer",
            excluded_tags={"soup"},
            weather_category="hot",
        )
        self.assertEqual(
            {
                stage["rule_id"]
                for stage in monday["stages"]
                if stage["rule_id"]
            },
            {
                "RULE-ACTIVE-STATUS",
                "RULE-GENERATED-DAY",
                "RULE-MEXICAN-MONDAY",
                "RULE-SEASON",
                "RULE-WEATHER",
            },
        )
        _, tuesday = static_day_trace(
            recipes,
            day="Tuesday",
            season="summer",
            excluded_tags=set(),
            weather_category="normal",
        )
        _, thursday = static_day_trace(
            recipes,
            day="Thursday",
            season="summer",
            excluded_tags=set(),
            weather_category="normal",
        )
        self.assertIn(
            "RULE-TUESDAY-LOW-EFFORT",
            {stage["rule_id"] for stage in tuesday["stages"]},
        )
        self.assertIn(
            "RULE-THURSDAY-LOW-EFFORT",
            {stage["rule_id"] for stage in thursday["stages"]},
        )

    def test_dynamic_rule_ids(self) -> None:
        candidates = [
            trace_recipe("DUPLICATE", protein="turkey"),
            trace_recipe("PROTEIN", protein="chicken"),
            trace_recipe("IDEA", protein="turkey", source="user-idea"),
            trace_recipe("OVERLAP", protein="beef"),
            trace_recipe("AVAILABLE", protein="seafood"),
        ]
        decision = dynamic_decision_trace(
            candidates,
            used_ids={"DUPLICATE"},
            protein_counts=collections.Counter({"chicken": 3}),
            idea_count=2,
            previous_options=[{"OVERLAP"}],
            overlap_counts=[2],
            inventory_scores={recipe["id"]: 0 for recipe in candidates},
            recent_ids=set(),
        )
        self.assertEqual(
            {
                stage["rule_id"]
                for stage in decision["stages"]
                if stage["rule_id"]
            },
            {
                "RULE-INVENTORY-RANKING",
                "RULE-RECENT-ROTATION",
                "RULE-UNIQUE-WEEK",
                "RULE-PROTEIN-CAP",
                "RULE-QUEUED-IDEA-CAP",
                "RULE-OPTION-OVERLAP",
            },
        )
        self.assertEqual(
            decision["rejection_reasons"],
            {
                "DUPLICATE": "duplicate_recipe",
                "PROTEIN": "protein_cap",
                "IDEA": "user_idea_cap",
                "OVERLAP": "option_overlap",
            },
        )

    def test_heat_minimum_rule_is_traced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "preferences").mkdir()
            shutil.copy2(
                ROOT / "preferences" / "weather-rules.json",
                root / "preferences" / "weather-rules.json",
            )
            (root / "preferences" / "meal-history.md").write_text(
                "# Meal History\n",
                encoding="utf-8",
            )
            weather_path = root / "weather" / "2026"
            weather_path.mkdir(parents=True)
            (weather_path / "2026-07-06.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "week_of": "2026-07-06",
                        "category": "hot",
                        "forecast_high_f": 95,
                        "source": "Rule coverage fixture",
                    }
                ),
                encoding="utf-8",
            )
            proteins = ("chicken", "turkey", "beef", "seafood")
            recipes = {
                f"HEAT-{index}": trace_recipe(
                    f"HEAT-{index}",
                    protein=proteins[index % len(proteins)],
                )
                for index in range(7)
            }
            trace: dict = {}
            assignments = constrained_assignments(
                dt.date(2026, 7, 6),
                recipes,
                {},
                [],
                collections.Counter(),
                0,
                root=root,
                trace=trace,
            )
            self.assertIsNotNone(assignments)
            self.assertIn("RULE-HEAT-MINIMUM", trace["rules_used"])

    def test_rule_registry_and_coverage_report(self) -> None:
        self.assertEqual(validate_rules(ROOT), [])
        rules = load_rules(ROOT)
        usage = {rule["id"]: 1 for rule in rules[:-3]}
        telemetry = {
            "aggregate": {
                "rule_usage_by_month": {
                    "2026-06": usage,
                }
            }
        }
        summary = rule_coverage_summary(
            telemetry,
            rules,
            month="2026-06",
        )
        self.assertEqual(summary["rules"], 16)
        self.assertEqual(summary["rules_tested"], 16)
        self.assertEqual(summary["rules_used_this_month"], 13)
        self.assertEqual(len(summary["unused_rules"]), 3)
        rendered = format_rule_coverage(summary)
        self.assertIn("Rules: 16", rendered)
        self.assertIn("Unused rules: 3", rendered)


if __name__ == "__main__":
    unittest.main()
