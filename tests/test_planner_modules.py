from __future__ import annotations

import unittest

import scripts.dry_run as facade
import scripts.planner_cli as cli
from planner.assignment import constrained_assignments, format_assignment_diagnostics
from planner.commit import apply_proposal, commit_assignments
from planner.eligibility import eligible_recipes, load_recipes
from planner.explanations import selection_explanation as explanation_implementation
from planner.proposal import ProposalGenerationError, generate_proposals
from planner.reporting import proposal_report
from planner.scoring import evaluate_proposal, selection_explanation


class PlannerModuleBoundaryTests(unittest.TestCase):
    def test_dry_run_facade_preserves_public_planner_api(self) -> None:
        exports = {
            "apply_proposal": apply_proposal,
            "commit_assignments": commit_assignments,
            "constrained_assignments": constrained_assignments,
            "eligible_recipes": eligible_recipes,
            "evaluate_proposal": evaluate_proposal,
            "format_assignment_diagnostics": format_assignment_diagnostics,
            "generate_proposals": generate_proposals,
            "load_recipes": load_recipes,
            "proposal_report": proposal_report,
            "ProposalGenerationError": ProposalGenerationError,
            "selection_explanation": selection_explanation,
        }

        for name, implementation in exports.items():
            with self.subTest(name=name):
                self.assertIs(getattr(facade, name), implementation)
                self.assertIs(getattr(cli, name), implementation)

    def test_dry_run_wrapper_delegates_to_planner_cli(self) -> None:
        self.assertIs(facade.main, cli.main)
        self.assertEqual(facade.__all__, cli.__all__)

    def test_scoring_preserves_explanation_compatibility_import(self) -> None:
        self.assertIs(selection_explanation, explanation_implementation)


if __name__ == "__main__":
    unittest.main()
