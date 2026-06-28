from __future__ import annotations

import collections

from planner.constants import MAX_PROTEIN_PER_WEEK


def validate_planned_diners(
    planned_diners: list[int] | None,
) -> list[int]:
    values = list(planned_diners or [4] * 7)
    if (
        len(values) != 7
        or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= 20
            for value in values
        )
    ):
        raise ValueError(
            "planned_diners must contain seven integers from 1 to 20"
        )
    return values


def scale_requirements(
    requirements: list[dict],
    factor: float,
) -> list[dict]:
    return [
        {
            **requirement,
            "quantity": round(
                float(requirement["quantity"]) * factor,
                3,
            ),
        }
        for requirement in requirements
    ]


def scale_recipe_for_diners(recipe: dict, diners: int) -> dict:
    servings = int(recipe.get("servings", 4))
    factor = diners / servings
    return {
        **recipe,
        "estimated_cost_usd": round(
            float(recipe["estimated_cost_usd"]) * factor,
            2,
        ),
        "inventory_requirements": scale_requirements(
            recipe.get("inventory_requirements", []),
            factor,
        ),
    }


def scale_sides_for_diners(
    sides: list[dict],
    diners: int,
) -> list[dict]:
    factor = diners / 4
    return [
        {
            **side,
            "estimated_cost_usd": round(
                float(side["estimated_cost_usd"]) * factor,
                2,
            ),
            "requirements": scale_requirements(
                side.get("requirements", []),
                factor,
            ),
        }
        for side in sides
    ]


def estimated_menu_cost(
    scored_meals: list[dict],
    side_map: dict[str, list[dict]],
    quick_meal_map: dict[int, dict],
) -> float:
    return round(
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


def average_fiber_grams(
    scored_meals: list[dict],
    side_map: dict[str, list[dict]],
) -> float:
    if not scored_meals:
        return 0.0
    return round(
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


def average_kid_friendly_score(
    scored_entries: list[tuple[int, dict]],
    quick_meal_map: dict[int, dict],
) -> float:
    if not scored_entries:
        return 0.0
    return round(
        sum(
            float(quick_meal_map.get(index, recipe)["kid_friendly_score"])
            for index, recipe in scored_entries
        )
        / len(scored_entries),
        1,
    )


def collect_inventory_requirements(
    scored_meals: list[dict],
    side_map: dict[str, list[dict]],
    quick_meal_map: dict[int, dict],
) -> list[dict]:
    requirements = [
        requirement
        for recipe in scored_meals
        for requirement in recipe.get("inventory_requirements", [])
    ]
    requirements.extend(
        requirement
        for suggestions in side_map.values()
        for side in suggestions
        for requirement in side.get("requirements", [])
    )
    requirements.extend(
        requirement
        for quick_meal in quick_meal_map.values()
        for requirement in quick_meal.get("requirements", [])
    )
    return requirements


def estimated_shopping_cost(
    estimated_cost: float,
    estimated_savings: float,
) -> float:
    return round(max(0.0, estimated_cost - estimated_savings), 2)


def recipe_rotation_score(
    assignments: list[str],
    scored_meals: list[dict],
    recent_repeats: list[str],
) -> int:
    repeated = collections.Counter(assignments)
    score = 100
    score -= sum((count - 1) * 12 for count in repeated.values())
    score -= len(recent_repeats) * 10
    method_counts = collections.Counter(
        recipe["cooking_method"] for recipe in scored_meals
    )
    protein_counts = collections.Counter(
        recipe["protein"] for recipe in scored_meals
    )
    score -= sum(max(0, count - 3) * 3 for count in method_counts.values())
    score -= sum(
        max(0, count - MAX_PROTEIN_PER_WEEK) * 3
        for count in protein_counts.values()
    )
    return max(0, score)
