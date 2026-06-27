from __future__ import annotations

import datetime as dt
from pathlib import Path

from scripts.quick_meals import suggest_quick_meal


def plan_quick_meals(
    scored_entries: list[tuple[int, dict]],
    *,
    week_of: dt.date,
    root: Path,
) -> dict[int, dict]:
    return {
        index: quick_meal
        for index, recipe in scored_entries
        if (
            quick_meal := suggest_quick_meal(
                recipe,
                week_of=week_of,
                day_index=index,
                root=root,
            )
        )
        is not None
    }


def quick_meal_requirements(quick_meal: dict | None) -> list[dict]:
    if quick_meal is None:
        return []
    return list(quick_meal.get("requirements", []))


def public_quick_meal(quick_meal: dict | None) -> dict | None:
    if quick_meal is None:
        return None
    return {
        "id": quick_meal["id"],
        "name": quick_meal["name"],
        "fiber_grams": quick_meal["fiber_grams"],
        "estimated_cost_usd": quick_meal["estimated_cost_usd"],
    }
