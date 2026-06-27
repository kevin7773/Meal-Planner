from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from planner.constants import DAYS, LOW_EFFORT_METHODS
    from scripts.schema_version import schema_version_errors
except ModuleNotFoundError:
    from schema_version import schema_version_errors

    DAYS = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    LOW_EFFORT_METHODS = {"slow-cooker", "minimal-cook", "no-cook"}


ROOT = Path(__file__).resolve().parents[1]
VALID_PROTEINS = {
    "chicken",
    "turkey",
    "beef",
    "seafood",
    "pork",
    "vegetarian",
    "other",
}
VALID_METHODS = {
    "stovetop",
    "oven",
    "grill",
    "smoker",
    "blackstone",
    "slow-cooker",
    "minimal-cook",
    "no-cook",
}
FORBIDDEN_TERMS = {"mayo", "mayonnaise"}


def pool_path(root: Path = ROOT) -> Path:
    return root / "planner-data" / "generated-idea-pools.json"


def load_generated_idea_document(root: Path = ROOT) -> dict:
    return json.loads(pool_path(root).read_text(encoding="utf-8"))


def load_generated_idea_pools(root: Path = ROOT) -> dict[str, list[dict]]:
    return load_generated_idea_document(root)["pools"]


def validate_generated_idea_pools(root: Path = ROOT) -> list[str]:
    try:
        document = load_generated_idea_document(root)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to load generated idea pools: {exc}"]

    errors = schema_version_errors(
        document,
        "planner-data/generated-idea-pools.json",
    )
    if errors:
        return errors

    pools = document.get("pools")
    if not isinstance(pools, dict):
        return ["generated idea pools must be an object keyed by day"]
    if set(pools) != set(DAYS):
        errors.append(
            "generated idea pools must define exactly Monday through Sunday"
        )

    seen_names: set[str] = set()
    for day in DAYS:
        entries = pools.get(day)
        if not isinstance(entries, list):
            errors.append(f"{day}: idea pool must be an array")
            continue
        if len(entries) < 3:
            errors.append(f"{day}: idea pool must contain at least 3 entries")
        seen_slots: set[int] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"{day}: each idea must be an object")
                continue
            slot = entry.get("slot")
            label = f"{day} slot {slot}"
            if isinstance(slot, bool) or not isinstance(slot, int) or slot < 1:
                errors.append(f"{day}: slot must be a positive integer")
            elif slot in seen_slots:
                errors.append(f"{day}: duplicate slot {slot}")
            else:
                seen_slots.add(slot)

            name = str(entry.get("name", "")).strip()
            if not name:
                errors.append(f"{label}: name is required")
            elif name.casefold() in seen_names:
                errors.append(f"{label}: duplicate generated idea name")
            else:
                seen_names.add(name.casefold())

            if entry.get("protein") not in VALID_PROTEINS:
                errors.append(f"{label}: invalid protein")
            method = entry.get("cooking_method")
            if method not in VALID_METHODS:
                errors.append(f"{label}: invalid cooking_method")
            if day in {"Tuesday", "Thursday"} and method not in LOW_EFFORT_METHODS:
                errors.append(f"{label}: {day} ideas must use a low-effort method")

            for field in ("fiber_grams", "estimated_cost_usd"):
                value = entry.get(field)
                if not isinstance(value, (int, float)) or value < 0:
                    errors.append(f"{label}: {field} must be non-negative")
            if entry.get("kid_friendly_score") not in {4, 5}:
                errors.append(f"{label}: kid_friendly_score must be 4 or 5")
            if not str(entry.get("kid_friendly_reason", "")).strip():
                errors.append(f"{label}: kid_friendly_reason is required")

            tags = entry.get("tags")
            if (
                not isinstance(tags, list)
                or any(not isinstance(tag, str) or not tag for tag in tags)
            ):
                errors.append(f"{label}: tags must be an array of strings")
                tags = []
            if len(tags) != len(set(tags)):
                errors.append(f"{label}: tags must not contain duplicates")
            if day == "Monday" and "mexican-monday" not in tags:
                errors.append(f"{label}: Monday ideas require mexican-monday tag")

            searchable = " ".join(
                [name, str(entry.get("kid_friendly_reason", "")), *tags]
            ).casefold()
            if any(term in searchable for term in FORBIDDEN_TERMS):
                errors.append(f"{label}: mayo and mayonnaise are not allowed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated dry-run idea pools."
    )
    parser.add_argument("command", choices=("validate",))
    parser.parse_args()
    errors = validate_generated_idea_pools()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Generated idea pools are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
