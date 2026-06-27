from __future__ import annotations

import collections
import datetime as dt
import re
from pathlib import Path

from planner.constants import DAYS, LOW_EFFORT_METHODS, MAX_PROTEIN_PER_WEEK, ROOT
from planner.eligibility import override_constraints, recent_recipe_ids, season_for
from scripts.inventory import assess_inventory, load_inventory
from scripts.quick_meals import PARENTS_ONLY_REASON, suggest_quick_meal
from scripts.side_dishes import suggest_sides
from scripts.weather_context import is_heat_friendly, load_weather_context, load_weather_rules


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
    if is_heat_friendly(recipe, weather_rules):
        reasons.append(f"Weather fit: heat-friendly for {weather_category}")
    reasons.append(f"Kid score: {recipe['kid_friendly_score']}/5")
    return {
        "inventory_coverage_score": inventory_coverage,
        "expiring_refrigerated_items": expiring_items,
        "day_rule": day_rule,
        "recent_repeat": recipe["id"] in recent_ids,
        "weather_fit": is_heat_friendly(recipe, weather_rules),
        "kid_score": recipe["kid_friendly_score"],
        "reasons": reasons,
    }


def evaluate_proposal(
    week_of: dt.date,
    assignments: list[str],
    recipes: dict[str, dict] | None = None,
    *,
    root: Path = ROOT,
) -> dict:
    recipes = recipes or load_recipes(root)
    errors: list[str] = []
    warnings: list[str] = []
    season = season_for(week_of)
    weather = load_weather_context(week_of, root)
    weather_rules = load_weather_rules(root)
    category_rule = weather_rules["categories"][weather["category"]]
    fixed_assignments, _ = override_constraints(week_of, root)

    if week_of.weekday() != 0:
        errors.append("Week must start on Monday.")
    if len(assignments) != 7:
        errors.append("A proposal must contain exactly seven recipe IDs.")

    selected: list[dict] = []
    for index, recipe_id in enumerate(assignments[:7]):
        recipe = recipes.get(recipe_id)
        if recipe is None:
            errors.append(f"{DAYS[index]} references unknown recipe {recipe_id}.")
            continue
        selected.append(recipe)
        is_override = (
            recipe.get("status") == "override"
            or fixed_assignments.get(DAYS[index]) == recipe_id
        )
        if not is_override and season not in recipe["seasons"]:
            errors.append(f"{recipe_id} is not approved for {season}.")
        if (
            not is_override
            and DAYS[index] == "Monday"
            and "mexican-monday" not in recipe["tags"]
        ):
            errors.append(f"Monday recipe {recipe_id} is not tagged mexican-monday.")
        if (
            not is_override
            and
            DAYS[index] in {"Tuesday", "Thursday"}
            and recipe["cooking_method"] not in LOW_EFFORT_METHODS
        ):
            errors.append(
                f"{DAYS[index]} recipe {recipe_id} must be slow-cooker, "
                "minimal-cook, or no-cook."
            )
        if (
            not is_override
            and recipe.get("kid_friendly_score", 0) < 4
            and recipe.get("kid_friendly_reason") != PARENTS_ONLY_REASON
        ):
            errors.append(
                f"{DAYS[index]} recipe {recipe_id} does not meet the kid-friendly threshold."
            )
        if not is_override and not str(recipe.get("kid_friendly_reason", "")).strip():
            errors.append(
                f"{DAYS[index]} recipe {recipe_id} lacks a kid-friendly rationale."
            )

    counts = collections.Counter(assignments)
    repeated = {recipe_id: count for recipe_id, count in counts.items() if count > 1}
    for recipe_id, repeat_count in sorted(repeated.items()):
        warnings.append(f"{recipe_id} appears {repeat_count} times this week.")

    protein_counts = collections.Counter(
        recipe["protein"]
        for recipe in selected
        if recipe.get("status") != "override"
    )
    for protein, protein_count in sorted(protein_counts.items()):
        if protein_count > MAX_PROTEIN_PER_WEEK:
            errors.append(
                f"Protein {protein} appears {protein_count} times; "
                f"the weekly maximum is {MAX_PROTEIN_PER_WEEK}."
            )

    heat_friendly_count = sum(
        is_heat_friendly(recipe, weather_rules) for recipe in selected
    )
    minimum_heat_friendly = category_rule["minimum_heat_friendly_meals"]
    if heat_friendly_count < minimum_heat_friendly:
        errors.append(
            f"{weather['category']} week requires at least "
            f"{minimum_heat_friendly} heat-friendly meals; found "
            f"{heat_friendly_count}."
        )
    excluded_tags = set(category_rule["exclude_tags"])
    for recipe in selected:
        recipe_terms = set(recipe.get("tags", [])) | set(
            re.findall(r"[a-z]+", recipe["name"].lower())
        )
        conflict = sorted(excluded_tags & recipe_terms)
        if conflict:
            errors.append(
                f"{recipe['id']} conflicts with {weather['category']} weather: "
                + ", ".join(conflict)
            )

    candidate_ids = sorted(
        {recipe["id"] for recipe in selected if recipe["status"] == "candidate"}
    )
    if candidate_ids:
        warnings.append("Family review requested for candidates: " + ", ".join(candidate_ids))
    idea_ids = sorted(
        {recipe["id"] for recipe in selected if recipe["status"] == "proposed"}
    )
    if idea_ids:
        warnings.append(
            "Selected ideas must become full FDP candidate recipes after commit: "
            + ", ".join(idea_ids)
        )

    recent_ids = recent_recipe_ids(root)
    recent_repeats = sorted(set(assignments) & recent_ids)
    if recent_repeats:
        warnings.append("Used within the recent rotation window: " + ", ".join(recent_repeats))

    scored_entries = [
        (index, recipe)
        for index, recipe in enumerate(selected)
        if recipe.get("status") != "override"
    ]
    scored_meals = [recipe for _, recipe in scored_entries]
    side_map: dict[str, list[dict]] = {}
    used_side_ids: set[str] = set()
    for recipe in scored_meals:
        suggestions = suggest_sides(
            recipe,
            season=season,
            week_of=week_of,
            root=root,
            exclude_ids=used_side_ids,
        )
        side_map[recipe["id"]] = suggestions
        used_side_ids.update(side["id"] for side in suggestions)
    quick_meal_map = {
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
    estimated_cost = round(
        sum(float(recipe["estimated_cost_usd"]) for recipe in scored_meals)
        + sum(
            float(side["estimated_cost_usd"])
            for suggestions in side_map.values()
            for side in suggestions
        )
        + sum(
            float(quick_meal["estimated_cost_usd"])
            for quick_meal in quick_meal_map.values()
        ),
        2,
    )
    average_fiber = (
        round(
            sum(
                float(recipe["fiber_grams"])
                + sum(
                    float(side["fiber_grams"])
                    for side in side_map.get(recipe["id"], [])
                )
                for recipe in scored_meals
            )
            / len(scored_meals),
            1,
        )
        if scored_meals
        else 0.0
    )
    average_kid_friendly = (
        round(
            sum(
                float(
                    quick_meal_map.get(index, recipe)["kid_friendly_score"]
                )
                for index, recipe in scored_entries
            )
            / len(scored_entries),
            1,
        )
        if scored_entries
        else 0.0
    )
    inventory_requirements = [
        requirement
        for recipe in scored_meals
        for requirement in recipe.get("inventory_requirements", [])
    ]
    inventory_requirements.extend(
        requirement
        for suggestions in side_map.values()
        for side in suggestions
        for requirement in side.get("requirements", [])
    )
    inventory_requirements.extend(
        requirement
        for quick_meal in quick_meal_map.values()
        for requirement in quick_meal.get("requirements", [])
    )
    inventory = assess_inventory(
        inventory_requirements,
        root=root,
        week_of=week_of,
    )
    estimated_shopping_cost = round(
        max(0.0, estimated_cost - inventory["estimated_savings_usd"]),
        2,
    )

    rotation_score = 100
    rotation_score -= sum((count - 1) * 12 for count in repeated.values())
    rotation_score -= len(recent_repeats) * 10
    method_counts = collections.Counter(recipe["cooking_method"] for recipe in scored_meals)
    protein_counts = collections.Counter(recipe["protein"] for recipe in scored_meals)
    rotation_score -= sum(max(0, count - 3) * 3 for count in method_counts.values())
    rotation_score -= sum(max(0, count - MAX_PROTEIN_PER_WEEK) * 3 for count in protein_counts.values())
    rotation_score = max(0, rotation_score)

    meals = []
    for index, recipe in enumerate(selected):
        meal_requirements = list(recipe.get("inventory_requirements", []))
        meal_requirements.extend(
            requirement
            for side in side_map.get(recipe["id"], [])
            for requirement in side.get("requirements", [])
        )
        if index in quick_meal_map:
            meal_requirements.extend(
                quick_meal_map[index].get("requirements", [])
            )
        explanation = selection_explanation(
            recipe,
            day=DAYS[index],
            day_index=index,
            week_of=week_of,
            requirements=meal_requirements,
            recent_ids=recent_ids,
            fixed_assignments=fixed_assignments,
            weather_rules=weather_rules,
            weather_category=weather["category"],
            root=root,
        )
        meals.append(
            {
                "day": DAYS[index],
                "date": (week_of + dt.timedelta(days=index)).isoformat(),
                "recipe_id": recipe["id"],
                "revision": recipe["revision"],
                "status": recipe["status"],
                "name": recipe["name"],
                "protein": recipe["protein"],
                "cooking_method": recipe["cooking_method"],
                "fiber_grams": recipe["fiber_grams"],
                "estimated_cost_usd": recipe["estimated_cost_usd"],
                "kid_friendly_score": recipe["kid_friendly_score"],
                "kid_friendly_reason": recipe["kid_friendly_reason"],
                "meal_scope": recipe.get("meal_scope", "complete-meal"),
                "selection_explanation": explanation,
                "side_suggestions": [
                    {
                        "id": side["id"],
                        "name": side["name"],
                        "fiber_grams": side["fiber_grams"],
                        "estimated_cost_usd": side["estimated_cost_usd"],
                        "kid_friendly_reason": side["kid_friendly_reason"],
                    }
                    for side in side_map.get(recipe["id"], [])
                ],
                "kids_quick_meal": (
                    {
                        "id": quick_meal_map[index]["id"],
                        "name": quick_meal_map[index]["name"],
                        "fiber_grams": quick_meal_map[index]["fiber_grams"],
                        "estimated_cost_usd": quick_meal_map[index][
                            "estimated_cost_usd"
                        ],
                    }
                    if index in quick_meal_map
                    else None
                ),
            }
        )

    return {
        "week_of": week_of.isoformat(),
        "season": season,
        "weather_category": weather["category"],
        "weather_note": weather.get("note", ""),
        "heat_friendly_meals": heat_friendly_count,
        "assignments": assignments,
        "meals": meals,
        "estimated_cost_usd": estimated_cost,
        "estimated_shopping_cost_usd": estimated_shopping_cost,
        "average_fiber_grams": average_fiber,
        "average_kid_friendly_score": average_kid_friendly,
        "inventory_coverage_score": inventory["coverage_score"],
        "inventory_savings_usd": inventory["estimated_savings_usd"],
        "inventory_buy": inventory["buy"],
        "inventory_warnings": inventory["warnings"],
        "rotation_score": rotation_score,
        "errors": errors,
        "warnings": warnings,
        "ready_to_commit": not errors,
    }
