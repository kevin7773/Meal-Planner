from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.assignment import constrained_assignments, format_assignment_diagnostics
from planner.commit import apply_proposal, commit_assignments
from planner.constants import (
    DAYS,
    LOW_EFFORT_METHODS,
    MAX_OPTION_OVERLAP,
    MAX_PROTEIN_PER_WEEK,
    MAX_USER_IDEAS_PER_WEEK,
    ROOT,
)
from planner.eligibility import (
    eligible_recipes,
    inventory_match_score,
    load_recipes,
    override_constraints,
    recent_recipe_ids,
    season_for,
)
from planner.proposal import (
    IDEA_POOLS,
    ProposalGenerationError,
    generate_proposals,
    generated_ideas,
    idea_inventory_requirements,
    user_idea_recipes,
)
from planner.reporting import proposal_report
from planner.scoring import (
    evaluate_proposal,
    expiring_refrigerated_items,
    selection_explanation,
)


def parse_week(value: str) -> dt.date:
    parsed = dt.date.fromisoformat(value)
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("week must be a Monday")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan weekly menus without side effects.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--week", required=True, type=parse_week)
    generate_parser.add_argument("--count", type=int, default=3)
    generate_parser.add_argument("--json", action="store_true")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--week", required=True, type=parse_week)
    apply_parser.add_argument("--recipes", required=True)
    apply_parser.add_argument("--actor", required=True)
    apply_parser.add_argument("--accept-warnings", action="store_true")

    args = parser.parse_args()
    if args.command == "generate":
        try:
            proposals = generate_proposals(args.week, args.count)
        except ProposalGenerationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(proposals, indent=2))
        else:
            print(
                "\n\n".join(
                    proposal_report(proposal, index)
                    for index, proposal in enumerate(proposals, start=1)
                )
            )
        return 0

    assignments = [value.strip() for value in args.recipes.split(",") if value.strip()]
    try:
        output = commit_assignments(
            args.week,
            assignments,
            actor=args.actor,
            accept_warnings=args.accept_warnings,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"Unable to commit dry run: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


__all__ = [
    "DAYS",
    "IDEA_POOLS",
    "LOW_EFFORT_METHODS",
    "MAX_OPTION_OVERLAP",
    "MAX_PROTEIN_PER_WEEK",
    "MAX_USER_IDEAS_PER_WEEK",
    "ROOT",
    "apply_proposal",
    "commit_assignments",
    "constrained_assignments",
    "eligible_recipes",
    "evaluate_proposal",
    "expiring_refrigerated_items",
    "format_assignment_diagnostics",
    "generate_proposals",
    "generated_ideas",
    "idea_inventory_requirements",
    "inventory_match_score",
    "load_recipes",
    "main",
    "override_constraints",
    "parse_week",
    "proposal_report",
    "ProposalGenerationError",
    "recent_recipe_ids",
    "season_for",
    "selection_explanation",
    "user_idea_recipes",
]


if __name__ == "__main__":
    raise SystemExit(main())
