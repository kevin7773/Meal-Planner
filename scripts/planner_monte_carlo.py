from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from planner.monte_carlo import format_simulation_report, run_simulation


def monday(value: str) -> dt.date:
    parsed = dt.date.fromisoformat(value)
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("start week must be a Monday")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic Monte Carlo planner testing."
    )
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-week", type=monday)
    parser.add_argument("--horizon-weeks", type=int, default=52)
    parser.add_argument("--ranking-variants", type=int, default=2)
    parser.add_argument("--search-limit", type=int, default=2_000)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def progress(completed: int, total: int) -> None:
        if not args.quiet and completed % max(1, total // 10) == 0:
            print(
                f"Progress: {completed:,}/{total:,}",
                file=sys.stderr,
            )

    report = run_simulation(
        iterations=args.iterations,
        seed=args.seed,
        start_week=args.start_week,
        horizon_weeks=args.horizon_weeks,
        ranking_variants=args.ranking_variants,
        search_evaluation_limit=args.search_limit,
        progress=progress,
    )
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
    if args.json:
        print(serialized, end="")
    else:
        print(format_simulation_report(report))
        if args.output:
            print(f"\nJSON report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
