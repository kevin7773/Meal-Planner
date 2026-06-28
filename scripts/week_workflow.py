from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.week_workflow import (
    approve_review_package,
    generate_review_package,
    inspect_week,
    send_approved_emails,
    test_email_credentials,
)


def monday(value: str) -> dt.date:
    parsed = dt.date.fromisoformat(value)
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("week must be a Monday")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review, approve, and deliver a weekly planning package."
    )
    parser.add_argument(
        "command",
        choices=("inspect", "generate", "approve", "send", "test-email"),
    )
    parser.add_argument("--week", required=True, type=monday)
    parser.add_argument("--actor")
    parser.add_argument("--sender")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "inspect":
            result = inspect_week(args.week)
        elif args.command == "generate":
            result = generate_review_package(args.week)
        elif args.command == "approve":
            if not args.actor:
                parser.error("approve requires --actor")
            result = approve_review_package(
                args.week,
                actor=args.actor,
            )
        elif args.command == "send":
            if not args.actor or not args.sender:
                parser.error("send requires --actor and --sender")
            result = send_approved_emails(
                args.week,
                actor=args.actor,
                sender=args.sender,
                password=os.environ.get(
                    "MEAL_PLANNER_EMAIL_PASSWORD",
                    "",
                ),
            )
        else:
            if not args.sender:
                parser.error("test-email requires --sender")
            result = test_email_credentials(
                sender=args.sender,
                password=os.environ.get(
                    "MEAL_PLANNER_EMAIL_PASSWORD",
                    "",
                ),
            )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Weekly workflow failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.command == "test-email":
            print(f"{result['sender']}: {result['status']}")
        else:
            print(
                f"{result['week_of']}: {result['status']} "
                f"({result['menu_path']})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
