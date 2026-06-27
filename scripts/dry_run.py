"""Backward-compatible wrapper for the planner command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.planner_cli import *  # noqa: F403
from scripts.planner_cli import __all__, main


if __name__ == "__main__":
    raise SystemExit(main())
