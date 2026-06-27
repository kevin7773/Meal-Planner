from __future__ import annotations

import collections
import re

from planner.constants import (
    LOW_EFFORT_METHODS,
    MAX_OPTION_OVERLAP,
    MAX_PROTEIN_PER_WEEK,
    MAX_USER_IDEAS_PER_WEEK,
)


TRACE_VERSION = 1


def _apply_stage(
    candidates: list[dict],
    *,
    name: str,
    rule_id: str | None,
    predicate,
    candidate_records: dict[str, dict],
) -> tuple[list[dict], dict]:
    remaining = []
    for recipe in candidates:
        if predicate(recipe):
            remaining.append(recipe)
        elif candidate_records[recipe["id"]]["outcome"] == "pending":
            candidate_records[recipe["id"]].update(
                outcome="filtered",
                stopped_at=name,
                stopped_rule_id=rule_id,
            )
    return remaining, {
        "name": name,
        "rule_id": rule_id,
        "before": len(candidates),
        "after": len(remaining),
        "removed": len(candidates) - len(remaining),
    }


def static_day_trace(
    recipes: dict[str, dict],
    *,
    day: str,
    season: str,
    excluded_tags: set[str],
    weather_category: str,
) -> tuple[list[dict], dict]:
    candidates = list(recipes.values())
    records = {
        recipe["id"]: {
            "recipe_id": recipe["id"],
            "name": recipe["name"],
            "outcome": "pending",
            "stopped_at": None,
            "stopped_rule_id": None,
        }
        for recipe in candidates
    }
    stages = []

    candidates, stage = _apply_stage(
        candidates,
        name="Active status filter",
        rule_id="RULE-ACTIVE-STATUS",
        predicate=lambda recipe: recipe["status"] != "retired",
        candidate_records=records,
    )
    stages.append(stage)
    candidates, stage = _apply_stage(
        candidates,
        name="Generated idea day filter",
        rule_id="RULE-GENERATED-DAY",
        predicate=lambda recipe: (
            recipe.get("source") != "generated-idea"
            or recipe.get("day") == day
        ),
        candidate_records=records,
    )
    stages.append(stage)

    if day == "Monday":
        day_stage_name = "Mexican Monday filter"
        day_rule_id = "RULE-MEXICAN-MONDAY"
        day_predicate = lambda recipe: "mexican-monday" in recipe["tags"]
    elif day in {"Tuesday", "Thursday"}:
        day_stage_name = f"{day} low-effort filter"
        day_rule_id = (
            "RULE-TUESDAY-LOW-EFFORT"
            if day == "Tuesday"
            else "RULE-THURSDAY-LOW-EFFORT"
        )
        day_predicate = (
            lambda recipe: recipe["cooking_method"] in LOW_EFFORT_METHODS
        )
    else:
        day_stage_name = f"{day} availability filter"
        day_rule_id = None
        day_predicate = lambda recipe: True
    candidates, stage = _apply_stage(
        candidates,
        name=day_stage_name,
        rule_id=day_rule_id,
        predicate=day_predicate,
        candidate_records=records,
    )
    stages.append(stage)

    candidates, stage = _apply_stage(
        candidates,
        name=f"{season.title()} season filter",
        rule_id="RULE-SEASON",
        predicate=lambda recipe: season in recipe["seasons"],
        candidate_records=records,
    )
    stages.append(stage)

    def weather_eligible(recipe: dict) -> bool:
        recipe_terms = set(recipe.get("tags", [])) | set(
            re.findall(r"[a-z]+", recipe["name"].lower())
        )
        return not (excluded_tags & recipe_terms)

    candidates, stage = _apply_stage(
        candidates,
        name=f"{weather_category} weather filter",
        rule_id="RULE-WEATHER",
        predicate=weather_eligible,
        candidate_records=records,
    )
    stages.append(stage)
    for recipe in candidates:
        records[recipe["id"]]["outcome"] = "eligible"

    return candidates, {
        "day": day,
        "started_count": len(recipes),
        "stages": stages,
        "candidates": list(records.values()),
        "selected_recipe_id": None,
        "selected_name": None,
    }


def dynamic_decision_trace(
    ordered_candidates: list[dict],
    *,
    used_ids: set[str],
    protein_counts: collections.Counter[str],
    idea_count: int,
    previous_options: list[set[str]],
    overlap_counts: list[int],
    inventory_scores: dict[str, int],
    recent_ids: set[str],
) -> dict:
    remaining = list(ordered_candidates)
    stages = [
        {
            "name": "Recent rotation ranking",
            "rule_id": "RULE-RECENT-ROTATION",
            "before": len(remaining),
            "after": len(remaining),
            "removed": 0,
            "action": "sorted",
        },
        {
            "name": "Inventory score ranking",
            "rule_id": "RULE-INVENTORY-RANKING",
            "before": len(remaining),
            "after": len(remaining),
            "removed": 0,
            "action": "sorted",
        }
    ]
    reasons: dict[str, str] = {}

    def constrain(
        name: str,
        rule_id: str,
        reason: str,
        predicate,
    ) -> None:
        nonlocal remaining
        before = len(remaining)
        kept = []
        for recipe in remaining:
            if predicate(recipe):
                kept.append(recipe)
            else:
                reasons[recipe["id"]] = reason
        remaining = kept
        stages.append(
            {
                "name": name,
                "rule_id": rule_id,
                "before": before,
                "after": len(remaining),
                "removed": before - len(remaining),
            }
        )

    constrain(
        "Within-week uniqueness",
        "RULE-UNIQUE-WEEK",
        "duplicate_recipe",
        lambda recipe: recipe["id"] not in used_ids,
    )
    constrain(
        "Protein cap",
        "RULE-PROTEIN-CAP",
        "protein_cap",
        lambda recipe: (
            protein_counts[recipe["protein"]] < MAX_PROTEIN_PER_WEEK
        ),
    )
    constrain(
        "Queued idea cap",
        "RULE-QUEUED-IDEA-CAP",
        "user_idea_cap",
        lambda recipe: (
            recipe.get("source") != "user-idea"
            or idea_count < MAX_USER_IDEAS_PER_WEEK
        ),
    )

    def within_overlap(recipe: dict) -> bool:
        next_overlaps = [
            overlap_counts[index] + int(recipe["id"] in previous)
            for index, previous in enumerate(previous_options)
        ]
        return not any(count > MAX_OPTION_OVERLAP for count in next_overlaps)

    constrain(
        "Option overlap limit",
        "RULE-OPTION-OVERLAP",
        "option_overlap",
        within_overlap,
    )
    ranked_candidates = [
        {
            "rank": rank,
            "recipe_id": recipe["id"],
            "name": recipe["name"],
            "protein": recipe["protein"],
            "inventory_score": inventory_scores[recipe["id"]],
            "recent_repeat": recipe["id"] in recent_ids,
            "ranking_score": round(
                (len(ordered_candidates) - rank + 1)
                / max(1, len(ordered_candidates))
                * 100,
                1,
            ),
            "outcome": (
                "constraint_rejected"
                if recipe["id"] in reasons
                else "eligible_not_selected"
            ),
            "constraint_reason": reasons.get(recipe["id"]),
        }
        for rank, recipe in enumerate(ordered_candidates, start=1)
    ]
    return {
        "stages": stages,
        "ranked_candidates": ranked_candidates,
        "rejection_reasons": reasons,
        "eligible_recipe_ids": [recipe["id"] for recipe in remaining],
    }


def fixed_day_trace(day: str, recipe: dict) -> dict:
    return {
        "day": day,
        "started_count": 1,
        "stages": [
            {
                "name": "Fixed human override",
                "rule_id": "RULE-FIXED-OVERRIDE",
                "before": 1,
                "after": 1,
                "removed": 0,
            }
        ],
        "candidates": [
            {
                "recipe_id": recipe["id"],
                "name": recipe["name"],
                "outcome": "selected",
                "stopped_at": None,
                "stopped_rule_id": "RULE-FIXED-OVERRIDE",
            }
        ],
        "ranked_candidates": [],
        "selected_recipe_id": recipe["id"],
        "selected_name": recipe["name"],
    }
