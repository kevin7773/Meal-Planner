from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from planner.constants import DAYS, LOW_EFFORT_METHODS, ROOT
from scripts.inventory import assess_inventory, load_inventory
from scripts.validate_recipes import split_recipe


def season_for(date: dt.date) -> str:
    if date.month in {6, 7, 8}:
        return "summer"
    if date.month in {9, 10, 11}:
        return "fall"
    if date.month in {12, 1, 2}:
        return "winter"
    return "spring"


def load_recipes(root: Path = ROOT) -> dict[str, dict]:
    recipes: dict[str, dict] = {}
    try:
        _, _, requirement_sets = load_inventory(root)
    except (OSError, KeyError, ValueError):
        requirement_sets = {}
    for path in sorted((root / "recipes").glob("*.md")):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        metadata, _ = split_recipe(path)
        record = dict(metadata)
        record["path"] = path
        record["filename"] = path.name
        record.setdefault("meal_scope", "complete-meal")
        record["inventory_requirements"] = requirement_sets.get(record["id"], [])
        recipes[record["id"]] = record
    return recipes


def recent_recipe_ids(root: Path = ROOT, weeks: int = 3) -> set[str]:
    history_path = root / "preferences" / "meal-history.md"
    if not history_path.exists():
        return set()
    text = history_path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## Week of ", text)[1 : weeks + 1]
    return set(re.findall(r"FDP-\d{4}", "\n".join(sections)))


def override_constraints(week_of: dt.date, root: Path = ROOT) -> tuple[dict[str, str], dict[str, dict]]:
    path = (
        root
        / "overrides"
        / str(week_of.year)
        / f"{week_of.isoformat()}-overrides.json"
    )
    if not path.exists():
        return {}, {}
    records = json.loads(path.read_text(encoding="utf-8")).get("overrides", [])
    assignments: dict[str, str] = {}
    recipes: dict[str, dict] = {}
    for record in records:
        day = record["day"]
        if record.get("type") == "alternate-recipe":
            assignments[day] = record["replacement_recipe_id"]
            continue
        recipe_id = f"OVERRIDE-{week_of.strftime('%Y%m%d')}-{day[:3].upper()}"
        assignments[day] = recipe_id
        recipes[recipe_id] = {
            "id": recipe_id,
            "name": record.get("title") or record["type"].replace("-", " ").title(),
            "revision": 0,
            "status": "override",
            "protein": "vegetarian",
            "meal_scope": "complete-meal",
            "fiber_grams": 0,
            "estimated_cost_usd": 0,
            "kid_friendly_score": 5,
            "kid_friendly_reason": "Human-specified weekly meal override",
            "cooking_method": "no-cook",
            "cook_time_minutes": 0,
            "seasons": [season_for(week_of)],
            "leftover_recipe_ids": [],
            "tags": ["override"],
            "source": "meal-override",
            "filename": None,
            "inventory_requirements": [],
        }
    return assignments, recipes


def eligible_recipes(
    recipes: dict[str, dict],
    day: str,
    season: str,
) -> list[dict]:
    eligible = [
        recipe
        for recipe in recipes.values()
        if (
            recipe["status"] != "retired"
            and season in recipe["seasons"]
            and (
                recipe.get("source") != "generated-idea"
                or recipe.get("day") == day
            )
        )
    ]
    if day == "Monday":
        eligible = [recipe for recipe in eligible if "mexican-monday" in recipe["tags"]]
    if day in {"Tuesday", "Thursday"}:
        eligible = [
            recipe for recipe in eligible
            if recipe["cooking_method"] in LOW_EFFORT_METHODS
        ]
    return sorted(eligible, key=lambda recipe: recipe["id"])


def inventory_match_score(recipe: dict, week_of: dt.date, root: Path) -> int:
    if not recipe.get("inventory_requirements"):
        return 0
    assessment = assess_inventory(
        recipe.get("inventory_requirements", []),
        root=root,
        week_of=week_of,
    )
    return int(assessment["coverage_score"])
