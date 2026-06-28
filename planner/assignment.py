from __future__ import annotations

import collections
import datetime as dt
from pathlib import Path

from planner.constants import (
    DAYS,
    MAX_OPTION_OVERLAP,
    MAX_PROTEIN_PER_WEEK,
    MAX_USER_IDEAS_PER_WEEK,
)
from planner.eligibility import (
    inventory_match_score,
    recent_recipe_ids,
    season_for,
)
from planner.explainability import explain_planning_trace
from planner.tracing import (
    TRACE_VERSION,
    dynamic_decision_trace,
    fixed_day_trace,
    static_day_trace,
)
from scripts.weather_context import is_heat_friendly, load_weather_context, load_weather_rules


def _failure_diagnostics(
    *,
    day_stats: list[dict],
    rejections: dict[str, dict[str, set[str]]],
    recipes: dict[str, dict],
    minimum_heat_friendly: int,
    heat_bound_failed: bool,
    extra_messages: list[str] | None = None,
) -> dict:
    messages = list(extra_messages or [])
    for stats in day_stats:
        if stats["eligible_count"] == 0:
            if (
                stats["day_rule_eligible_count"] > 0
                and stats["weather_excluded_count"]
                == stats["day_rule_eligible_count"]
            ):
                messages.append(
                    f"{stats['day']} failed: 0 eligible recipes after weather "
                    f"exclusions ({stats['weather_excluded_count']} excluded)."
                )
            else:
                rule = (
                    "Mexican Monday"
                    if stats["day"] == "Monday"
                    else "low-effort"
                    if stats["day"] in {"Tuesday", "Thursday"}
                    else "day"
                )
                messages.append(
                    f"{stats['day']} failed: 0 recipes satisfy the {rule}, "
                    "season, and status requirements."
                )
        elif stats["recent_count"] == stats["eligible_count"]:
            noun = "Mexican recipes" if stats["day"] == "Monday" else "recipes"
            quantifier = "both" if stats["eligible_count"] == 2 else "all"
            messages.append(
                f"{stats['day']} context: {stats['eligible_count']} eligible "
                f"{noun}, {quantifier} recently used; rotation is a scoring "
                "preference, not a hard exclusion."
            )

    elimination_details = []
    for reason, by_day in rejections.items():
        recipe_ids = sorted(
            {
                recipe_id
                for rejected_ids in by_day.values()
                for recipe_id in rejected_ids
            }
        )
        if not recipe_ids:
            continue
        detail = {
            "reason": reason,
            "count": len(recipe_ids),
            "recipe_ids": recipe_ids,
            "by_day": {
                day: sorted(rejected_ids)
                for day, rejected_ids in by_day.items()
                if rejected_ids
            },
        }
        elimination_details.append(detail)
        if reason == "protein_cap":
            by_protein: collections.Counter[str] = collections.Counter(
                recipes[recipe_id]["protein"]
                for recipe_id in recipe_ids
                if recipe_id in recipes
            )
            detail["by_protein"] = dict(sorted(by_protein.items()))
            for protein, count in sorted(by_protein.items()):
                messages.append(
                    f"Protein cap eliminated {count} {protein} "
                    f"recipe{'s' if count != 1 else ''} during assignment search."
                )
        elif reason == "option_overlap":
            messages.append(
                f"Option-overlap limit eliminated {len(recipe_ids)} distinct "
                "recipes during assignment search."
            )
        elif reason == "duplicate_recipe":
            messages.append(
                f"Within-week uniqueness eliminated {len(recipe_ids)} distinct "
                "recipes during assignment search."
            )
        elif reason == "user_idea_cap":
            messages.append(
                f"Queued-idea cap eliminated {len(recipe_ids)} distinct ideas "
                "during assignment search."
            )

    if heat_bound_failed:
        messages.append(
            "Heat-friendly minimum could not be reached with the remaining "
            f"days (required: {minimum_heat_friendly})."
        )
    if not messages:
        messages.append(
            "Assignment search exhausted every candidate combination without "
            "satisfying all constraints."
        )
    return {
        "messages": list(dict.fromkeys(messages)),
        "days": day_stats,
        "eliminations": elimination_details,
        "minimum_heat_friendly_meals": minimum_heat_friendly,
    }


def format_assignment_diagnostics(diagnostics: dict) -> str:
    return "\n".join(f"- {message}" for message in diagnostics.get("messages", []))


def constrained_assignments(
    week_of: dt.date,
    recipes: dict[str, dict],
    fixed_assignments: dict[str, str],
    previous_options: list[set[str]],
    global_usage: collections.Counter[str],
    variant: int,
    *,
    root: Path,
    diagnostics: dict | None = None,
    trace: dict | None = None,
    weather_context_override: dict | None = None,
    weather_rules_override: dict | None = None,
    recent_ids_override: set[str] | None = None,
    inventory_scores_override: dict[str, int] | None = None,
    explain_trace: bool = True,
    max_search_evaluations: int | None = None,
) -> list[str] | None:
    if diagnostics is not None:
        diagnostics.clear()
    if trace is not None:
        trace.clear()
    season = season_for(week_of)
    recent_ids = (
        recent_ids_override
        if recent_ids_override is not None
        else recent_recipe_ids(root)
    )
    weather = weather_context_override or load_weather_context(week_of, root)
    weather_rules = weather_rules_override or load_weather_rules(root)
    category_rule = weather_rules["categories"][weather["category"]]
    excluded_tags = set(category_rule["exclude_tags"])
    minimum_heat_friendly = category_rule["minimum_heat_friendly_meals"]
    pools: dict[str, list[dict]] = {}
    static_traces: dict[str, dict] = {}
    day_stats: list[dict] = []
    active = [
        recipe
        for recipe in recipes.values()
        if recipe["status"] != "retired"
    ]
    seasonal = [
        recipe for recipe in active if season in recipe["seasons"]
    ]
    for day in DAYS:
        if day in fixed_assignments:
            continue
        pools[day], static_traces[day] = static_day_trace(
            recipes,
            day=day,
            season=season,
            excluded_tags=excluded_tags,
            weather_category=weather["category"],
        )
        static_stages = static_traces[day]["stages"]
        active_stage = static_stages[0]
        season_stage = next(
            stage for stage in static_stages if "season filter" in stage["name"]
        )
        weather_stage = static_stages[-1]
        day_stats.append(
            {
                "day": day,
                "active_count": active_stage["after"],
                "season_eligible_count": len(seasonal),
                "day_rule_eligible_count": season_stage["after"],
                "weather_excluded_count": weather_stage["removed"],
                "eligible_count": len(pools[day]),
                "recent_count": sum(
                    recipe["id"] in recent_ids for recipe in pools[day]
                ),
            }
        )
    rejections: dict[str, dict[str, set[str]]] = {
        reason: collections.defaultdict(set)
        for reason in (
            "duplicate_recipe",
            "protein_cap",
            "user_idea_cap",
            "option_overlap",
        )
    }
    heat_bound_failed = False

    def fail(extra_messages: list[str] | None = None) -> None:
        if diagnostics is not None:
            diagnostics.update(
                _failure_diagnostics(
                    day_stats=day_stats,
                    rejections=rejections,
                    recipes=recipes,
                    minimum_heat_friendly=minimum_heat_friendly,
                    heat_bound_failed=heat_bound_failed,
                    extra_messages=extra_messages,
                )
            )

    if any(not pool for pool in pools.values()):
        fail()
        return None

    assignments: dict[str, str] = dict(fixed_assignments)
    used_ids = set(fixed_assignments.values())
    protein_counts: collections.Counter[str] = collections.Counter()
    user_idea_count = 0
    heat_friendly_count = 0
    for recipe_id in fixed_assignments.values():
        recipe = recipes.get(recipe_id)
        if recipe is None:
            fail([f"Fixed assignment references missing recipe {recipe_id}."])
            return None
        protein_counts[recipe["protein"]] += 1
        user_idea_count += recipe.get("source") == "user-idea"
        heat_friendly_count += is_heat_friendly(recipe, weather_rules)
    if any(count > MAX_PROTEIN_PER_WEEK for count in protein_counts.values()):
        fail(
            [
                "Fixed assignments already exceed the weekly protein cap: "
                + ", ".join(
                    f"{protein}={count}"
                    for protein, count in sorted(protein_counts.items())
                    if count > MAX_PROTEIN_PER_WEEK
                )
                + "."
            ]
        )
        return None

    overlap_counts = [
        len(used_ids & previous)
        for previous in previous_options
    ]
    if any(count > MAX_OPTION_OVERLAP for count in overlap_counts):
        fail(["Fixed assignments exceed the distinct-option overlap limit."])
        return None

    search_days = sorted(
        pools,
        key=lambda day: (len(pools[day]), DAYS.index(day)),
    )
    inventory_scores = {
        day: {
            recipe["id"]: (
                inventory_scores_override[recipe["id"]]
                if inventory_scores_override is not None
                and recipe["id"] in inventory_scores_override
                else inventory_match_score(recipe, week_of, root)
            )
            for recipe in pool
        }
        for day, pool in pools.items()
    }
    successful_decisions: dict[str, dict] = {}
    search_candidate_attempts = 0
    search_limit_hit = False

    def candidate_key(recipe: dict, day: str) -> tuple:
        user_idea_rank = 0 if recipe.get("source") == "user-idea" else 1
        review_rank = 0 if recipe.get("status") == "candidate" else 1
        rotation = (
            sum(ord(character) for character in recipe["id"]) + variant
        ) % max(1, len(recipes))
        return (
            global_usage[recipe["id"]],
            0 if is_heat_friendly(recipe, weather_rules) else 1,
            user_idea_rank,
            1 if recipe["id"] in recent_ids else 0,
            protein_counts[recipe["protein"]],
            -inventory_scores[day][recipe["id"]],
            review_rank,
            rotation,
            recipe["id"],
        )

    def search(position: int, idea_count: int, heat_count: int) -> bool:
        nonlocal search_candidate_attempts, heat_bound_failed, search_limit_hit
        if (
            max_search_evaluations is not None
            and search_candidate_attempts >= max_search_evaluations
        ):
            search_limit_hit = True
            return False
        if position == len(search_days):
            if heat_count < minimum_heat_friendly:
                heat_bound_failed = True
            return heat_count >= minimum_heat_friendly
        if heat_count + (len(search_days) - position) < minimum_heat_friendly:
            heat_bound_failed = True
            return False
        day = search_days[position]
        ordered_candidates = sorted(
            pools[day],
            key=lambda recipe: candidate_key(recipe, day),
        )
        decision_trace = dynamic_decision_trace(
            ordered_candidates,
            used_ids=used_ids,
            protein_counts=protein_counts,
            idea_count=idea_count,
            previous_options=previous_options,
            overlap_counts=overlap_counts,
            inventory_scores=inventory_scores[day],
            recent_ids=recent_ids,
        )
        backtracked_ids: list[str] = []
        for recipe in ordered_candidates:
            if (
                max_search_evaluations is not None
                and search_candidate_attempts >= max_search_evaluations
            ):
                search_limit_hit = True
                return False
            search_candidate_attempts += 1
            recipe_id = recipe["id"]
            protein = recipe["protein"]
            is_user_idea = recipe.get("source") == "user-idea"
            rejection_reason = decision_trace["rejection_reasons"].get(recipe_id)
            if rejection_reason:
                rejections[rejection_reason][day].add(recipe_id)
                continue
            next_overlaps = [
                overlap_counts[index] + int(recipe_id in previous)
                for index, previous in enumerate(previous_options)
            ]
            if any(count > MAX_OPTION_OVERLAP for count in next_overlaps):
                rejections["option_overlap"][day].add(recipe_id)
                continue

            assignments[day] = recipe_id
            used_ids.add(recipe_id)
            protein_counts[protein] += 1
            old_overlaps = overlap_counts[:]
            overlap_counts[:] = next_overlaps
            if search(
                position + 1,
                idea_count + int(is_user_idea),
                heat_count + int(is_heat_friendly(recipe, weather_rules)),
            ):
                for candidate in decision_trace["ranked_candidates"]:
                    if candidate["recipe_id"] == recipe_id:
                        candidate["outcome"] = "selected"
                    elif candidate["recipe_id"] in backtracked_ids:
                        candidate["outcome"] = "backtracked"
                decision_trace["backtracked_recipe_ids"] = backtracked_ids
                successful_decisions[day] = decision_trace
                return True
            overlap_counts[:] = old_overlaps
            protein_counts[protein] -= 1
            used_ids.remove(recipe_id)
            del assignments[day]
            backtracked_ids.append(recipe_id)
        return False

    if not search(0, user_idea_count, heat_friendly_count):
        fail(
            ["Search evaluation limit reached during assignment."]
            if search_limit_hit
            else None
        )
        return None
    if trace is not None:
        traced_days = []
        for day in DAYS:
            if day in fixed_assignments:
                traced_days.append(
                    fixed_day_trace(day, recipes[fixed_assignments[day]])
                )
                continue
            day_trace = static_traces[day]
            decision = successful_decisions[day]
            day_trace["stages"].extend(decision["stages"])
            day_trace["ranked_candidates"] = decision["ranked_candidates"]
            selected_id = assignments[day]
            day_trace["selected_recipe_id"] = selected_id
            day_trace["selected_name"] = recipes[selected_id]["name"]
            ranked_by_id = {
                candidate["recipe_id"]: candidate
                for candidate in decision["ranked_candidates"]
            }
            for candidate in day_trace["candidates"]:
                ranked = ranked_by_id.get(candidate["recipe_id"])
                if ranked:
                    candidate.update(
                        rank=ranked["rank"],
                        inventory_score=ranked["inventory_score"],
                        ranking_score=ranked["ranking_score"],
                        recent_repeat=ranked["recent_repeat"],
                        outcome=ranked["outcome"],
                        constraint_reason=ranked["constraint_reason"],
                    )
            traced_days.append(day_trace)
        trace.update(
            {
                "trace_version": TRACE_VERSION,
                "candidate_recipes_available": len(recipes),
                "static_candidates_considered": sum(
                    len(day_trace["candidates"])
                    for day_trace in static_traces.values()
                ),
                "search_candidate_attempts": search_candidate_attempts,
                "search_order": search_days,
                "rules_used": (
                    ["RULE-HEAT-MINIMUM"]
                    if minimum_heat_friendly > 0
                    else []
                ),
                "days": traced_days,
            }
        )
        if explain_trace:
            explain_planning_trace(trace)
    return [assignments[day] for day in DAYS]
