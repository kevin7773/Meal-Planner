from __future__ import annotations

import collections
import datetime as dt
import re
from pathlib import Path

from planner.constants import DAYS, LOW_EFFORT_METHODS, MAX_PROTEIN_PER_WEEK, ROOT
from planner.eligibility import override_constraints, recent_recipe_ids, season_for
from planner.explanations import (
    expiring_refrigerated_items,
    selection_explanation,
)
from planner.metrics import (
    average_fiber_grams,
    average_kid_friendly_score,
    collect_inventory_requirements,
    estimated_menu_cost,
    estimated_shopping_cost as calculate_shopping_cost,
    recipe_rotation_score,
)
from planner.quick_meal_planning import (
    plan_quick_meals,
    public_quick_meal,
    quick_meal_requirements,
)
from planner.side_planning import (
    plan_side_suggestions,
    public_side_suggestions,
    side_requirements,
)
from scripts.inventory import assess_inventory
from scripts.quick_meals import PARENTS_ONLY_REASON
from scripts.weather_context import is_heat_friendly, load_weather_context, load_weather_rules


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
    side_map = plan_side_suggestions(
        scored_meals,
        season=season,
        week_of=week_of,
        root=root,
    )
    quick_meal_map = plan_quick_meals(
        scored_entries,
        week_of=week_of,
        root=root,
    )
    estimated_cost = estimated_menu_cost(
        scored_meals,
        side_map,
        quick_meal_map,
    )
    average_fiber = average_fiber_grams(scored_meals, side_map)
    average_kid_friendly = average_kid_friendly_score(
        scored_entries,
        quick_meal_map,
    )
    inventory_requirements = collect_inventory_requirements(
        scored_meals,
        side_map,
        quick_meal_map,
    )
    inventory = assess_inventory(
        inventory_requirements,
        root=root,
        week_of=week_of,
    )
    estimated_shopping_cost = calculate_shopping_cost(
        estimated_cost,
        inventory["estimated_savings_usd"],
    )

    rotation_score = recipe_rotation_score(
        assignments,
        scored_meals,
        recent_repeats,
    )

    meals = []
    for index, recipe in enumerate(selected):
        meal_requirements = list(recipe.get("inventory_requirements", []))
        meal_requirements.extend(side_requirements(side_map.get(recipe["id"], [])))
        meal_requirements.extend(
            quick_meal_requirements(quick_meal_map.get(index))
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
                "cook_time_minutes": recipe.get("cook_time_minutes", 0),
                "fiber_grams": recipe["fiber_grams"],
                "estimated_cost_usd": recipe["estimated_cost_usd"],
                "kid_friendly_score": recipe["kid_friendly_score"],
                "kid_friendly_reason": recipe["kid_friendly_reason"],
                "meal_scope": recipe.get("meal_scope", "complete-meal"),
                "selection_explanation": explanation,
                "side_suggestions": public_side_suggestions(
                    side_map.get(recipe["id"], [])
                ),
                "kids_quick_meal": public_quick_meal(
                    quick_meal_map.get(index)
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
