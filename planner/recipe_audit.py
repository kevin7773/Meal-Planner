from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from planner.constants import ROOT


def write_recipe_audit(
    *,
    action: str,
    recipe_id: str,
    root: Path = ROOT,
    details: dict | None = None,
) -> Path:
    now = dt.datetime.now(dt.timezone.utc)
    year_root = root / "audit" / "recipe-actions" / now.strftime("%Y")
    year_root.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", action.lower()).strip("-") or "action"
    base = f"{now.strftime('%Y%m%d-%H%M%S')}-{recipe_id.lower()}-{slug}"
    path = year_root / f"{base}.json"
    counter = 2
    while path.exists():
        path = year_root / f"{base}-{counter}.json"
        counter += 1
    payload = {
        "schema_version": 1,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "action": action,
        "recipe_id": recipe_id,
        "details": details or {},
    }
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path
