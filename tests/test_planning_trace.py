from __future__ import annotations

import datetime as dt
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.proposal import generate_proposals
from planner.reporting import proposal_report


ROOT = Path(__file__).resolve().parents[1]


class PlanningTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in (
            "ideas",
            "inventory",
            "planner-data",
            "preferences",
            "quick-meals",
            "recipes",
            "sides",
        ):
            shutil.copytree(ROOT / directory, self.root / directory)
        self.week = dt.date(2026, 7, 6)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def generate(self) -> dict:
        return generate_proposals(self.week, 1, root=self.root)[0]

    def test_every_proposal_contains_versioned_seven_day_trace(self) -> None:
        proposals = generate_proposals(self.week, 3, root=self.root)

        for proposal in proposals:
            trace = proposal["planning_trace"]
            self.assertEqual(trace["trace_version"], 2)
            self.assertEqual(len(trace["days"]), 7)
            self.assertGreater(trace["static_candidates_considered"], 0)
            self.assertNotIn("candidate_evaluations", trace)
            self.assertGreater(trace["search_candidate_attempts"], 0)
            self.assertEqual(trace["explainability"]["score"], 100.0)
            self.assertEqual(trace["explainability"]["unexplained"], 0)
            self.assertEqual(proposal["explainability_score"], 100.0)
            self.assertEqual(
                [day["selected_recipe_id"] for day in trace["days"]],
                proposal["assignments"],
            )

    def test_monday_trace_shows_filters_ranking_and_selection(self) -> None:
        trace = self.generate()["planning_trace"]
        monday = trace["days"][0]
        stage_names = [stage["name"] for stage in monday["stages"]]

        self.assertIn("Mexican Monday filter", stage_names)
        self.assertIn("Summer season filter", stage_names)
        self.assertIn("normal weather filter", stage_names)
        self.assertIn("Inventory score ranking", stage_names)
        self.assertIn("Recent rotation ranking", stage_names)
        self.assertIn("Protein cap", stage_names)
        for stage in monday["stages"]:
            self.assertLessEqual(stage["after"], stage["before"])

        selected = [
            candidate
            for candidate in monday["candidates"]
            if candidate["outcome"] == "selected"
        ]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["recipe_id"], monday["selected_recipe_id"])
        self.assertIsInstance(selected[0]["inventory_score"], int)
        self.assertGreater(selected[0]["ranking_score"], 0)
        self.assertLessEqual(selected[0]["ranking_score"], 100)
        self.assertEqual(selected[0]["decision"], "Selected")
        self.assertTrue(selected[0]["reason"])

    def test_trace_explains_candidates_filtered_before_ranking(self) -> None:
        monday = self.generate()["planning_trace"]["days"][0]
        filtered = [
            candidate
            for candidate in monday["candidates"]
            if candidate["outcome"] == "filtered"
        ]

        self.assertTrue(filtered)
        self.assertTrue(all(candidate["stopped_at"] for candidate in filtered))
        self.assertTrue(all(candidate["reason"] for candidate in filtered))
        self.assertTrue(
            any(
                candidate["stopped_at"] == "Mexican Monday filter"
                for candidate in filtered
            )
        )

    def test_report_renders_planning_trace(self) -> None:
        report = proposal_report(self.generate(), 1)

        self.assertIn("PLANNING TRACE", report)
        self.assertIn("Static candidates considered:", report)
        self.assertIn("Search candidate attempts:", report)
        self.assertIn("Explainability score: 100.0/100", report)
        self.assertIn("Mexican Monday filter:", report)
        self.assertIn("Candidate decisions:", report)
        self.assertIn("Rejected -", report)


if __name__ == "__main__":
    unittest.main()
