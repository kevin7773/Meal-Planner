from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.recipe_audit import write_recipe_audit
from planner.recipe_cache import build_recipe_cache
from planner.recipe_images import record_recipe_image


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage recipe image metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set")
    set_parser.add_argument("--id", required=True)
    set_parser.add_argument("--source-type", required=True)
    set_parser.add_argument("--source", required=True)
    set_parser.add_argument("--prompt")
    set_parser.add_argument("--captured-on")

    args = parser.parse_args()
    try:
        record = record_recipe_image(
            args.id,
            source_type=args.source_type,
            source=args.source,
            prompt=args.prompt,
            captured_on=args.captured_on,
        )
        build_recipe_cache(PROJECT_ROOT)
        write_recipe_audit(
            action="image-update",
            recipe_id=args.id,
            details=record,
        )
        print(record["filename"])
        return 0
    except (OSError, ValueError) as error:
        print(f"Recipe image update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
