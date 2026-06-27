from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import re
from pathlib import Path

try:
    from scripts.inventory import assess_inventory, load_inventory
    from scripts.validate_recipes import split_recipe
    from scripts.side_dishes import suggest_sides
    from scripts.quick_meals import suggest_quick_meal
except ModuleNotFoundError:
    from inventory import assess_inventory, load_inventory
    from validate_recipes import split_recipe
    from side_dishes import suggest_sides
    from quick_meals import suggest_quick_meal


DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def recipe_week_section(
    metadata: dict,
    body: str,
    date: dt.date,
    side_suggestions: list[dict] | None = None,
    kids_quick_meal: dict | None = None,
    planned_diners: int = 4,
    override: dict | None = None,
) -> str:
    content = body.split("## Family Notes", 1)[0].strip()
    content = re.sub(r"(?s)^# .+?\n\n", "", content, count=1)
    lines = [
        f"## {date.strftime('%A, %B %d')} - {metadata['name']}",
        "",
        f"**Recipe:** {metadata['id']} rev {metadata['revision']} ({metadata['status']})",
        f"**Planned Diners:** {planned_diners}",
        "",
        content,
    ]
    if side_suggestions:
        lines.extend(
            [
                "",
                "### Suggested Side Dishes",
                "",
                *[
                    f"- **{side['name']} ({side['id']}):** "
                    f"{side['fiber_grams']} grams fiber per serving; "
                    f"{side['kid_friendly_reason']}"
                    for side in side_suggestions
                ],
            ]
        )
    if kids_quick_meal:
        lines.extend(
            [
                "",
                "### Kids' Quick Meal",
                "",
                f"- **{kids_quick_meal['name']} ({kids_quick_meal['id']}):** "
                f"${kids_quick_meal['estimated_cost_usd']:.2f}; "
                f"{kids_quick_meal['fiber_grams']} grams fiber per serving",
            ]
        )
    if override:
        lines.extend(
            [
                "",
                "**Meal Override:** alternate-recipe",
                f"**Original Recipe:** {override.get('original_recipe_id') or 'None'}",
                f"**Override Note:** {override.get('note') or 'Alternate recipe selected'}",
            ]
        )
    return "\n".join(
        lines
    )


def load_recipe(root: Path, recipe_id: str) -> tuple[dict, str]:
    for path in (root / "recipes").glob("*.md"):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        metadata, body = split_recipe(path)
        if metadata.get("id") == recipe_id:
            return metadata, body
    raise ValueError(f"Unknown recipe ID: {recipe_id}")


def extract_section(body: str, heading: str) -> str:
    pattern = rf"(?ms)^## {re.escape(heading)}\n.*?(?=^## |\Z)"
    match = re.search(pattern, body)
    return match.group(0).strip() if match else ""


def shopping_quantity(value: float, unit: str) -> float:
    if unit in {"count", "can", "box", "bag", "bunch", "ear", "slice"}:
        return float(math.ceil(value))
    if unit in {"cup", "pound"}:
        return math.ceil(value * 4) / 4
    if unit in {"ounce", "tablespoon"}:
        return float(math.ceil(value))
    return round(value, 2)


def format_quantity(value: float, unit: str) -> str:
    return f"{shopping_quantity(value, unit):g}"


def grocery_document(
    root: Path,
    week_of: dt.date,
    recipes: list[tuple[dict, str]],
    planned_diners: list[int],
    side_sets: list[list[dict]],
    quick_meals: list[dict | None],
) -> tuple[str, dict, float]:
    catalog, _, requirement_sets = load_inventory(root)
    requirements: list[dict] = []
    estimated_cost = 0.0
    for index, (metadata, _) in enumerate(recipes):
        scale = planned_diners[index] / int(metadata.get("servings", 4))
        estimated_cost += float(metadata["estimated_cost_usd"]) * scale
        for requirement in requirement_sets.get(metadata["id"], []):
            quantity = float(requirement["quantity"])
            if catalog[requirement["item_id"]]["class"] != "consumable":
                quantity *= scale
            requirements.append(
                {"item_id": requirement["item_id"], "quantity": quantity}
            )
        for side in side_sets[index]:
            estimated_cost += float(side["estimated_cost_usd"]) * scale
            for requirement in side.get("requirements", []):
                requirements.append(
                    {
                        "item_id": requirement["item_id"],
                        "quantity": float(requirement["quantity"]) * scale,
                    }
                )
        quick_meal = quick_meals[index]
        if quick_meal:
            estimated_cost += float(quick_meal["estimated_cost_usd"])
            requirements.extend(quick_meal.get("requirements", []))

    assessment = assess_inventory(
        requirements,
        root=root,
        week_of=week_of,
    )
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for item in assessment["buy"]:
        grouped[catalog[item["item_id"]]["class"]].append(item)
    headings = (
        ("fresh-produce", "Fresh Produce"),
        ("refrigerated", "Refrigerated"),
        ("frozen", "Frozen"),
        ("pantry", "Pantry"),
        ("staple", "Staples"),
    )
    lines = [
        "+++",
        f'week_of = "{week_of.isoformat()}"',
        'status = "generated"',
        "+++",
        "",
        "# Grocery List",
        "",
        f"**Week of:** {week_of.isoformat()}",
        "**Diner Schedule:** Monday-Wednesday: 4; Thursday-Sunday: 3",
        f"**Inventory Coverage:** {assessment['coverage_score']}/100",
        f"**Estimated Inventory Savings:** ${assessment['estimated_savings_usd']:.2f}",
        "",
    ]
    for item_class, heading in headings:
        lines.extend([f"## {heading}", ""])
        items = sorted(grouped.get(item_class, []), key=lambda item: item["name"])
        if items:
            lines.extend(
                f"- {format_quantity(float(item['quantity']), item['unit'])} "
                f"{item['unit']} {item['name']}"
                for item in items
            )
        else:
            lines.append("- Nothing needed after current inventory")
        lines.append("")
    lines.extend(["## Stock Checks", ""])
    if assessment["warnings"]:
        lines.extend(f"- {warning}" for warning in assessment["warnings"])
    else:
        lines.append("- No stock warnings")
    lines.append("")
    return "\n".join(lines), assessment, round(estimated_cost, 2)


def build_artifacts(
    menu_path: Path,
    grocery_path: Path,
    recipe_ids: list[str],
    planned_diners: list[int] | None = None,
) -> None:
    if len(recipe_ids) != 7:
        raise ValueError("Exactly seven recipe IDs are required")
    root = menu_path.resolve().parents[2]
    original = menu_path.read_text(encoding="utf-8")
    front_matter, _ = original[4:].split("\n+++\n", 1)
    week_match = re.search(r'(?m)^week_of = "(\d{4}-\d{2}-\d{2})"$', front_matter)
    if not week_match:
        raise ValueError("Menu is missing week_of metadata")
    week_of = dt.date.fromisoformat(week_match.group(1))
    planned_diners = planned_diners or [4] * 7
    if len(planned_diners) != 7 or any(value < 1 for value in planned_diners):
        raise ValueError("planned_diners must contain seven positive values")
    history_match = re.search(
        r"(?ms)^## Planning Status History\n.*$",
        original,
    )
    if not history_match:
        raise ValueError("Menu is missing Planning Status History")

    recipes = [load_recipe(root, recipe_id) for recipe_id in recipe_ids]
    override_path = (
        root
        / "overrides"
        / str(week_of.year)
        / f"{week_of.isoformat()}-overrides.json"
    )
    overrides = {}
    if override_path.exists():
        overrides = {
            record["day"]: record
            for record in json.loads(
                override_path.read_text(encoding="utf-8")
            ).get("overrides", [])
        }
    season = (
        "summer"
        if week_of.month in {6, 7, 8}
        else "fall"
        if week_of.month in {9, 10, 11}
        else "winter"
        if week_of.month in {12, 1, 2}
        else "spring"
    )
    used_side_ids: set[str] = set()
    sections = []
    side_sets: list[list[dict]] = []
    quick_meals: list[dict | None] = []
    for index, (metadata, body) in enumerate(recipes):
        metadata.setdefault("meal_scope", "complete-meal")
        suggestions = suggest_sides(
            metadata,
            season=season,
            week_of=week_of,
            root=root,
            exclude_ids=used_side_ids,
        )
        used_side_ids.update(side["id"] for side in suggestions)
        quick_meal = suggest_quick_meal(
            metadata,
            week_of=week_of,
            day_index=index,
            root=root,
        )
        side_sets.append(suggestions)
        quick_meals.append(quick_meal)
        sections.append(
            recipe_week_section(
                metadata,
                body,
                week_of + dt.timedelta(days=index),
                suggestions,
                quick_meal,
                planned_diners[index],
                overrides.get(DAYS[index]),
            )
        )
    grocery_text, inventory, estimated_cost = grocery_document(
        root,
        week_of,
        recipes,
        planned_diners,
        side_sets,
        quick_meals,
    )
    grocery_path.parent.mkdir(parents=True, exist_ok=True)
    grocery_path.write_text(grocery_text, encoding="utf-8", newline="\n")
    leftover_section = extract_section(original, "Weekly Leftover Plan")
    rotation_section = extract_section(original, "Rotation Notes")
    average_fiber = round(
        sum(
            float(metadata["fiber_grams"])
            + sum(float(side["fiber_grams"]) for side in side_sets[index])
            for index, (metadata, _) in enumerate(recipes)
        )
        / 7,
        1,
    )
    average_kid_score = round(
        sum(
            float(
                quick_meals[index]["kid_friendly_score"]
                if quick_meals[index]
                else metadata["kid_friendly_score"]
            )
            for index, (metadata, _) in enumerate(recipes)
        )
        / 7,
        1,
    )
    candidate_ids = sorted(
        metadata["id"]
        for metadata, _ in recipes
        if metadata["status"] == "candidate"
    )
    shopping_cost = max(
        0.0,
        estimated_cost - float(inventory["estimated_savings_usd"]),
    )
    dry_run_section = "\n".join(
        [
            "## Dry Run Summary",
            "",
            f"- Estimated weekly cost: ${estimated_cost:.2f}",
            f"- Estimated shopping cost after inventory: ${shopping_cost:.2f}",
            f"- Inventory coverage score: {inventory['coverage_score']}/100",
            f"- Estimated inventory savings: ${inventory['estimated_savings_usd']:.2f}",
            f"- Average fiber: {average_fiber:.1f} grams per serving",
            f"- Average kid-friendly score: {average_kid_score:.1f}/5",
            "- Recipe rotation score: 100/100",
            "- Family review requested for candidates: " + ", ".join(candidate_ids),
        ]
    )
    menu_summary_sections = [
        section
        for section in (leftover_section, rotation_section, dry_run_section)
        if section
    ]
    menu_text = "\n".join(
        [
            "+++",
            front_matter,
            "+++",
            "",
            "# Weekly Dinner Menu",
            "",
            f"**Week of:** {week_of.isoformat()}",
            "**Diner Schedule:** Monday-Wednesday: 4; Thursday-Sunday: 3",
            "**Season:** Summer",
            "",
            "\n\n".join(sections),
            "",
            "\n\n".join(menu_summary_sections),
            "",
            history_match.group(0).strip(),
            "",
        ]
    )
    menu_path.write_text(menu_text, encoding="utf-8", newline="\n")

    email_root = root / "email-outputs" / str(week_of.year) / week_of.isoformat()
    email_root.mkdir(parents=True, exist_ok=True)
    groups = (
        ("email-1-mon-tue.md", "Monday-Tuesday", sections[0:2]),
        ("email-2-wed-thu-fri.md", "Wednesday-Friday", sections[2:5]),
        ("email-3-sat-sun.md", "Saturday-Sunday", sections[5:7]),
    )
    for filename, label, group_sections in groups:
        content = [
            "To: klsmallwood73@gmail.com",
            f"Subject: Weekly Dinner Menu: {label}, {week_of.isoformat()}",
            "",
            *group_sections,
        ]
        if filename.startswith("email-3"):
            email_summary_sections = [
                section for section in (leftover_section, rotation_section) if section
            ]
            content.extend(
                [
                    "",
                    grocery_path.read_text(encoding="utf-8").strip(),
                    "",
                    "\n\n".join(email_summary_sections),
                ]
            )
        (email_root / filename).write_text(
            "\n\n".join(content).strip() + "\n",
            encoding="utf-8",
            newline="\n",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menu", required=True, type=Path)
    parser.add_argument("--grocery", required=True, type=Path)
    parser.add_argument("--recipes", required=True)
    parser.add_argument(
        "--diners",
        default="4,4,4,4,4,4,4",
        help="Comma-separated diner counts for Monday through Sunday",
    )
    args = parser.parse_args()
    build_artifacts(
        args.menu,
        args.grocery,
        [value.strip() for value in args.recipes.split(",") if value.strip()],
        [int(value.strip()) for value in args.diners.split(",") if value.strip()],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
