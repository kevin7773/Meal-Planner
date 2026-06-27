from __future__ import annotations

import datetime as dt
from pathlib import Path

from scripts.inventory import assess_inventory, load_inventory
from scripts.weather_context import is_heat_friendly


def expiring_refrigerated_items(
    requirements: list[dict],
    *,
    meal_date: dt.date,
    week_of: dt.date,
    root: Path,
) -> list[str]:
    catalog, stock, _ = load_inventory(root)
    required_ids = {item["item_id"] for item in requirements}
    week_end = week_of + dt.timedelta(days=6)
    names: set[str] = set()
    for lot in stock.get("items", []):
        item_id = lot.get("item_id")
        if item_id not in required_ids or item_id not in catalog:
            continue
        if catalog[item_id]["class"] != "refrigerated":
            continue
        expires_on = lot.get("expires_on")
        if not expires_on or float(lot.get("quantity") or 0) <= 0:
            continue
        try:
            expiration = dt.date.fromisoformat(expires_on)
        except ValueError:
            continue
        if meal_date <= expiration <= week_end:
            names.add(catalog[item_id]["name"])
    return sorted(names)


def selection_explanation(
    recipe: dict,
    *,
    day: str,
    day_index: int,
    week_of: dt.date,
    requirements: list[dict],
    recent_ids: set[str],
    fixed_assignments: dict[str, str],
    weather_rules: dict,
    weather_category: str,
    root: Path,
) -> dict:
    is_override = (
        recipe.get("status") == "override"
        or fixed_assignments.get(day) == recipe["id"]
    )
    inventory_coverage = None
    if requirements:
        inventory_coverage = int(
            assess_inventory(
                requirements,
                root=root,
                week_of=week_of,
            )["coverage_score"]
        )
    meal_date = week_of + dt.timedelta(days=day_index)
    expiring_items = expiring_refrigerated_items(
        requirements,
        meal_date=meal_date,
        week_of=week_of,
        root=root,
    )
    if is_override:
        day_rule = "Required by human meal override"
    elif day == "Monday":
        day_rule = "Satisfies Mexican Monday"
    elif day in {"Tuesday", "Thursday"}:
        day_rule = f"Satisfies {day} low-effort rule"
    else:
        day_rule = f"Fits {day} schedule"

    reasons = [
        (
            f"Inventory coverage: {inventory_coverage}/100"
            if inventory_coverage is not None
            else "Inventory coverage: not applicable"
        )
    ]
    if expiring_items:
        reasons.append(
            "Uses expiring refrigerated inventory: " + ", ".join(expiring_items)
        )
    reasons.append(day_rule)
    reasons.append(
        "Recent rotation: repeat within window"
        if recipe["id"] in recent_ids
        else "Recent rotation: no recent repeat"
    )
    weather_fit = is_heat_friendly(recipe, weather_rules)
    if weather_fit:
        reasons.append(f"Weather fit: heat-friendly for {weather_category}")
    reasons.append(f"Kid score: {recipe['kid_friendly_score']}/5")
    return {
        "inventory_coverage_score": inventory_coverage,
        "expiring_refrigerated_items": expiring_items,
        "day_rule": day_rule,
        "recent_repeat": recipe["id"] in recent_ids,
        "weather_fit": weather_fit,
        "kid_score": recipe["kid_friendly_score"],
        "reasons": reasons,
    }
