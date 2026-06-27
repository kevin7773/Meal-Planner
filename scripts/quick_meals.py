from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENTS_ONLY_REASON = "Not kid friendly - for the parents only"


def load_quick_meals(root: Path = ROOT) -> list[dict]:
    path = root / "quick-meals" / "kids-quick-meals.json"
    return json.loads(path.read_text(encoding="utf-8"))["quick_meals"]


def validate_quick_meals(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        meals = load_quick_meals(root)
        catalog = json.loads(
            (root / "inventory" / "catalog.json").read_text(encoding="utf-8")
        )
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        return [f"Unable to load quick-meal data: {exc}"]
    catalog_ids = {item["id"] for item in catalog["items"]}
    seen: set[str] = set()
    for meal in meals:
        meal_id = meal.get("id", "<missing>")
        if meal_id in seen:
            errors.append(f"{meal_id}: duplicate quick-meal ID")
        seen.add(meal_id)
        if not str(meal.get("name", "")).strip():
            errors.append(f"{meal_id}: name is required")
        if meal.get("kid_friendly_score") not in {4, 5}:
            errors.append(f"{meal_id}: kid_friendly_score must be 4 or 5")
        for field in ("estimated_cost_usd", "fiber_grams"):
            value = meal.get(field)
            if not isinstance(value, (int, float)) or value < 0:
                errors.append(f"{meal_id}: {field} must be non-negative")
        for requirement in meal.get("requirements", []):
            if requirement.get("item_id") not in catalog_ids:
                errors.append(
                    f"{meal_id}: unknown inventory item {requirement.get('item_id')}"
                )
            if not isinstance(requirement.get("quantity"), (int, float)):
                errors.append(f"{meal_id}: requirement quantity must be numeric")
    return errors


def suggest_quick_meal(
    recipe: dict,
    *,
    week_of: dt.date,
    day_index: int,
    root: Path = ROOT,
) -> dict | None:
    preferred_id = recipe.get("preferred_kids_quick_meal_id")
    needs_alternative = (
        recipe.get("kid_friendly_reason") == PARENTS_ONLY_REASON
        or recipe.get("kid_alternative_required") is True
    )
    if not needs_alternative:
        return None
    meals = load_quick_meals(root)
    if preferred_id:
        return next(
            (dict(meal) for meal in meals if meal["id"] == preferred_id),
            None,
        )
    seed = sum(ord(character) for character in str(recipe.get("id", "")))
    return dict(meals[(seed + week_of.toordinal() + day_index) % len(meals)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate kid quick-meal options.")
    parser.add_argument("command", choices=("validate",))
    parser.parse_args()
    errors = validate_quick_meals()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Kid quick-meal library is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
