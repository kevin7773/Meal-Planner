from __future__ import annotations

import collections
import datetime as dt
import json
import re
from pathlib import Path

from planner.constants import ROOT
from scripts.schema_version import schema_version_errors


CONSTRAINT_KEYS = (
    "protein_cap",
    "weather",
    "mexican_monday",
    "inventory_conflicts",
    "option_overlap",
    "queued_idea_cap",
    "duplicate_recipe",
    "heat_friendly",
)
MAX_RECENT_RUNS = 100


def telemetry_path(root: Path = ROOT) -> Path:
    return root / "telemetry" / "planner-telemetry.json"


def empty_telemetry(now: dt.datetime | None = None) -> dict:
    timestamp = (now or dt.datetime.now(dt.timezone.utc)).isoformat()
    return {
        "schema_version": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
        "aggregate": {
            "generation_runs": 0,
            "menus_generated": 0,
            "failed_generation_runs": 0,
            "total_generation_time_ms": 0.0,
            "proposals_rejected": 0,
            "constraint_failures": {
                key: 0 for key in CONSTRAINT_KEYS
            },
            "recipe_utilization": {},
            "recommendation_drift": {
                "meal_observations": 0,
                "protein_distribution": {},
                "cooking_method_distribution": {},
                "season_distribution": {},
                "blackstone_selections": 0,
                "prep_minutes_total": 0.0,
                "cost_usd_total": 0.0,
                "fiber_grams_total": 0.0
            },
            "rule_usage_by_month": {},
        },
        "recent_runs": [],
    }


def load_telemetry(root: Path = ROOT) -> dict:
    path = telemetry_path(root)
    if not path.exists():
        return empty_telemetry()
    return json.loads(path.read_text(encoding="utf-8"))


def proposal_constraint_failures(proposals: list[dict]) -> dict[str, int]:
    failures = {key: 0 for key in CONSTRAINT_KEYS}
    for proposal in proposals:
        trace = proposal.get("planning_trace", {})
        for day in trace.get("days", []):
            for stage in day.get("stages", []):
                name = stage.get("name", "")
                if "weather filter" in name:
                    failures["weather"] += int(stage.get("removed", 0))
                elif name == "Mexican Monday filter":
                    failures["mexican_monday"] += int(stage.get("removed", 0))
            for candidate in day.get("candidates", []):
                reason = candidate.get("constraint_reason")
                if reason == "protein_cap":
                    failures["protein_cap"] += 1
                elif reason == "option_overlap":
                    failures["option_overlap"] += 1
                elif reason == "user_idea_cap":
                    failures["queued_idea_cap"] += 1
                elif reason == "duplicate_recipe":
                    failures["duplicate_recipe"] += 1
        if proposal.get("inventory_coverage_score", 100) < 100:
            failures["inventory_conflicts"] += 1
    return failures


def diagnostic_constraint_failures(diagnostics: dict) -> dict[str, int]:
    failures = {key: 0 for key in CONSTRAINT_KEYS}
    for attempt in diagnostics.get("attempts", []):
        for detail in attempt.get("eliminations", []):
            reason = detail.get("reason")
            count = int(detail.get("count", 0))
            if reason == "protein_cap":
                failures["protein_cap"] += count
            elif reason == "option_overlap":
                failures["option_overlap"] += count
            elif reason == "user_idea_cap":
                failures["queued_idea_cap"] += count
            elif reason == "duplicate_recipe":
                failures["duplicate_recipe"] += count
        for day in attempt.get("days", []):
            failures["weather"] += int(day.get("weather_excluded_count", 0))
            if (
                day.get("day") == "Monday"
                and int(day.get("eligible_count", 0)) == 0
            ):
                failures["mexican_monday"] += 1
        if any(
            "Heat-friendly minimum" in message
            for message in attempt.get("messages", [])
        ):
            failures["heat_friendly"] += 1
    return failures


def recommendation_profile(proposals: list[dict]) -> dict:
    protein_distribution: dict[str, int] = {}
    method_distribution: dict[str, int] = {}
    season_distribution: dict[str, int] = {}
    meal_observations = 0
    prep_total = 0.0
    cost_total = 0.0
    fiber_total = 0.0
    for proposal in proposals:
        recommended_meals = [
            meal
            for meal in proposal.get("meals", [])
            if meal.get("status") != "override"
        ]
        count = len(recommended_meals)
        meal_observations += count
        season = str(proposal.get("season", "unknown"))
        season_distribution[season] = (
            season_distribution.get(season, 0) + count
        )
        for meal in recommended_meals:
            protein = str(meal.get("protein", "unknown"))
            method = str(meal.get("cooking_method", "unknown"))
            protein_distribution[protein] = (
                protein_distribution.get(protein, 0) + 1
            )
            method_distribution[method] = (
                method_distribution.get(method, 0) + 1
            )
            prep_total += float(meal.get("cook_time_minutes", 0) or 0)
        cost_total += float(proposal.get("estimated_cost_usd", 0) or 0)
        fiber_total += (
            float(proposal.get("average_fiber_grams", 0) or 0) * count
        )
    return {
        "meal_observations": meal_observations,
        "protein_distribution": dict(sorted(protein_distribution.items())),
        "cooking_method_distribution": dict(sorted(method_distribution.items())),
        "season_distribution": dict(sorted(season_distribution.items())),
        "blackstone_selections": method_distribution.get("blackstone", 0),
        "prep_minutes_total": round(prep_total, 3),
        "cost_usd_total": round(cost_total, 3),
        "fiber_grams_total": round(fiber_total, 3),
        "average_prep_minutes": (
            round(prep_total / meal_observations, 1)
            if meal_observations
            else 0.0
        ),
        "average_cost_usd": (
            round(cost_total / meal_observations, 2)
            if meal_observations
            else 0.0
        ),
        "average_fiber_grams": (
            round(fiber_total / meal_observations, 1)
            if meal_observations
            else 0.0
        ),
    }


def proposal_rule_usage(proposals: list[dict]) -> collections.Counter[str]:
    usage: collections.Counter[str] = collections.Counter()
    for proposal in proposals:
        trace = proposal.get("planning_trace", {})
        usage.update(trace.get("rules_used", []))
        for day in trace.get("days", []):
            for stage in day.get("stages", []):
                rule_id = stage.get("rule_id")
                if rule_id:
                    usage[rule_id] += 1
    return usage


def diagnostic_rule_usage(
    diagnostics: dict,
) -> collections.Counter[str]:
    usage: collections.Counter[str] = collections.Counter()
    reason_rules = {
        "protein_cap": "RULE-PROTEIN-CAP",
        "option_overlap": "RULE-OPTION-OVERLAP",
        "user_idea_cap": "RULE-QUEUED-IDEA-CAP",
        "duplicate_recipe": "RULE-UNIQUE-WEEK",
    }
    for attempt in diagnostics.get("attempts", []):
        for detail in attempt.get("eliminations", []):
            rule_id = reason_rules.get(detail.get("reason"))
            if rule_id:
                usage[rule_id] += max(1, int(detail.get("count", 0)))
        for day in attempt.get("days", []):
            if int(day.get("weather_excluded_count", 0)) > 0:
                usage["RULE-WEATHER"] += 1
            if day.get("day") == "Monday":
                usage["RULE-MEXICAN-MONDAY"] += 1
        if any(
            "Heat-friendly minimum" in message
            for message in attempt.get("messages", [])
        ):
            usage["RULE-HEAT-MINIMUM"] += 1
    return usage


def _merge_distribution(
    target: dict[str, int],
    additions: dict[str, int],
) -> None:
    for key, count in additions.items():
        target[key] = int(target.get(key, 0)) + int(count)


def record_generation(
    *,
    week_of: dt.date,
    requested_proposals: int,
    generation_time_ms: float,
    proposals: list[dict] | None = None,
    failure_diagnostics: dict | None = None,
    root: Path = ROOT,
    now: dt.datetime | None = None,
) -> dict:
    timestamp = (now or dt.datetime.now(dt.timezone.utc)).isoformat()
    document = load_telemetry(root)
    aggregate = document["aggregate"]
    successful_proposals = proposals or []
    success = failure_diagnostics is None
    rejected = sum(
        int(
            proposal.get("planning_trace", {}).get(
                "rejected_proposal_attempts",
                0,
            )
        )
        + int(bool(proposal.get("errors")))
        for proposal in successful_proposals
    )
    if failure_diagnostics is not None:
        rejected += len(failure_diagnostics.get("attempts", []))
        failures = diagnostic_constraint_failures(failure_diagnostics)
        rule_usage = diagnostic_rule_usage(failure_diagnostics)
    else:
        failures = proposal_constraint_failures(successful_proposals)
        rule_usage = proposal_rule_usage(successful_proposals)

    aggregate["generation_runs"] += 1
    aggregate["menus_generated"] += len(successful_proposals)
    aggregate["failed_generation_runs"] += int(not success)
    aggregate["total_generation_time_ms"] = round(
        float(aggregate["total_generation_time_ms"])
        + float(generation_time_ms),
        3,
    )
    aggregate["proposals_rejected"] += rejected
    for key, count in failures.items():
        aggregate["constraint_failures"][key] += count
    profile = recommendation_profile(successful_proposals)
    drift = aggregate.setdefault(
        "recommendation_drift",
        empty_telemetry()["aggregate"]["recommendation_drift"],
    )
    drift["meal_observations"] += profile["meal_observations"]
    drift["blackstone_selections"] += profile["blackstone_selections"]
    drift["prep_minutes_total"] = round(
        float(drift["prep_minutes_total"]) + profile["prep_minutes_total"],
        3,
    )
    drift["cost_usd_total"] = round(
        float(drift["cost_usd_total"]) + profile["cost_usd_total"],
        3,
    )
    drift["fiber_grams_total"] = round(
        float(drift["fiber_grams_total"]) + profile["fiber_grams_total"],
        3,
    )
    _merge_distribution(
        drift["protein_distribution"],
        profile["protein_distribution"],
    )
    _merge_distribution(
        drift["cooking_method_distribution"],
        profile["cooking_method_distribution"],
    )
    _merge_distribution(
        drift["season_distribution"],
        profile["season_distribution"],
    )
    usage_by_month = aggregate.setdefault("rule_usage_by_month", {})
    month_usage = usage_by_month.setdefault(timestamp[:7], {})
    for rule_id, count in rule_usage.items():
        month_usage[rule_id] = int(month_usage.get(rule_id, 0)) + int(count)
    utilization = aggregate.setdefault("recipe_utilization", {})
    for proposal in successful_proposals:
        for day in proposal.get("planning_trace", {}).get("days", []):
            for candidate in day.get("candidates", []):
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
                        "score_observations": 0,
                    },
                )
                record["name"] = candidate["name"]
                record["times_eligible"] += 1
                record["times_selected"] += int(
                    candidate.get("outcome") == "selected"
                )
                record["ranking_score_total"] = round(
                    float(record["ranking_score_total"])
                    + float(candidate["ranking_score"]),
                    3,
                )
                record["score_observations"] += 1

    document["updated_at"] = timestamp
    document["recent_runs"].append(
        {
            "recorded_at": timestamp,
            "week_of": week_of.isoformat(),
            "requested_proposals": requested_proposals,
            "menus_generated": len(successful_proposals),
            "generation_time_ms": round(float(generation_time_ms), 3),
            "proposals_rejected": rejected,
            "success": success,
            "constraint_failures": failures,
            "recommendation_profile": profile,
            "rule_usage": dict(sorted(rule_usage.items())),
        }
    )
    document["recent_runs"] = document["recent_runs"][-MAX_RECENT_RUNS:]

    path = telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
    return document


def telemetry_summary(document: dict) -> dict:
    aggregate = document["aggregate"]
    runs = int(aggregate["generation_runs"])
    return {
        "menus_generated": int(aggregate["menus_generated"]),
        "generation_runs": runs,
        "failed_generation_runs": int(aggregate["failed_generation_runs"]),
        "average_generation_time_ms": (
            round(float(aggregate["total_generation_time_ms"]) / runs, 1)
            if runs
            else 0.0
        ),
        "average_proposals_rejected": (
            round(float(aggregate["proposals_rejected"]) / runs, 2)
            if runs
            else 0.0
        ),
        "constraint_failures": dict(aggregate["constraint_failures"]),
    }


def recipe_utilization_rows(document: dict) -> list[dict]:
    utilization = document["aggregate"].get("recipe_utilization", {})
    rows = []
    for recipe_id, record in utilization.items():
        eligible = int(record["times_eligible"])
        selected = int(record["times_selected"])
        observations = int(record["score_observations"])
        rows.append(
            {
                "recipe_id": recipe_id,
                "name": record["name"],
                "times_eligible": eligible,
                "times_selected": selected,
                "selection_rate": (
                    round(selected / eligible * 100, 1) if eligible else 0.0
                ),
                "average_score": (
                    round(
                        float(record["ranking_score_total"]) / observations,
                        1,
                    )
                    if observations
                    else 0.0
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["selection_rate"],
            -row["times_eligible"],
            row["name"].casefold(),
            row["recipe_id"],
        ),
    )


def _distribution_summary(
    distribution: dict[str, int],
    total: int,
) -> dict[str, dict]:
    return {
        key: {
            "count": int(count),
            "percentage": round(int(count) / total * 100, 1) if total else 0.0,
        }
        for key, count in sorted(
            distribution.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }


def recommendation_drift_summary(document: dict) -> dict:
    drift = document["aggregate"].get("recommendation_drift", {})
    observations = int(drift.get("meal_observations", 0))
    blackstone = int(drift.get("blackstone_selections", 0))
    return {
        "meal_observations": observations,
        "protein_distribution": _distribution_summary(
            drift.get("protein_distribution", {}),
            observations,
        ),
        "cooking_method_distribution": _distribution_summary(
            drift.get("cooking_method_distribution", {}),
            observations,
        ),
        "season_distribution": _distribution_summary(
            drift.get("season_distribution", {}),
            observations,
        ),
        "blackstone_usage": {
            "count": blackstone,
            "percentage": (
                round(blackstone / observations * 100, 1)
                if observations
                else 0.0
            ),
        },
        "average_prep_minutes": (
            round(float(drift.get("prep_minutes_total", 0)) / observations, 1)
            if observations
            else 0.0
        ),
        "average_cost_usd": (
            round(float(drift.get("cost_usd_total", 0)) / observations, 2)
            if observations
            else 0.0
        ),
        "average_fiber_grams": (
            round(float(drift.get("fiber_grams_total", 0)) / observations, 1)
            if observations
            else 0.0
        ),
        "recent_runs": [
            {
                "recorded_at": run["recorded_at"],
                "week_of": run["week_of"],
                **run.get("recommendation_profile", {}),
            }
            for run in document.get("recent_runs", [])
            if run.get("recommendation_profile", {}).get(
                "meal_observations",
                0,
            )
        ],
    }


def format_recommendation_drift(summary: dict) -> str:
    lines = [
        "Recommendation Drift",
        "",
        f"Meals observed: {summary['meal_observations']}",
        (
            "Blackstone usage: "
            f"{summary['blackstone_usage']['count']} "
            f"({summary['blackstone_usage']['percentage']:.1f}%)"
        ),
        f"Average prep: {summary['average_prep_minutes']:.1f} minutes",
        f"Average cost: ${summary['average_cost_usd']:.2f} per meal",
        f"Average fiber: {summary['average_fiber_grams']:.1f} g/serving",
        "",
        "Protein distribution",
    ]
    if summary["protein_distribution"]:
        lines.extend(
            f"{name}: {data['count']} ({data['percentage']:.1f}%)"
            for name, data in summary["protein_distribution"].items()
        )
    else:
        lines.append("No observations recorded.")
    lines.extend(["", "Cooking methods"])
    if summary["cooking_method_distribution"]:
        lines.extend(
            f"{name}: {data['count']} ({data['percentage']:.1f}%)"
            for name, data in summary["cooking_method_distribution"].items()
        )
    else:
        lines.append("No observations recorded.")
    lines.extend(["", "Seasonal balance"])
    if summary["season_distribution"]:
        lines.extend(
            f"{name}: {data['count']} ({data['percentage']:.1f}%)"
            for name, data in summary["season_distribution"].items()
        )
    else:
        lines.append("No observations recorded.")
    lines.extend(["", "Recent generation trend"])
    if summary["recent_runs"]:
        lines.append(
            f"{'Recorded':25} {'Week':10} {'Meals':>5} "
            f"{'Prep':>7} {'Cost':>8} {'Fiber':>7}"
        )
        lines.append("-" * 70)
        for run in summary["recent_runs"]:
            lines.append(
                f"{run['recorded_at'][:25]:25} {run['week_of']:10} "
                f"{run['meal_observations']:>5} "
                f"{run['average_prep_minutes']:>6.1f}m "
                f"${run['average_cost_usd']:>7.2f} "
                f"{run['average_fiber_grams']:>6.1f}g"
            )
    else:
        lines.append("No generation trend recorded yet.")
    return "\n".join(lines)


def format_recipe_utilization(rows: list[dict]) -> str:
    lines = [
        "Recipe Utilization",
        "",
        (
            f"{'Recipe':38} {'ID':10} {'Eligible':>8} "
            f"{'Selected':>8} {'Rate':>7} {'Avg Score':>9}"
        ),
        "-" * 87,
    ]
    if not rows:
        lines.append("No recipe utilization has been recorded yet.")
        return "\n".join(lines)
    for row in rows:
        name = row["name"][:38]
        lines.append(
            f"{name:38} {row['recipe_id']:10} "
            f"{row['times_eligible']:>8} {row['times_selected']:>8} "
            f"{row['selection_rate']:>6.1f}% {row['average_score']:>9.1f}"
        )
    return "\n".join(lines)


def format_telemetry_summary(summary: dict) -> str:
    labels = {
        "protein_cap": "Protein cap",
        "weather": "Weather",
        "mexican_monday": "Mexican Monday",
        "inventory_conflicts": "Inventory conflicts",
        "option_overlap": "Option overlap",
        "queued_idea_cap": "Queued idea cap",
        "duplicate_recipe": "Duplicate recipe",
        "heat_friendly": "Heat-friendly minimum",
    }
    lines = [
        "Planner Telemetry",
        "",
        f"Menus generated: {summary['menus_generated']}",
        f"Generation runs: {summary['generation_runs']}",
        f"Failed generation runs: {summary['failed_generation_runs']}",
        (
            "Average generation time: "
            f"{summary['average_generation_time_ms']:.1f} ms"
        ),
        (
            "Average proposals rejected: "
            f"{summary['average_proposals_rejected']:.2f}"
        ),
        "",
        "Constraint failures",
    ]
    lines.extend(
        f"{labels[key]}: {summary['constraint_failures'][key]}"
        for key in CONSTRAINT_KEYS
    )
    return "\n".join(lines)


def validate_telemetry(root: Path = ROOT) -> list[str]:
    path = telemetry_path(root)
    if not path.exists():
        return ["telemetry/planner-telemetry.json is missing"]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to load planner telemetry: {exc}"]
    errors = schema_version_errors(
        document,
        "telemetry/planner-telemetry.json",
    )
    if errors:
        return errors
    aggregate = document.get("aggregate")
    if not isinstance(aggregate, dict):
        return ["planner telemetry aggregate must be an object"]
    for field in (
        "generation_runs",
        "menus_generated",
        "failed_generation_runs",
        "proposals_rejected",
    ):
        value = aggregate.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"planner telemetry {field} must be non-negative")
    total_time = aggregate.get("total_generation_time_ms")
    if not isinstance(total_time, (int, float)) or total_time < 0:
        errors.append(
            "planner telemetry total_generation_time_ms must be non-negative"
        )
    failures = aggregate.get("constraint_failures")
    if not isinstance(failures, dict) or set(failures) != set(CONSTRAINT_KEYS):
        errors.append(
            "planner telemetry constraint_failures has invalid keys"
        )
    elif any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in failures.values()
    ):
        errors.append(
            "planner telemetry constraint failure counts must be non-negative"
        )
    utilization = aggregate.get("recipe_utilization")
    if not isinstance(utilization, dict):
        errors.append("planner telemetry recipe_utilization must be an object")
    else:
        for recipe_id, record in utilization.items():
            if not isinstance(recipe_id, str) or not recipe_id:
                errors.append("planner telemetry has an invalid recipe ID")
                continue
            if not isinstance(record, dict) or not str(
                record.get("name", "")
            ).strip():
                errors.append(f"{recipe_id}: utilization name is required")
                continue
            for field in (
                "times_eligible",
                "times_selected",
                "score_observations",
            ):
                value = record.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    errors.append(
                        f"{recipe_id}: utilization {field} must be non-negative"
                    )
            score_total = record.get("ranking_score_total")
            if not isinstance(score_total, (int, float)) or score_total < 0:
                errors.append(
                    f"{recipe_id}: ranking_score_total must be non-negative"
                )
            eligible = record.get("times_eligible")
            selected = record.get("times_selected")
            observations = record.get("score_observations")
            if (
                isinstance(eligible, int)
                and not isinstance(eligible, bool)
                and isinstance(selected, int)
                and not isinstance(selected, bool)
                and selected > eligible
            ):
                errors.append(
                    f"{recipe_id}: times_selected cannot exceed times_eligible"
                )
            if (
                isinstance(eligible, int)
                and not isinstance(eligible, bool)
                and isinstance(observations, int)
                and not isinstance(observations, bool)
                and observations != eligible
            ):
                errors.append(
                    f"{recipe_id}: score_observations must equal times_eligible"
                )
            if (
                isinstance(score_total, (int, float))
                and not isinstance(score_total, bool)
                and isinstance(observations, int)
                and not isinstance(observations, bool)
                and score_total > observations * 100
            ):
                errors.append(
                    f"{recipe_id}: ranking_score_total exceeds 100 per observation"
                )
    drift = aggregate.get("recommendation_drift")
    if not isinstance(drift, dict):
        errors.append("planner telemetry recommendation_drift must be an object")
    else:
        observations = drift.get("meal_observations")
        if (
            isinstance(observations, bool)
            or not isinstance(observations, int)
            or observations < 0
        ):
            errors.append(
                "planner telemetry meal_observations must be non-negative"
            )
            observations = None
        for field in (
            "protein_distribution",
            "cooking_method_distribution",
            "season_distribution",
        ):
            distribution = drift.get(field)
            if not isinstance(distribution, dict) or any(
                not isinstance(key, str)
                or not key
                or isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                for key, value in (
                    distribution.items()
                    if isinstance(distribution, dict)
                    else []
                )
            ):
                errors.append(
                    f"planner telemetry {field} must contain non-negative counts"
                )
            elif observations is not None and sum(
                distribution.values()
            ) != observations:
                errors.append(
                    f"planner telemetry {field} must sum to meal_observations"
                )
        blackstone = drift.get("blackstone_selections")
        if (
            isinstance(blackstone, bool)
            or not isinstance(blackstone, int)
            or blackstone < 0
        ):
            errors.append(
                "planner telemetry blackstone_selections must be non-negative"
            )
        elif observations is not None and blackstone > observations:
            errors.append(
                "planner telemetry blackstone_selections exceeds observations"
            )
        for field in (
            "prep_minutes_total",
            "cost_usd_total",
            "fiber_grams_total",
        ):
            value = drift.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                errors.append(
                    f"planner telemetry {field} must be non-negative"
                )
    usage_by_month = aggregate.get("rule_usage_by_month")
    if not isinstance(usage_by_month, dict):
        errors.append("planner telemetry rule_usage_by_month must be an object")
    else:
        for month, usage in usage_by_month.items():
            if re.fullmatch(r"\d{4}-\d{2}", month) is None:
                errors.append(f"planner telemetry has invalid rule month {month}")
            if not isinstance(usage, dict) or any(
                not isinstance(rule_id, str)
                or not rule_id.startswith("RULE-")
                or isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
                for rule_id, count in (
                    usage.items() if isinstance(usage, dict) else []
                )
            ):
                errors.append(
                    f"planner telemetry rule usage for {month} is invalid"
                )
    recent_runs = document.get("recent_runs")
    if not isinstance(recent_runs, list):
        errors.append("planner telemetry recent_runs must be an array")
    elif len(recent_runs) > MAX_RECENT_RUNS:
        errors.append(
            f"planner telemetry retains at most {MAX_RECENT_RUNS} recent runs"
        )
    return errors
