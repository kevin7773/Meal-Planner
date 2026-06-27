from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

try:
    from scripts.validate_recipes import split_recipe
    from scripts.side_dishes import suggest_sides
    from scripts.quick_meals import suggest_quick_meal
except ModuleNotFoundError:
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
) -> str:
    content = body.split("## Family Notes", 1)[0].strip()
    content = re.sub(r"(?s)^# .+?\n\n", "", content, count=1)
    lines = [
        f"## {date.strftime('%A, %B %d')} - {metadata['name']}",
        "",
        f"**Recipe:** {metadata['id']} rev {metadata['revision']} ({metadata['status']})",
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


def build_artifacts(menu_path: Path, grocery_path: Path, recipe_ids: list[str]) -> None:
    if len(recipe_ids) != 7:
        raise ValueError("Exactly seven recipe IDs are required")
    root = menu_path.resolve().parents[2]
    original = menu_path.read_text(encoding="utf-8")
    front_matter, _ = original[4:].split("\n+++\n", 1)
    week_match = re.search(r'(?m)^week_of = "(\d{4}-\d{2}-\d{2})"$', front_matter)
    if not week_match:
        raise ValueError("Menu is missing week_of metadata")
    week_of = dt.date.fromisoformat(week_match.group(1))
    history_match = re.search(
        r"(?ms)^## Planning Status History\n.*$",
        original,
    )
    if not history_match:
        raise ValueError("Menu is missing Planning Status History")

    recipes = [load_recipe(root, recipe_id) for recipe_id in recipe_ids]
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
        sections.append(
            recipe_week_section(
                metadata,
                body,
                week_of + dt.timedelta(days=index),
                suggestions,
                quick_meal,
            )
        )
    leftover_section = extract_section(original, "Weekly Leftover Plan")
    rotation_section = extract_section(original, "Rotation Notes")
    dry_run_section = extract_section(original, "Dry Run Summary")
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
            f"**Week of:** {week_of.isoformat()}  ",
            "**Family Size:** 4  ",
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
    args = parser.parse_args()
    build_artifacts(
        args.menu,
        args.grocery,
        [value.strip() for value in args.recipes.split(",") if value.strip()],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
