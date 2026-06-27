from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from scripts.validate_recipes import split_recipe
    from scripts.inventory import assess_inventory, load_inventory
    from scripts.recipe_ideas import load_ideas
    from scripts.menu_status import split_menu
    from scripts.side_dishes import suggest_sides
    from scripts.quick_meals import PARENTS_ONLY_REASON, suggest_quick_meal
except ModuleNotFoundError:
    from validate_recipes import split_recipe
    from inventory import assess_inventory, load_inventory
    from recipe_ideas import load_ideas
    from menu_status import split_menu
    from side_dishes import suggest_sides
    from quick_meals import PARENTS_ONLY_REASON, suggest_quick_meal


ROOT = Path(__file__).resolve().parents[1]
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
LOW_EFFORT_METHODS = {"slow-cooker", "minimal-cook", "no-cook"}
MAX_PROTEIN_PER_WEEK = 3
MAX_OPTION_OVERLAP = 2
MAX_USER_IDEAS_PER_WEEK = 2
IDEA_POOLS = {
    "Monday": [
        ("Chicken and Cheese Quesadillas with Pinto Beans", "chicken", "blackstone", 12, 22.0, ["mexican-monday"], "Familiar cheesy quesadillas with beans and toppings served separately"),
        ("Mild Turkey Taco Brown Rice Bowls", "turkey", "blackstone", 13, 23.0, ["mexican-monday"], "Familiar taco flavors in a build-your-own bowl"),
        ("Blackstone Chicken Fajita Soft Tacos", "chicken", "blackstone", 12, 24.0, ["mexican-monday"], "Familiar soft tacos with mild seasoning and optional vegetables"),
    ],
    "Tuesday": [
        ("Slow-Cooker BBQ Chicken Baked Potato Bar", "chicken", "slow-cooker", 11, 22.0, [], "Familiar barbecue chicken with customizable potato toppings"),
        ("Slow-Cooker Mild Salsa Chicken Quesadillas", "chicken", "slow-cooker", 12, 21.0, [], "Cheesy quesadillas with mild chicken filling and salsa on the side"),
        ("Slow-Cooker Turkey Sloppy Joe Sliders", "turkey", "slow-cooker", 10, 22.0, [], "Familiar sweet-savory sliders with vegetables blended into the sauce"),
    ],
    "Wednesday": [
        ("Blackstone Chicken Fried Brown Rice", "chicken", "blackstone", 9, 22.0, [], "Familiar fried rice with mild seasoning and vegetables cut small"),
        ("Turkey Cheesesteak Brown Rice Bowls", "turkey", "blackstone", 10, 23.0, [], "Cheesy turkey bowl with peppers served separately when preferred"),
        ("Grilled Chicken Pizza Pitas", "chicken", "grill", 9, 22.0, [], "Personal pizza format with familiar cheese and customizable toppings"),
    ],
    "Thursday": [
        ("No-Cook Turkey and Cheese Sandwich Bar", "turkey", "no-cook", 9, 20.0, [], "Familiar sandwiches assembled individually with fruit and vegetables on the side"),
        ("Rotisserie Chicken Corn Rice Bowls", "chicken", "minimal-cook", 10, 21.0, [], "Build-your-own bowl with familiar chicken, rice, corn, and cheese"),
        ("No-Cook Chicken and Cheese Roll-Up Plates", "chicken", "no-cook", 9, 20.0, [], "Snack-plate format with simple roll-ups, whole-grain crackers, and fruit"),
    ],
    "Friday": [
        ("Blackstone Hibachi Chicken Fried Rice", "chicken", "blackstone", 10, 24.0, [], "Familiar chicken and fried rice with sauce served on the side"),
        ("Grilled Turkey Cheeseburgers with Corn", "turkey", "grill", 9, 23.0, [], "Classic cheeseburger format using turkey with familiar sides"),
        ("Grilled Salmon with Brown Rice and Green Beans", "seafood", "grill", 9, 29.0, [], "Established family-favorite salmon with simple familiar sides"),
    ],
    "Saturday": [
        ("Blackstone Breakfast for Dinner", "turkey", "blackstone", 9, 22.0, [], "Familiar pancakes, eggs, fruit, and turkey sausage served separately"),
        ("Chicken Cheesesteak Baked Potatoes", "chicken", "blackstone", 10, 23.0, [], "Cheesy chicken and baked potatoes with vegetables optional"),
        ("Turkey Smash Burgers with Sweet Potato Wedges", "turkey", "blackstone", 10, 24.0, [], "Crispy-edged cheeseburgers with a familiar finger-food side"),
    ],
    "Sunday": [
        ("Grilled BBQ Chicken Corn Rice Bowls", "chicken", "grill", 11, 23.0, [], "Build-your-own bowl with familiar barbecue chicken, rice, corn, and cheese"),
        ("Chicken Parmesan Meatball Subs", "chicken", "grill", 9, 24.0, [], "Familiar meatball sub with mild tomato sauce and melted cheese"),
        ("Grilled Salmon Rice Bowls with Fruit", "seafood", "grill", 9, 29.0, [], "Established family-favorite salmon with simple rice and fruit"),
    ],
}


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


def generated_ideas(week_of: dt.date) -> dict[str, dict]:
    ideas: dict[str, dict] = {}
    strongest_kid_formats = (
        "quesadilla",
        "slider",
        "pizza",
        "sandwich",
        "cheeseburger",
        "smash burger",
        "breakfast for dinner",
        "meatball sub",
        "soft taco",
        "salmon",
        "roll-up",
    )
    for day_index, day in enumerate(DAYS):
        for option_index, (
            name,
            protein,
            method,
            fiber,
            cost,
            extra_tags,
            kid_reason,
        ) in enumerate(
            IDEA_POOLS[day],
            start=1,
        ):
            idea_id = f"IDEA-{week_of.strftime('%Y%m%d')}-{day[:3].upper()}-{option_index}"
            kid_score = (
                5
                if any(term in name.lower() for term in strongest_kid_formats)
                else 4
            )
            inventory_requirements = idea_inventory_requirements(name, protein)
            ideas[idea_id] = {
                "id": idea_id,
                "name": name,
                "revision": 0,
                "status": "proposed",
                "protein": protein,
                "meal_scope": "complete-meal",
                "fiber_grams": fiber,
                "estimated_cost_usd": cost,
                "kid_friendly_score": kid_score,
                "kid_friendly_reason": kid_reason,
                "cooking_method": method,
                "cook_time_minutes": 240 if method == "slow-cooker" else 30,
                "seasons": [season_for(week_of)],
                "leftover_recipe_ids": [],
                "tags": [season_for(week_of), protein, method, *extra_tags],
                "source": "generated-idea",
                "filename": None,
                "inventory_requirements": inventory_requirements,
                "day": day,
                "day_index": day_index,
            }
    return ideas


def user_idea_recipes(week_of: dt.date, root: Path = ROOT) -> dict[str, dict]:
    try:
        document = load_ideas(root)
    except (OSError, json.JSONDecodeError):
        return {}
    recipes: dict[str, dict] = {}
    season = season_for(week_of)
    for idea in document.get("ideas", []):
        if idea.get("status") != "queued" or season not in idea.get("seasons", []):
            continue
        recipes[idea["id"]] = {
            "id": idea["id"],
            "name": idea["name"],
            "revision": 0,
            "status": "proposed",
            "protein": idea["protein"],
            "meal_scope": idea.get("meal_scope", "complete-meal"),
            "fiber_grams": idea["fiber_grams"],
            "estimated_cost_usd": idea["estimated_cost_usd"],
            "kid_friendly_score": idea["kid_friendly_score"],
            "kid_friendly_reason": idea["kid_friendly_reason"],
            "cooking_method": idea["cooking_method"],
            "cook_time_minutes": 240 if idea["cooking_method"] == "slow-cooker" else 30,
            "seasons": idea["seasons"],
            "leftover_recipe_ids": [],
            "tags": idea["tags"],
            "source": "user-idea",
            "filename": None,
            "inventory_requirements": idea_inventory_requirements(
                idea["idea"],
                idea["protein"],
            ),
        }
    return recipes


def idea_inventory_requirements(name: str, protein: str) -> list[dict]:
    lowered = name.lower()
    requirements: collections.Counter[str] = collections.Counter()
    if protein == "chicken":
        if "rotisserie" in lowered:
            requirements["rotisserie-chicken"] += 3
        else:
            requirements["chicken-breast"] += 1.5
    elif protein == "turkey":
        requirements["ground-turkey"] += 1.5
    elif protein == "seafood":
        requirements["salmon"] += 1.5

    if "rice" in lowered:
        requirements["brown-rice"] += 1.5
    if any(word in lowered for word in ("quesadilla", "taco", "roll-up")):
        requirements["whole-wheat-tortilla"] += 8
    if "slider" in lowered:
        requirements["slider-bun"] += 8
    if "pinto" in lowered:
        requirements["pinto-beans"] += 1
    if "corn" in lowered:
        requirements["frozen-corn"] += 1
    if "potato" in lowered:
        requirements["russet-potato"] += 4
    if any(word in lowered for word in ("cheese", "pizza", "cheeseburger")):
        requirements["cheddar"] += 4
    requirements["kosher-salt"] += 1
    requirements["black-pepper"] += 1
    requirements["garlic-powder"] += 1
    return [
        {"item_id": item_id, "quantity": quantity}
        for item_id, quantity in sorted(requirements.items())
    ]


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


def constrained_assignments(
    week_of: dt.date,
    recipes: dict[str, dict],
    fixed_assignments: dict[str, str],
    previous_options: list[set[str]],
    global_usage: collections.Counter[str],
    variant: int,
    *,
    root: Path,
) -> list[str] | None:
    season = season_for(week_of)
    pools = {
        day: eligible_recipes(recipes, day, season)
        for day in DAYS
        if day not in fixed_assignments
    }
    if any(not pool for pool in pools.values()):
        return None

    assignments: dict[str, str] = dict(fixed_assignments)
    used_ids = set(fixed_assignments.values())
    protein_counts: collections.Counter[str] = collections.Counter()
    user_idea_count = 0
    for recipe_id in fixed_assignments.values():
        recipe = recipes.get(recipe_id)
        if recipe is None:
            return None
        protein_counts[recipe["protein"]] += 1
        user_idea_count += recipe.get("source") == "user-idea"
    if any(count > MAX_PROTEIN_PER_WEEK for count in protein_counts.values()):
        return None

    overlap_counts = [
        len(used_ids & previous)
        for previous in previous_options
    ]
    if any(count > MAX_OPTION_OVERLAP for count in overlap_counts):
        return None

    search_days = sorted(
        pools,
        key=lambda day: (len(pools[day]), DAYS.index(day)),
    )

    def candidate_key(recipe: dict) -> tuple:
        source_rank = (
            0
            if recipe.get("source") == "user-idea"
            else 1
            if recipe.get("status") == "candidate"
            else 2
        )
        rotation = (
            sum(ord(character) for character in recipe["id"]) + variant
        ) % max(1, len(recipes))
        return (
            global_usage[recipe["id"]],
            source_rank,
            protein_counts[recipe["protein"]],
            -inventory_match_score(recipe, week_of, root),
            rotation,
            recipe["id"],
        )

    def search(position: int, idea_count: int) -> bool:
        if position == len(search_days):
            return True
        day = search_days[position]
        for recipe in sorted(pools[day], key=candidate_key):
            recipe_id = recipe["id"]
            protein = recipe["protein"]
            is_user_idea = recipe.get("source") == "user-idea"
            if recipe_id in used_ids:
                continue
            if protein_counts[protein] >= MAX_PROTEIN_PER_WEEK:
                continue
            if is_user_idea and idea_count >= MAX_USER_IDEAS_PER_WEEK:
                continue
            next_overlaps = [
                overlap_counts[index] + int(recipe_id in previous)
                for index, previous in enumerate(previous_options)
            ]
            if any(count > MAX_OPTION_OVERLAP for count in next_overlaps):
                continue

            assignments[day] = recipe_id
            used_ids.add(recipe_id)
            protein_counts[protein] += 1
            old_overlaps = overlap_counts[:]
            overlap_counts[:] = next_overlaps
            if search(position + 1, idea_count + int(is_user_idea)):
                return True
            overlap_counts[:] = old_overlaps
            protein_counts[protein] -= 1
            used_ids.remove(recipe_id)
            del assignments[day]
        return False

    if not search(0, user_idea_count):
        return None
    return [assignments[day] for day in DAYS]


def generate_proposals(
    week_of: dt.date,
    count: int = 3,
    *,
    root: Path = ROOT,
) -> list[dict]:
    if week_of.weekday() != 0:
        raise ValueError("week_of must be a Monday")
    recipes = load_recipes(root)
    ideas = generated_ideas(week_of)
    user_ideas = user_idea_recipes(week_of, root)
    fixed_assignments, override_recipes = override_constraints(week_of, root)
    season = season_for(week_of)
    proposals: list[dict] = []
    active_library = [recipe for recipe in recipes.values() if recipe["status"] != "retired"]
    use_generated_ideas = len(active_library) < 7
    previous_options: list[set[str]] = []
    global_usage: collections.Counter[str] = collections.Counter()

    for variant in range(count):
        if use_generated_ideas:
            proposal_recipes = {
                **ideas,
                **user_ideas,
                **override_recipes,
            }
        else:
            proposal_recipes = {**recipes, **user_ideas, **override_recipes}
        assignments = constrained_assignments(
            week_of,
            proposal_recipes,
            fixed_assignments,
            previous_options,
            global_usage,
            variant,
            root=root,
        )
        if assignments is None and not use_generated_ideas:
            proposal_recipes = {
                **recipes,
                **ideas,
                **user_ideas,
                **override_recipes,
            }
            assignments = constrained_assignments(
                week_of,
                proposal_recipes,
                fixed_assignments,
                previous_options,
                global_usage,
                variant,
                root=root,
            )
        if assignments is None:
            raise ValueError(
                "Unable to build distinct weekly options with the current "
                "day, protein, override, and overlap constraints."
            )
        proposals.append(
            evaluate_proposal(week_of, assignments, proposal_recipes, root=root)
        )
        previous_options.append(set(assignments))
        global_usage.update(assignments)

    return proposals


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
        is_override = recipe.get("status") == "override"
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


def proposal_report(proposal: dict, number: int | None = None) -> str:
    title = f"Option {number}" if number is not None else "Dry Run"
    lines = [
        title,
        f"Week of: {proposal['week_of']}",
        f"Estimated cost: ${proposal['estimated_cost_usd']:.2f}",
        f"After inventory: ${proposal['estimated_shopping_cost_usd']:.2f}",
        f"Inventory coverage: {proposal['inventory_coverage_score']}/100",
        f"Average fiber: {proposal['average_fiber_grams']:.1f} g/serving",
        f"Kid-friendly score: {proposal['average_kid_friendly_score']:.1f}/5",
        f"Recipe rotation score: {proposal['rotation_score']}/100",
        "",
    ]
    for meal in proposal["meals"]:
        lines.append(
            f"{meal['day']}: {meal['recipe_id']} rev {meal['revision']} - "
            f"{meal['name']} [{meal['cooking_method']}]"
        )
        lines.append(f"  Kid-friendly: {meal['kid_friendly_reason']}")
        if meal["side_suggestions"]:
            lines.append(
                "  Suggested sides: "
                + "; ".join(
                    f"{side['name']} ({side['fiber_grams']}g fiber)"
                    for side in meal["side_suggestions"]
                )
            )
        if meal["kids_quick_meal"]:
            quick_meal = meal["kids_quick_meal"]
            lines.append(
                f"  Kids' quick meal: {quick_meal['name']} "
                f"({quick_meal['id']}, ${quick_meal['estimated_cost_usd']:.2f})"
            )
    if proposal["errors"]:
        lines.extend(["", "BLOCKING ERRORS"])
        lines.extend(f"- {error}" for error in proposal["errors"])
    if proposal["warnings"]:
        lines.extend(["", "WARNINGS"])
        lines.extend(f"- {warning}" for warning in proposal["warnings"])
    if proposal["inventory_warnings"]:
        lines.extend(["", "INVENTORY WARNINGS"])
        lines.extend(f"- {warning}" for warning in proposal["inventory_warnings"])
    lines.extend(["", "No files were written."])
    return "\n".join(lines)


def apply_proposal(
    proposal: dict,
    *,
    actor: str,
    accept_warnings: bool = False,
    root: Path = ROOT,
    now: dt.datetime | None = None,
) -> Path:
    if proposal["errors"]:
        raise ValueError(
            "Cannot commit a proposal with blocking errors: "
            + "; ".join(proposal["errors"])
        )
    if proposal["warnings"] and not accept_warnings:
        raise ValueError("Proposal has warnings; explicit acceptance is required.")
    actor = re.sub(r"\s+", " ", actor.replace("|", "/")).strip()
    if not actor:
        raise ValueError("actor is required")

    week_of = dt.date.fromisoformat(proposal["week_of"])
    output = root / "menus" / str(week_of.year) / f"{week_of.isoformat()}.md"
    replacing_reopened_draft = False
    if output.exists():
        metadata, _ = split_menu(output)
        replacing_reopened_draft = (
            metadata.get("status") == "draft"
            and metadata.get("rebuild_pending") is True
        )
        if not replacing_reopened_draft:
            raise FileExistsError(f"Weekly menu already exists: {output}")
    timestamp = (now or dt.datetime.now(dt.timezone.utc)).astimezone(
        dt.timezone.utc
    ).isoformat(timespec="seconds").replace("+00:00", "Z")

    lines = [
        "+++",
        f'week_of = "{week_of.isoformat()}"',
        'status = "draft"',
        f'status_updated_at = "{timestamp}"',
        "+++",
        "",
        "# Weekly Dinner Menu",
        "",
        f"**Week of:** {week_of.isoformat()}  ",
        "**Family Size:** 4  ",
        f"**Season:** {proposal['season'].title()}",
        "",
    ]
    for meal in proposal["meals"]:
        meal_date = dt.date.fromisoformat(meal["date"])
        lines.extend(
            [
                f"## {meal['day']}, {meal_date.strftime('%B %d')} - {meal['name']}",
                "",
                f"**Recipe:** {meal['recipe_id']} rev {meal['revision']} ({meal['status']})  ",
                f"**Estimated Fiber:** {meal['fiber_grams']} grams per serving  ",
                f"**Estimated Cost:** ${float(meal['estimated_cost_usd']):.2f}  ",
                f"**Kid-Friendly Design:** {meal['kid_friendly_reason']}  ",
                f"**Cooking Method:** {meal['cooking_method']}",
                (
                    "**Suggested Sides:** "
                    + "; ".join(
                        f"{side['name']} ({side['id']})"
                        for side in meal["side_suggestions"]
                    )
                    if meal["side_suggestions"]
                    else "**Suggested Sides:** None; recipe is a complete meal"
                ),
                (
                    f"**Kids' Quick Meal:** {meal['kids_quick_meal']['name']} "
                    f"({meal['kids_quick_meal']['id']}, "
                    f"${float(meal['kids_quick_meal']['estimated_cost_usd']):.2f})"
                    if meal["kids_quick_meal"]
                    else "**Kids' Quick Meal:** Not needed"
                ),
                "",
                (
                    f"Canonical recipe: `recipes/{load_recipes(root)[meal['recipe_id']]['filename']}`"
                    if meal["recipe_id"].startswith("FDP-")
                    else "Fixed meal override from the weekly override record."
                    if meal["status"] == "override"
                    else "Proposed recipe idea: create a full FDP candidate before generated status."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Dry Run Summary",
            "",
            f"- Estimated weekly cost: ${proposal['estimated_cost_usd']:.2f}",
            f"- Estimated shopping cost after inventory: ${proposal['estimated_shopping_cost_usd']:.2f}",
            f"- Inventory coverage score: {proposal['inventory_coverage_score']}/100",
            f"- Estimated inventory savings: ${proposal['inventory_savings_usd']:.2f}",
            f"- Average fiber: {proposal['average_fiber_grams']:.1f} grams per serving",
            f"- Average kid-friendly score: {proposal['average_kid_friendly_score']:.1f}/5",
            f"- Recipe rotation score: {proposal['rotation_score']}/100",
            "- Accepted warnings: " + ("; ".join(proposal["warnings"]) or "None"),
            "",
            "## Planning Status History",
            "",
            "| Status | Timestamp | Actor | Note |",
            "| --- | --- | --- | --- |",
            (
                f"| draft | {timestamp} | {actor} | "
                + (
                    "Selected replacement from dry-run comparison"
                    if replacing_reopened_draft
                    else "Selected from dry-run comparison"
                )
                + " |"
            ),
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return output


def commit_assignments(
    week_of: dt.date,
    assignments: list[str],
    *,
    actor: str,
    accept_warnings: bool = False,
    root: Path = ROOT,
    now: dt.datetime | None = None,
) -> Path:
    _, override_recipes = override_constraints(week_of, root)
    recipe_universe = {
        **load_recipes(root),
        **generated_ideas(week_of),
        **user_idea_recipes(week_of, root),
        **override_recipes,
    }
    proposal = evaluate_proposal(
        week_of,
        assignments,
        recipe_universe,
        root=root,
    )
    return apply_proposal(
        proposal,
        actor=actor,
        accept_warnings=accept_warnings,
        root=root,
        now=now,
    )


def parse_week(value: str) -> dt.date:
    parsed = dt.date.fromisoformat(value)
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("week must be a Monday")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan weekly menus without side effects.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--week", required=True, type=parse_week)
    generate_parser.add_argument("--count", type=int, default=3)
    generate_parser.add_argument("--json", action="store_true")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--week", required=True, type=parse_week)
    apply_parser.add_argument("--recipes", required=True)
    apply_parser.add_argument("--actor", required=True)
    apply_parser.add_argument("--accept-warnings", action="store_true")

    args = parser.parse_args()
    if args.command == "generate":
        proposals = generate_proposals(args.week, args.count)
        if args.json:
            print(json.dumps(proposals, indent=2))
        else:
            print("\n\n".join(
                proposal_report(proposal, index)
                for index, proposal in enumerate(proposals, start=1)
            ))
        return 0

    assignments = [value.strip() for value in args.recipes.split(",") if value.strip()]
    try:
        output = commit_assignments(
            args.week,
            assignments,
            actor=args.actor,
            accept_warnings=args.accept_warnings,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"Unable to commit dry run: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
