from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.telemetry import (
    format_recommendation_drift,
    format_recipe_utilization,
    format_telemetry_summary,
    load_telemetry,
    recommendation_drift_summary,
    recipe_utilization_rows,
    telemetry_summary,
    validate_telemetry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect planner telemetry.")
    parser.add_argument("command", choices=("show", "validate"))
    parser.add_argument("--json", action="store_true")
    report_mode = parser.add_mutually_exclusive_group()
    report_mode.add_argument("--recipes", action="store_true")
    report_mode.add_argument("--drift", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate_telemetry()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("Planner telemetry is valid.")
        return 0

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
    summary = telemetry_summary(document)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_telemetry_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
