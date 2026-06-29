from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


AUDIT_PATTERN = re.compile(
    r"^\d{8}-\d{6}-fdp-\d{4}-[a-z0-9-]+(?:-\d+)?\.json$"
)


def validate(root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    audit_root = root / "audit" / "recipe-actions"
    if not audit_root.exists():
        return []
    for path in sorted(audit_root.rglob("*.json")):
        relative = path.relative_to(root)
        if path.parent.name and not re.fullmatch(r"\d{4}", path.parent.name):
            errors.append(f"{relative}: audit files must live under a YYYY directory")
        if not AUDIT_PATTERN.fullmatch(path.name):
            errors.append(f"{relative}: unexpected audit filename format")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"{relative}: invalid JSON ({error.msg})")
            continue
        if payload.get("schema_version") != 1:
            errors.append(f"{relative}: schema_version must be 1")
        for field in ("timestamp", "action", "recipe_id"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{relative}: {field} is required")
        details = payload.get("details")
        if not isinstance(details, dict):
            errors.append(f"{relative}: details must be an object")
        recipe_id = payload.get("recipe_id")
        if isinstance(recipe_id, str) and not re.fullmatch(r"FDP-\d{4}", recipe_id):
            errors.append(f"{relative}: recipe_id must use FDP-NNNN format")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cookbook audit records.")
    parser.add_argument("command", choices=("validate",))
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        count = len(list((PROJECT_ROOT / "audit" / "recipe-actions").rglob("*.json")))
        print(json.dumps({"audit_records": count}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
