from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.inventory import assess_inventory, load_inventory
    from scripts.schema_version import schema_version_errors
except ModuleNotFoundError:
    from inventory import assess_inventory, load_inventory
    from schema_version import schema_version_errors


ROOT = Path(__file__).resolve().parents[1]


def load_side_document(root: Path = ROOT) -> dict:
    return json.loads(
        (root / "sides" / "side-dishes.json").read_text(encoding="utf-8")
    )


def load_sides(root: Path = ROOT) -> list[dict]:
    return load_side_document(root)["sides"]


def validate_sides(root: Path = ROOT) -> list[str]:
    try:
        document = load_side_document(root)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to load side dishes: {exc}"]
    errors = schema_version_errors(document, "sides/side-dishes.json")
    if errors:
        return errors
    try:
        sides = document["sides"]
        catalog, _, _ = load_inventory(root)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return [f"unable to load side dishes: {exc}"]
    seen: set[str] = set()
    for side in sides:
        side_id = side.get("id")
        if not isinstance(side_id, str) or not side_id.startswith("SIDE-"):
            errors.append("side dish has an invalid ID")
        elif side_id in seen:
            errors.append(f"duplicate side ID: {side_id}")
        seen.add(side_id)
        if not str(side.get("name", "")).strip():
            errors.append(f"{side_id}: name is required")
        if side.get("kid_friendly_score") not in {4, 5}:
            errors.append(f"{side_id}: kid_friendly_score must be 4 or 5")
        if not str(side.get("kid_friendly_reason", "")).strip():
            errors.append(f"{side_id}: kid_friendly_reason is required")
        if not isinstance(side.get("fiber_grams"), (int, float)) or side["fiber_grams"] < 0:
            errors.append(f"{side_id}: fiber_grams must be non-negative")
        if not isinstance(side.get("estimated_cost_usd"), (int, float)) or side["estimated_cost_usd"] < 0:
            errors.append(f"{side_id}: estimated_cost_usd must be non-negative")
        for requirement in side.get("requirements", []):
            if requirement.get("item_id") not in catalog:
                errors.append(
                    f"{side_id}: unknown ingredient {requirement.get('item_id')}"
                )
            if not isinstance(requirement.get("quantity"), (int, float)) or requirement["quantity"] <= 0:
                errors.append(f"{side_id}: requirement quantity must be positive")
    return errors


def suggest_sides(
    recipe: dict,
    *,
    season: str,
    week_of,
    root: Path = ROOT,
    count: int = 2,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    if recipe.get("meal_scope", "complete-meal") != "entree":
        return []
    title = recipe.get("name", "").lower()
    exclude_ids = exclude_ids or set()
    candidates = []
    for side in load_sides(root):
        if season not in side["seasons"] or side["kid_friendly_score"] < 4:
            continue
        if side["id"] in exclude_ids:
            continue
        if any(tag in title for tag in side.get("tags", []) if len(tag) > 4):
            continue
        inventory = assess_inventory(
            side["requirements"],
            root=root,
            week_of=week_of,
        )
        method_bonus = (
            8
            if side["cooking_method"] == recipe.get("cooking_method")
            else 4
            if side["cooking_method"] == "no-cook"
            else 0
        )
        score = (
            side["fiber_grams"] * 8
            + side["kid_friendly_score"] * 10
            + inventory["coverage_score"] * 0.3
            + method_bonus
            - side["estimated_cost_usd"]
        )
        enriched = dict(side)
        enriched["inventory_coverage_score"] = inventory["coverage_score"]
        enriched["score"] = round(score, 1)
        candidates.append(enriched)
    candidates.sort(key=lambda side: (-side["score"], side["id"]))
    selected: list[dict] = []
    used_primary_tags: set[str] = set()
    for side in candidates:
        primary_tags = set(side.get("tags", [])) & {"fruit", "vegetable", "beans", "whole-grain"}
        if primary_tags & used_primary_tags:
            continue
        selected.append(side)
        used_primary_tags.update(primary_tags)
        if len(selected) == count:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate",))
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate_sides()
        if errors:
            for error in errors:
                print(f"- {error}")
            return 1
        print("Side-dish library is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
