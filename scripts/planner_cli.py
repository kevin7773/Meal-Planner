from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
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
    ProposalGenerationError,
    generate_proposals,
    generated_ideas,
    idea_inventory_requirements,
    user_idea_recipes,
)
from planner.reporting import proposal_report
from planner.rules import (
    format_rule_coverage,
    load_rules,
    rule_coverage_summary,
)
from planner.scoring import (
    evaluate_proposal,
    expiring_refrigerated_items,
    selection_explanation,
)
from planner.telemetry import (
    format_recommendation_drift,
    format_recipe_utilization,
    format_telemetry_summary,
    load_telemetry,
    recommendation_drift_summary,
    recipe_utilization_rows,
    record_generation,
    telemetry_summary,
)


def parse_week(value: str) -> dt.date:
    parsed = dt.date.fromisoformat(value)
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("week must be a Monday")
    return parsed


def parse_diners(value: str) -> list[int]:
    try:
        diners = [
            int(item.strip())
            for item in value.split(",")
            if item.strip()
        ]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "diners must be comma-separated integers"
        ) from error
    if len(diners) != 7 or any(not 1 <= diner <= 20 for diner in diners):
        raise argparse.ArgumentTypeError(
            "diners must contain seven values from 1 to 20"
        )
    return diners


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan weekly menus without side effects.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--week", required=True, type=parse_week)
    generate_parser.add_argument("--count", type=int, default=3)
    generate_parser.add_argument(
        "--diners",
        type=parse_diners,
        default=[4] * 7,
    )
    generate_parser.add_argument("--json", action="store_true")
    generate_parser.add_argument("--no-telemetry", action="store_true")

    telemetry_parser = subparsers.add_parser("telemetry")
    telemetry_parser.add_argument("--json", action="store_true")
    telemetry_mode = telemetry_parser.add_mutually_exclusive_group()
    telemetry_mode.add_argument("--recipes", action="store_true")
    telemetry_mode.add_argument("--drift", action="store_true")
    telemetry_mode.add_argument("--rules", action="store_true")
    telemetry_parser.add_argument("--month")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--week", required=True, type=parse_week)
    apply_parser.add_argument("--recipes", required=True)
    apply_parser.add_argument("--actor", required=True)
    apply_parser.add_argument(
        "--diners",
        type=parse_diners,
        default=[4] * 7,
    )
    apply_parser.add_argument("--accept-warnings", action="store_true")

    args = parser.parse_args()
    if args.command == "telemetry":
        document = load_telemetry()
        if args.recipes:
            rows = recipe_utilization_rows(document)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                print(format_recipe_utilization(rows))
            return 0
        if args.drift:
            drift = recommendation_drift_summary(document)
            if args.json:
                print(json.dumps(drift, indent=2))
            else:
                print(format_recommendation_drift(drift))
            return 0
        if args.rules:
            coverage = rule_coverage_summary(
                document,
                load_rules(),
                month=args.month,
            )
            if args.json:
                print(json.dumps(coverage, indent=2))
            else:
                print(format_rule_coverage(coverage))
            return 0
        summary = telemetry_summary(document)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(format_telemetry_summary(summary))
        return 0

    if args.command == "generate":
        started = time.perf_counter()
        try:
            proposals = generate_proposals(
                args.week,
                args.count,
                planned_diners=args.diners,
            )
        except ProposalGenerationError as exc:
            if not args.no_telemetry:
                try:
                    record_generation(
                        week_of=args.week,
                        requested_proposals=args.count,
                        generation_time_ms=(
                            time.perf_counter() - started
                        )
                        * 1000,
                        failure_diagnostics=exc.diagnostics,
                    )
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    pass
            print(str(exc), file=sys.stderr)
            return 1
        if not args.no_telemetry:
            try:
                record_generation(
                    week_of=args.week,
                    requested_proposals=args.count,
                    generation_time_ms=(time.perf_counter() - started) * 1000,
                    proposals=proposals,
                )
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
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
            planned_diners=args.diners,
            accept_warnings=args.accept_warnings,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"Unable to commit dry run: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


__all__ = [
    "DAYS",
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
