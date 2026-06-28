from __future__ import annotations

import collections
import datetime as dt
import random
import re
import time
from pathlib import Path

from planner.assignment import constrained_assignments
from planner.constants import (
    DAYS,
    LOW_EFFORT_METHODS,
    MAX_PROTEIN_PER_WEEK,
    ROOT,
)
from planner.eligibility import (
    inventory_match_score,
    load_recipes,
    recent_recipe_ids,
    season_for,
)
from planner.proposal import generated_ideas, user_idea_recipes
from scripts.weather_context import is_heat_friendly, load_weather_rules


WEATHER_WEIGHTS = {
    "winter": {
        "normal": 0.90,
        "warm": 0.08,
        "hot": 0.02,
        "extreme-heat": 0.00,
    },
    "spring": {
        "normal": 0.65,
        "warm": 0.25,
        "hot": 0.09,
        "extreme-heat": 0.01,
    },
    "summer": {
        "normal": 0.15,
        "warm": 0.35,
        "hot": 0.40,
        "extreme-heat": 0.10,
    },
    "fall": {
        "normal": 0.65,
        "warm": 0.25,
        "hot": 0.09,
        "extreme-heat": 0.01,
    },
}
CONSTRAINT_KEYS = (
    "protein_cap",
    "weather",
    "mexican_monday",
    "inventory_conflicts",
    "option_overlap",
    "queued_idea_cap",
    "duplicate_recipe",
    "heat_friendly",
    "search_limit",
)


def next_monday(today: dt.date | None = None) -> dt.date:
    current = today or dt.date.today()
    return current + dt.timedelta(days=(-current.weekday()) % 7)


def choose_weather_category(
    rng: random.Random,
    season: str,
) -> str:
    weights = WEATHER_WEIGHTS[season]
    return rng.choices(
        list(weights),
        weights=list(weights.values()),
        k=1,
    )[0]


def _constraint_counts(trace: dict) -> dict[str, int]:
    counts = {key: 0 for key in CONSTRAINT_KEYS}
    for day in trace.get("days", []):
        for stage in day.get("stages", []):
            name = stage.get("name", "")
            if "weather filter" in name:
                counts["weather"] += int(stage.get("removed", 0))
            elif name == "Mexican Monday filter":
                counts["mexican_monday"] += int(stage.get("removed", 0))
        for candidate in day.get("candidates", []):
            reason = candidate.get("constraint_reason")
            if reason == "protein_cap":
                counts["protein_cap"] += 1
            elif reason == "option_overlap":
                counts["option_overlap"] += 1
            elif reason == "user_idea_cap":
                counts["queued_idea_cap"] += 1
            elif reason == "duplicate_recipe":
                counts["duplicate_recipe"] += 1
    return counts


def _failure_constraint_counts(diagnostics: dict) -> dict[str, int]:
    counts = {key: 0 for key in CONSTRAINT_KEYS}
    for detail in diagnostics.get("eliminations", []):
        reason = detail.get("reason")
        count = int(detail.get("count", 0))
        if reason == "protein_cap":
            counts["protein_cap"] += count
        elif reason == "option_overlap":
            counts["option_overlap"] += count
        elif reason == "user_idea_cap":
            counts["queued_idea_cap"] += count
        elif reason == "duplicate_recipe":
            counts["duplicate_recipe"] += count
    for day in diagnostics.get("days", []):
        counts["weather"] += int(day.get("weather_excluded_count", 0))
        if day.get("day") == "Monday" and not day.get("eligible_count"):
            counts["mexican_monday"] += 1
    if any(
        "Heat-friendly minimum" in message
        for message in diagnostics.get("messages", [])
    ):
        counts["heat_friendly"] += 1
    if any(
        "Search evaluation limit" in message
        for message in diagnostics.get("messages", [])
    ):
        counts["search_limit"] += 1
    return counts


def selected_constraint_violations(
    assignments: list[str],
    selected: list[dict],
    *,
    season: str,
    weather_category: str,
    weather_rules: dict,
) -> collections.Counter[str]:
    violations: collections.Counter[str] = collections.Counter()
    duplicates = collections.Counter(assignments)
    violations["duplicate_recipe"] += sum(
        count - 1 for count in duplicates.values() if count > 1
    )
    proteins = collections.Counter(
        recipe["protein"] for recipe in selected
    )
    violations["protein_cap"] += sum(
        count - MAX_PROTEIN_PER_WEEK
        for count in proteins.values()
        if count > MAX_PROTEIN_PER_WEEK
    )
    for index, recipe in enumerate(selected):
        day = DAYS[index]
        if season not in recipe["seasons"]:
            violations["season"] += 1
        if day == "Monday" and "mexican-monday" not in recipe["tags"]:
            violations["mexican_monday"] += 1
        if (
            day in {"Tuesday", "Thursday"}
            and recipe["cooking_method"] not in LOW_EFFORT_METHODS
        ):
            violations["low_effort"] += 1
        excluded_tags = set(
            weather_rules["categories"][weather_category]["exclude_tags"]
        )
        terms = set(recipe.get("tags", [])) | set(
            re.findall(r"[a-z]+", recipe["name"].lower())
        )
        if excluded_tags & terms:
            violations["weather"] += 1
    minimum_heat = weather_rules["categories"][weather_category][
        "minimum_heat_friendly_meals"
    ]
    heat_count = sum(
        is_heat_friendly(recipe, weather_rules) for recipe in selected
    )
    if heat_count < minimum_heat:
        violations["heat_friendly"] += minimum_heat - heat_count
    return violations


def run_simulation(
    *,
    iterations: int = 10_000,
    seed: int = 42,
    start_week: dt.date | None = None,
    horizon_weeks: int = 52,
    ranking_variants: int = 2,
    search_evaluation_limit: int = 2_000,
    root: Path = ROOT,
    progress=None,
) -> dict:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if horizon_weeks < 1:
        raise ValueError("horizon_weeks must be positive")
    if ranking_variants < 1:
        raise ValueError("ranking_variants must be positive")
    if search_evaluation_limit < 1:
        raise ValueError("search_evaluation_limit must be positive")
    first_week = start_week or next_monday()
    if first_week.weekday() != 0:
        raise ValueError("start_week must be a Monday")

    started = time.perf_counter()
    rng = random.Random(seed)
    canonical = load_recipes(root)
    active_count = sum(
        recipe["status"] != "retired" for recipe in canonical.values()
    )
    supplement = active_count < 7
    weather_rules = load_weather_rules(root)
    recent_ids = recent_recipe_ids(root)
    universe_cache: dict[tuple[dt.date, bool], dict[str, dict]] = {}
    inventory_cache: dict[tuple[dt.date, str], int] = {}
    scenario_result_cache: dict[
        tuple[dt.date, str, int],
        tuple[list[str] | None, dict[str, dict], dict, dict],
    ] = {}

    successful = 0
    failed = 0
    cost_total = 0.0
    fiber_total = 0.0
    meal_count = 0
    protein_counts: collections.Counter[str] = collections.Counter()
    method_counts: collections.Counter[str] = collections.Counter()
    season_counts: collections.Counter[str] = collections.Counter()
    weather_counts: collections.Counter[str] = collections.Counter()
    constraint_counts: collections.Counter[str] = collections.Counter()
    utilization: dict[str, dict] = {}
    selected_recipe_ids: set[str] = set()
    inventory_coverage_total = 0.0
    inventory_coverage_observations = 0
    final_violations: collections.Counter[str] = collections.Counter()

    def recipe_universe(
        week: dt.date,
        include_generated: bool,
    ) -> dict[str, dict]:
        key = (week, include_generated)
        if key not in universe_cache:
            universe_cache[key] = {
                **canonical,
                **(
                    generated_ideas(week, root)
                    if include_generated
                    else {}
                ),
                **user_idea_recipes(week, root),
            }
        return universe_cache[key]

    def inventory_scores(
        week: dt.date,
        recipes: dict[str, dict],
    ) -> dict[str, int]:
        scores = {}
        for recipe_id, recipe in recipes.items():
            key = (week, recipe_id)
            if key not in inventory_cache:
                inventory_cache[key] = inventory_match_score(
                    recipe,
                    week,
                    root,
                )
            scores[recipe_id] = inventory_cache[key]
        return scores

    for iteration in range(iterations):
        week = first_week + dt.timedelta(
            weeks=rng.randrange(horizon_weeks)
        )
        season = season_for(week)
        weather_category = choose_weather_category(rng, season)
        weather = {
            "schema_version": 1,
            "week_of": week.isoformat(),
            "category": weather_category,
            "forecast_high_f": None,
            "source": "Seeded simulation scenario",
            "note": "",
        }
        variant = rng.randrange(ranking_variants)
        scenario_key = (week, weather_category, variant)
        if scenario_key in scenario_result_cache:
            assignments, recipes, diagnostics, trace = scenario_result_cache[
                scenario_key
            ]
        else:
            include_generated = supplement
            recipes = recipe_universe(week, include_generated)
            diagnostics = {}
            trace = {}
            assignments = constrained_assignments(
                week,
                recipes,
                {},
                [],
                collections.Counter(),
                variant,
                root=root,
                diagnostics=diagnostics,
                trace=trace,
                weather_context_override=weather,
                weather_rules_override=weather_rules,
                recent_ids_override=recent_ids,
                inventory_scores_override=inventory_scores(week, recipes),
                explain_trace=False,
                max_search_evaluations=search_evaluation_limit,
            )
            if assignments is None and not include_generated:
                recipes = recipe_universe(week, True)
                diagnostics = {}
                trace = {}
                assignments = constrained_assignments(
                    week,
                    recipes,
                    {},
                    [],
                    collections.Counter(),
                    variant,
                    root=root,
                    diagnostics=diagnostics,
                    trace=trace,
                    weather_context_override=weather,
                    weather_rules_override=weather_rules,
                    recent_ids_override=recent_ids,
                    inventory_scores_override=inventory_scores(week, recipes),
                    explain_trace=False,
                    max_search_evaluations=search_evaluation_limit,
                )
            scenario_result_cache[scenario_key] = (
                assignments,
                recipes,
                diagnostics,
                trace,
            )
        if assignments is None:
            failed += 1
            constraint_counts.update(
                _failure_constraint_counts(diagnostics)
            )
        else:
            successful += 1
            selected = [recipes[recipe_id] for recipe_id in assignments]
            selected_recipe_ids.update(assignments)
            cost_total += sum(
                float(recipe["estimated_cost_usd"]) for recipe in selected
            )
            fiber_total += sum(
                float(recipe["fiber_grams"]) for recipe in selected
            )
            meal_count += len(selected)
            protein_counts.update(recipe["protein"] for recipe in selected)
            method_counts.update(
                recipe["cooking_method"] for recipe in selected
            )
            season_counts[season] += len(selected)
            weather_counts[weather_category] += 1
            run_constraints = _constraint_counts(trace)
            if any(
                candidate.get("outcome") == "selected"
                and int(candidate.get("inventory_score", 100)) < 100
                for day in trace["days"]
                for candidate in day["candidates"]
            ):
                run_constraints["inventory_conflicts"] += 1
            constraint_counts.update(run_constraints)
            final_violations.update(
                selected_constraint_violations(
                    assignments,
                    selected,
                    season=season,
                    weather_category=weather_category,
                    weather_rules=weather_rules,
                )
            )

            for day in trace["days"]:
                for candidate in day["candidates"]:
                    if candidate.get("rank") is None:
                        continue
                    recipe_id = candidate["recipe_id"]
                    record = utilization.setdefault(
                        recipe_id,
                        {
                            "name": candidate["name"],
                            "times_eligible": 0,
                            "times_selected": 0,
                            "ranking_score_total": 0.0,
                        },
                    )
                    record["times_eligible"] += 1
                    record["times_selected"] += int(
                        candidate.get("outcome") == "selected"
                    )
                    record["ranking_score_total"] += float(
                        candidate["ranking_score"]
                    )
                    if candidate.get("outcome") == "selected":
                        inventory_coverage_total += float(
                            candidate["inventory_score"]
                        )
                        inventory_coverage_observations += 1
        if progress is not None and (
            (iteration + 1) % max(1, iterations // 100) == 0
            or iteration + 1 == iterations
        ):
            progress(iteration + 1, iterations)

    utilization_rows = []
    for recipe_id, record in utilization.items():
        eligible = record["times_eligible"]
        selected = record["times_selected"]
        utilization_rows.append(
            {
                "recipe_id": recipe_id,
                "name": record["name"],
                "times_eligible": eligible,
                "times_selected": selected,
                "selection_rate": round(
                    selected / eligible * 100,
                    1,
                ),
                "average_score": round(
                    record["ranking_score_total"] / eligible,
                    1,
                ),
            }
        )
    utilization_rows.sort(
        key=lambda row: (
            row["selection_rate"],
            -row["times_eligible"],
            row["name"].casefold(),
        )
    )

    def distribution(counter: collections.Counter[str], total: int) -> dict:
        return {
            key: {
                "count": count,
                "percentage": round(count / total * 100, 1) if total else 0.0,
            }
            for key, count in sorted(
                counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
        }

    elapsed = time.perf_counter() - started
    return {
        "schema_version": 1,
        "simulation": {
            "iterations": iterations,
            "seed": seed,
            "start_week": first_week.isoformat(),
            "horizon_weeks": horizon_weeks,
            "ranking_variants": ranking_variants,
            "search_evaluation_limit": search_evaluation_limit,
            "weather_weights": WEATHER_WEIGHTS,
            "cost_basis": (
                "Recipe estimated costs before inventory savings, sides, "
                "and kids' alternate meals"
            ),
            "fiber_basis": (
                "Recipe fiber metadata before side suggestions and kids' "
                "alternate meals"
            ),
            "constraint_failure_basis": (
                "Candidate filter and constraint-rejection observations"
            ),
        },
        "results": {
            "successful_weeks": successful,
            "failed_weeks": failed,
            "success_rate": round(successful / iterations * 100, 2),
            "average_grocery_bill_usd": (
                round(cost_total / successful, 2) if successful else 0.0
            ),
            "average_fiber_grams": (
                round(fiber_total / meal_count, 1) if meal_count else 0.0
            ),
            "average_inventory_coverage_score": (
                round(
                    inventory_coverage_total
                    / inventory_coverage_observations,
                    1,
                )
                if inventory_coverage_observations
                else 0.0
            ),
            "protein_distribution": distribution(
                protein_counts,
                meal_count,
            ),
            "cooking_method_distribution": distribution(
                method_counts,
                meal_count,
            ),
            "seasonal_distribution": distribution(
                season_counts,
                meal_count,
            ),
            "weather_scenarios": distribution(
                weather_counts,
                successful,
            ),
            "recipe_utilization": utilization_rows,
            "recipe_diversity": {
                "eligible_recipes": len(utilization_rows),
                "selected_recipes": len(selected_recipe_ids),
                "percentage": (
                    round(
                        len(selected_recipe_ids)
                        / len(utilization_rows)
                        * 100,
                        1,
                    )
                    if utilization_rows
                    else 0.0
                ),
            },
            "constraint_failures": {
                key: int(constraint_counts.get(key, 0))
                for key in CONSTRAINT_KEYS
            },
            "final_constraint_violations": {
                "total": sum(final_violations.values()),
                "by_rule": {
                    key: int(count)
                    for key, count in sorted(final_violations.items())
                    if count
                },
            },
            "elapsed_seconds": round(elapsed, 3),
            "weeks_per_second": round(
                iterations / elapsed,
                1,
            ) if elapsed else 0.0,
            "unique_scenarios_evaluated": len(scenario_result_cache),
            "scenario_cache_hit_rate": round(
                (iterations - len(scenario_result_cache))
                / iterations
                * 100,
                1,
            ),
        },
    }


def format_simulation_report(report: dict) -> str:
    simulation = report["simulation"]
    results = report["results"]
    lines = [
        "Planner Simulation",
        "",
        f"Weeks generated: {simulation['iterations']:,}",
        f"Successful weeks: {results['successful_weeks']:,}",
        f"Failed weeks: {results['failed_weeks']:,}",
        f"Success rate: {results['success_rate']:.2f}%",
        (
            "Average estimated grocery bill: "
            f"${results['average_grocery_bill_usd']:.2f}"
        ),
        f"Average fiber: {results['average_fiber_grams']:.1f} g/serving",
        (
            "Average inventory coverage: "
            f"{results['average_inventory_coverage_score']:.1f}/100"
        ),
        (
            "Recipe diversity: "
            f"{results['recipe_diversity']['selected_recipes']}/"
            f"{results['recipe_diversity']['eligible_recipes']} "
            f"({results['recipe_diversity']['percentage']:.1f}%)"
        ),
        (
            "Final constraint violations: "
            f"{results['final_constraint_violations']['total']}"
        ),
        (
            f"Runtime: {results['elapsed_seconds']:.2f}s "
            f"({results['weeks_per_second']:.1f} weeks/s)"
        ),
        (
            "Unique solver scenarios: "
            f"{results['unique_scenarios_evaluated']:,} "
            f"({results['scenario_cache_hit_rate']:.1f}% cache hit rate)"
        ),
        "",
        "Protein distribution",
    ]
    lines.extend(
        f"{name}: {data['count']:,} ({data['percentage']:.1f}%)"
        for name, data in results["protein_distribution"].items()
    )
    lines.extend(["", "Constraint failures"])
    lines.extend(
        f"{name.replace('_', ' ').title()}: {count:,}"
        for name, count in results["constraint_failures"].items()
    )
    minimum_eligible = max(5, simulation["iterations"] // 100)
    underused = [
        row
        for row in results["recipe_utilization"]
        if row["times_eligible"] >= minimum_eligible
    ][:10]
    lines.extend(
        [
            "",
            (
                "Lowest recipe selection rates "
                f"(minimum {minimum_eligible:,} eligible observations)"
            ),
        ]
    )
    if underused:
        lines.extend(
            (
                f"{row['recipe_id']} {row['name']}: "
                f"{row['times_selected']:,}/{row['times_eligible']:,} "
                f"({row['selection_rate']:.1f}%), "
                f"score {row['average_score']:.1f}"
            )
            for row in underused
        )
    else:
        lines.append("No recipes met the eligibility threshold.")
    lines.extend(
        [
            "",
            f"Cost basis: {simulation['cost_basis']}",
            f"Fiber basis: {simulation['fiber_basis']}",
            (
                "Constraint basis: "
                f"{simulation['constraint_failure_basis']}"
            ),
        ]
    )
    return "\n".join(lines)
