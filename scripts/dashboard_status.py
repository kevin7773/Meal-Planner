from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.dashboard_status import build_dashboard_status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report read-only operational status for the suite dashboard."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_dashboard_status()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for item in report["items"]:
            print(
                f"{item['label']}: {item['value']} | {item['detail']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
