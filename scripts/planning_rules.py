from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.rules import (
    format_rule_coverage,
    load_rules,
    rule_coverage_summary,
    validate_rules,
)
from planner.telemetry import load_telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect planning rule coverage.")
    parser.add_argument("command", choices=("report", "validate"))
    parser.add_argument("--month")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate_rules()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("Planning rule registry is valid.")
        return 0
    summary = rule_coverage_summary(
        load_telemetry(),
        load_rules(),
        month=args.month,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_rule_coverage(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
