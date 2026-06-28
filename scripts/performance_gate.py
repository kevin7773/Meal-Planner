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
)


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
        lines.append(
            f"[{status}] {check['metric']}: {check['actual']} "
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
    args = parser.parse_args()

    if args.command == "validate":
        load_baseline(args.baseline)
        print(f"Valid performance baseline: {args.baseline}")
        return 0

    if args.command == "update-baseline" and not args.reason:
        parser.error("update-baseline requires --reason")

    result = run_performance_gate(baseline_path=args.baseline)
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
