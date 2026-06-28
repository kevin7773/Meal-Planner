from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from planner.constants import DAYS, ROOT
from planner.eligibility import load_recipes, override_constraints
from planner.proposal import generated_ideas, user_idea_recipes
from planner.scoring import evaluate_proposal
from scripts.menu_status import split_menu


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
        "planned_diners = ["
        + ", ".join(str(value) for value in proposal["planned_diners"])
        + "]",
        "+++",
        "",
        "# Weekly Dinner Menu",
        "",
        f"**Week of:** {week_of.isoformat()}  ",
        "**Diner Schedule:** "
        + "; ".join(
            f"{day} {proposal['planned_diners'][index]}"
            for index, day in enumerate(DAYS)
        )
        + "  ",
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
                f"**Planned Diners:** {meal['planned_diners']}  ",
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
            "## Why This Menu",
            "",
            (
                f"- Weather fit: {proposal['weather_category']}; "
                f"{proposal['heat_friendly_meals']} of 7 meals are "
                "heat-friendly."
            ),
            (
                "- Inventory fit: "
                f"{proposal['inventory_coverage_score']}/100 coverage; "
                f"estimated shopping cost "
                f"${proposal['estimated_shopping_cost_usd']:.2f}."
            ),
            (
                "- Family fit: average kid-friendly score "
                f"{proposal['average_kid_friendly_score']:.1f}/5."
            ),
            (
                "- Nutrition fit: average fiber "
                f"{proposal['average_fiber_grams']:.1f} grams per serving."
            ),
            (
                "- Rotation fit: "
                f"{proposal['rotation_score']}/100 with recent repeats "
                "penalized."
            ),
            "",
        ]
    )
    for meal in proposal["meals"]:
        reasons = meal["selection_explanation"]["reasons"][:3]
        lines.extend(
            [
                f"### {meal['day']} - {meal['name']}",
                *[f"- {reason}" for reason in reasons],
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
    planned_diners: list[int] | None = None,
    accept_warnings: bool = False,
    root: Path = ROOT,
    now: dt.datetime | None = None,
) -> Path:
    _, override_recipes = override_constraints(week_of, root)
    recipe_universe = {
        **load_recipes(root),
        **generated_ideas(week_of, root),
        **user_idea_recipes(week_of, root),
        **override_recipes,
    }
    proposal = evaluate_proposal(
        week_of,
        assignments,
        recipe_universe,
        planned_diners=planned_diners,
        root=root,
    )
    return apply_proposal(
        proposal,
        actor=actor,
        accept_warnings=accept_warnings,
        root=root,
        now=now,
    )
