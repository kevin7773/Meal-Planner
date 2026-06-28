from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.performance_gate import (
    BASELINE_PATH,
    load_baseline,
    run_performance_gate,
    update_approved_metrics,
    write_baseline,
    write_simulation_report,
)


DISPLAY_NAMES = {
    "average_grocery_bill_usd": "average_recipe_cost_usd",
    "recipe_diversity_percentage": "recipe_diversity",
}


def format_metric_value(
    metric: str,
    value: float,
    *,
    signed: bool = False,
) -> str:
    if metric == "average_grocery_bill_usd":
        sign = "+" if signed and value > 0 else "-" if value < 0 else ""
        return f"{sign}${abs(value):.2f}"
    if metric == "recipe_diversity_percentage":
        return f"{value:+.1f}%" if signed else f"{value:.1f}%"
    if metric == "final_constraint_violations":
        return f"{value:+g}" if signed else f"{value:g}"
    return f"{value:+.1f}" if signed else f"{value:.1f}"


def format_result(result: dict) -> str:
    lines = [
        (
            "Planner performance regression gate: "
            + ("PASS" if result["passed"] else "FAIL")
        ),
        "",
    ]
    for check in result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        metric = check["metric"]
        display_name = DISPLAY_NAMES.get(metric, metric)
        actual = format_metric_value(metric, check["actual"])
        if not check["passed"] and "approved" in check:
            approved = format_metric_value(metric, check["approved"])
            delta = format_metric_value(
                metric,
                check["delta"],
                signed=True,
            )
            lines.append(
                f"[{status}] {display_name}: {approved} -> {actual} "
                f"({delta}); {check['requirement']}"
            )
        else:
            lines.append(
                f"[{status}] {display_name}: {actual} "
                f"({check['requirement']})"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or deliberately update planner performance policy."
    )
    parser.add_argument(
        "command",
        choices=("check", "validate", "update-baseline"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
    )
    parser.add_argument(
        "--reason",
        help="Required review note for update-baseline.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--report-output",
        type=Path,
        help="Write the complete simulation report as JSON.",
    )
    args = parser.parse_args()

    if args.command == "validate":
        load_baseline(args.baseline)
        print(f"Valid performance baseline: {args.baseline}")
        return 0

    if args.command == "update-baseline" and not args.reason:
        parser.error("update-baseline requires --reason")

    result = run_performance_gate(baseline_path=args.baseline)
    if args.report_output:
        write_simulation_report(args.report_output, result["report"])
    if args.command == "update-baseline":
        baseline = load_baseline(args.baseline)
        updated = update_approved_metrics(
            baseline,
            result["report"],
            reason=args.reason,
        )
        write_baseline(args.baseline, updated)
        print(f"Updated approved baseline: {args.baseline}")
        print(format_result(result))
        return 0

    if args.json:
        payload = {
            "passed": result["passed"],
            "metrics": result["metrics"],
            "checks": result["checks"],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_result(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
