from __future__ import annotations

import contextlib
import datetime as dt
import io
import sys
import unittest
from unittest import mock

from planner.proposal import ProposalGenerationError
from scripts import planner_cli


class PlannerCliTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.week = dt.date(2026, 7, 6)
        self.proposals = [
            {
                "week_of": self.week.isoformat(),
                "planning_trace": {
                    "rejected_proposal_attempts": 0,
                    "days": [],
                },
                "errors": [],
                "inventory_coverage_score": 100,
            }
        ]

    def run_cli(self, arguments: list[str]) -> int:
        with mock.patch.object(sys, "argv", ["planner_cli.py", *arguments]):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()):
                    return planner_cli.main()

    @mock.patch.object(planner_cli, "record_generation")
    @mock.patch.object(planner_cli, "generate_proposals")
    def test_successful_generation_records_telemetry(
        self,
        generate: mock.Mock,
        record: mock.Mock,
    ) -> None:
        generate.return_value = self.proposals

        result = self.run_cli(
            ["generate", "--week", self.week.isoformat(), "--count", "1", "--json"]
        )

        self.assertEqual(result, 0)
        record.assert_called_once()
        call = record.call_args.kwargs
        self.assertEqual(call["week_of"], self.week)
        self.assertEqual(call["requested_proposals"], 1)
        self.assertIs(call["proposals"], self.proposals)
        self.assertGreaterEqual(call["generation_time_ms"], 0)

    @mock.patch.object(planner_cli, "record_generation")
    @mock.patch.object(planner_cli, "generate_proposals")
    def test_failed_generation_records_diagnostics(
        self,
        generate: mock.Mock,
        record: mock.Mock,
    ) -> None:
        error = ProposalGenerationError(
            self.week,
            1,
            [
                {
                    "label": "Test pool",
                    "messages": ["Protein cap eliminated candidates."],
                    "days": [],
                    "eliminations": [],
                }
            ],
        )
        generate.side_effect = error

        result = self.run_cli(
            ["generate", "--week", self.week.isoformat(), "--count", "1", "--json"]
        )

        self.assertEqual(result, 1)
        record.assert_called_once()
        self.assertIs(
            record.call_args.kwargs["failure_diagnostics"],
            error.diagnostics,
        )

    @mock.patch.object(planner_cli, "record_generation")
    @mock.patch.object(planner_cli, "generate_proposals")
    def test_no_telemetry_flag_preserves_strict_read_only_run(
        self,
        generate: mock.Mock,
        record: mock.Mock,
    ) -> None:
        generate.return_value = self.proposals

        result = self.run_cli(
            [
                "generate",
                "--week",
                self.week.isoformat(),
                "--count",
                "1",
                "--json",
                "--no-telemetry",
            ]
        )

        self.assertEqual(result, 0)
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
