from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path

from planner.assignment import constrained_assignments, format_assignment_diagnostics
from planner.constants import DAYS, ROOT
from planner.eligibility import load_recipes, override_constraints, season_for
from planner.scoring import evaluate_proposal
from scripts.recipe_ideas import load_ideas


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


class ProposalGenerationError(ValueError):
    def __init__(self, week_of: dt.date, option_number: int, attempts: list[dict]):
        self.diagnostics = {
            "week_of": week_of.isoformat(),
            "option_number": option_number,
            "attempts": attempts,
        }
        lines = [
            "Unable to build distinct weekly options with the current "
            "day, protein, override, weather, and overlap constraints.",
            "Failure diagnostics:",
        ]
        for attempt in attempts:
            lines.append(f"{attempt['label']}:")
            rendered = format_assignment_diagnostics(attempt)
            lines.append(rendered or "- No detailed diagnostics were produced.")
        super().__init__("\n".join(lines))


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
    active_library = [
        recipe for recipe in recipes.values() if recipe["status"] != "retired"
    ]
    use_generated_ideas = len(active_library) < 7
    previous_options: list[set[str]] = []
    global_usage: collections.Counter[str] = collections.Counter()

    for variant in range(count):
        attempt_diagnostics: list[dict] = []
        if use_generated_ideas:
            proposal_recipes = {
                **ideas,
                **user_ideas,
                **override_recipes,
            }
        else:
            proposal_recipes = {**recipes, **user_ideas, **override_recipes}
        diagnostics: dict = {}
        assignments = constrained_assignments(
            week_of,
            proposal_recipes,
            fixed_assignments,
            previous_options,
            global_usage,
            variant,
            root=root,
            diagnostics=diagnostics,
        )
        if assignments is None:
            diagnostics["label"] = (
                "Generated-idea candidate pool"
                if use_generated_ideas
                else "Canonical-library candidate pool"
            )
            attempt_diagnostics.append(diagnostics)
        if assignments is None and not use_generated_ideas:
            proposal_recipes = {
                **recipes,
                **ideas,
                **user_ideas,
                **override_recipes,
            }
            diagnostics = {}
            assignments = constrained_assignments(
                week_of,
                proposal_recipes,
                fixed_assignments,
                previous_options,
                global_usage,
                variant,
                root=root,
                diagnostics=diagnostics,
            )
            if assignments is None:
                diagnostics["label"] = "Expanded pool with generated ideas"
                attempt_diagnostics.append(diagnostics)
        if assignments is None:
            raise ProposalGenerationError(
                week_of,
                variant + 1,
                attempt_diagnostics,
            )
        proposals.append(
            evaluate_proposal(week_of, assignments, proposal_recipes, root=root)
        )
        previous_options.append(
            set(assignments) - set(fixed_assignments.values())
        )
        global_usage.update(assignments)

    return proposals
