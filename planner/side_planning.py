from __future__ import annotations

import datetime as dt
from pathlib import Path

from scripts.side_dishes import suggest_sides


def plan_side_suggestions(
    recipes: list[dict],
    *,
    season: str,
    week_of: dt.date,
    root: Path,
) -> dict[str, list[dict]]:
    side_map: dict[str, list[dict]] = {}
    used_side_ids: set[str] = set()
    for recipe in recipes:
        suggestions = suggest_sides(
            recipe,
            season=season,
            week_of=week_of,
            root=root,
            exclude_ids=used_side_ids,
        )
        side_map[recipe["id"]] = suggestions
        used_side_ids.update(side["id"] for side in suggestions)
    return side_map


def side_requirements(sides: list[dict]) -> list[dict]:
    return [
        requirement
        for side in sides
        for requirement in side.get("requirements", [])
    ]


def public_side_suggestions(sides: list[dict]) -> list[dict]:
    return [
        {
            "id": side["id"],
            "name": side["name"],
            "fiber_grams": side["fiber_grams"],
            "estimated_cost_usd": side["estimated_cost_usd"],
            "kid_friendly_reason": side["kid_friendly_reason"],
        }
        for side in sides
    ]
