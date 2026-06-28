from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.inventory_mapping import (
    format_inventory_mapping_report,
    inventory_mapping_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report recipe inventory-mapping completeness."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = inventory_mapping_report()
    print(
        json.dumps(report, indent=2)
        if args.json
        else format_inventory_mapping_report(report)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
