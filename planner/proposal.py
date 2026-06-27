from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path

from planner.assignment import constrained_assignments, format_assignment_diagnostics
from planner.constants import DAYS, ROOT
from planner.eligibility import load_recipes, override_constraints, season_for
from planner.scoring import evaluate_proposal
from scripts.generated_idea_pools import load_generated_idea_pools
from scripts.recipe_ideas import load_ideas


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


def generated_ideas(
    week_of: dt.date,
    root: Path = ROOT,
) -> dict[str, dict]:
    ideas: dict[str, dict] = {}
    pools = load_generated_idea_pools(root)
    for day_index, day in enumerate(DAYS):
        for entry in pools[day]:
            name = entry["name"]
            protein = entry["protein"]
            method = entry["cooking_method"]
            idea_id = (
                f"IDEA-{week_of.strftime('%Y%m%d')}-{day[:3].upper()}-"
                f"{entry['slot']}"
            )
            inventory_requirements = idea_inventory_requirements(name, protein)
            ideas[idea_id] = {
                "id": idea_id,
                "name": name,
                "revision": 0,
                "status": "proposed",
                "protein": protein,
                "meal_scope": "complete-meal",
                "fiber_grams": entry["fiber_grams"],
                "estimated_cost_usd": entry["estimated_cost_usd"],
                "kid_friendly_score": entry["kid_friendly_score"],
                "kid_friendly_reason": entry["kid_friendly_reason"],
                "cooking_method": method,
                "cook_time_minutes": 240 if method == "slow-cooker" else 30,
                "seasons": [season_for(week_of)],
                "leftover_recipe_ids": [],
                "tags": [
                    season_for(week_of),
                    protein,
                    method,
                    *entry["tags"],
                ],
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
    ideas = generated_ideas(week_of, root)
    user_ideas = user_idea_recipes(week_of, root)
    fixed_assignments, override_recipes = override_constraints(week_of, root)
    season = season_for(week_of)
    proposals: list[dict] = []
    active_library = [
        recipe for recipe in recipes.values() if recipe["status"] != "retired"
    ]
    supplement_with_generated_ideas = len(active_library) < 7
    previous_options: list[set[str]] = []
    global_usage: collections.Counter[str] = collections.Counter()

    for variant in range(count):
        attempt_diagnostics: list[dict] = []
        if supplement_with_generated_ideas:
            proposal_recipes = {
                **recipes,
                **ideas,
                **user_ideas,
                **override_recipes,
            }
        else:
            proposal_recipes = {**recipes, **user_ideas, **override_recipes}
        diagnostics: dict = {}
        planning_trace: dict = {}
        assignments = constrained_assignments(
            week_of,
            proposal_recipes,
            fixed_assignments,
            previous_options,
            global_usage,
            variant,
            root=root,
            diagnostics=diagnostics,
            trace=planning_trace,
        )
        if assignments is None:
            diagnostics["label"] = (
                "Canonical library supplemented with generated ideas"
                if supplement_with_generated_ideas
                else "Canonical-library candidate pool"
            )
            attempt_diagnostics.append(diagnostics)
        if assignments is None and not supplement_with_generated_ideas:
            proposal_recipes = {
                **recipes,
                **ideas,
                **user_ideas,
                **override_recipes,
            }
            diagnostics = {}
            planning_trace = {}
            assignments = constrained_assignments(
                week_of,
                proposal_recipes,
                fixed_assignments,
                previous_options,
                global_usage,
                variant,
                root=root,
                diagnostics=diagnostics,
                trace=planning_trace,
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
        proposal = evaluate_proposal(
            week_of,
            assignments,
            proposal_recipes,
            root=root,
        )
        planning_trace["rejected_proposal_attempts"] = len(
            attempt_diagnostics
        )
        if supplement_with_generated_ideas:
            planning_trace.setdefault("rules_used", []).append(
                "RULE-GENERATED-SUPPLEMENT"
            )
        proposal["planning_trace"] = planning_trace
        proposal["explainability_score"] = planning_trace[
            "explainability"
        ]["score"]
        proposals.append(proposal)
        previous_options.append(
            set(assignments) - set(fixed_assignments.values())
        )
        global_usage.update(assignments)

    return proposals
