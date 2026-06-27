from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from scripts.build_week_artifacts import load_recipe, recipe_week_section
    from scripts.inventory import load_inventory
    from scripts.menu_status import MenuStatusError, split_menu, transition_menu
    from scripts.side_dishes import suggest_sides
except ModuleNotFoundError:
    from build_week_artifacts import load_recipe, recipe_week_section
    from inventory import load_inventory
    from menu_status import MenuStatusError, split_menu, transition_menu
    from side_dishes import suggest_sides


ROOT = Path(__file__).resolve().parents[1]
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
OVERRIDE_TYPES = (
    "dining-out",
    "special-occasion",
    "skip",
    "custom",
    "alternate-recipe",
)


def day_section_pattern(day: str) -> re.Pattern[str]:
    following = "|".join(DAYS[DAYS.index(day) + 1 :])
    next_day = rf"^## (?:{following})," if following else r"(?!x)x"
    boundary = (
        rf"(?={next_day}|^## (?:Weekly Leftover Plan|Rotation Notes|"
        rf"Dry Run Summary|Planning Status History)|^# Grocery List|\Z)"
    )
    return re.compile(
        rf"(?ms)^## {re.escape(day)}, (?P<date>.+?) - (?P<title>.+?)\n"
        rf"(?P<body>.*?){boundary}"
    )


def menu_days(menu_path: Path) -> list[dict]:
    text = menu_path.read_text(encoding="utf-8")
    result: list[dict] = []
    for day in DAYS:
        match = day_section_pattern(day).search(text)
        if not match:
            continue
        recipe_match = re.search(r"\*\*Recipe:\*\* (FDP-\d{4})", match.group("body"))
        result.append(
            {
                "day": day,
                "date": match.group("date"),
                "title": match.group("title"),
                "recipe_id": recipe_match.group(1) if recipe_match else None,
            }
        )
    return result


def replace_day_section(text: str, day: str, replacement: str) -> str:
    pattern = day_section_pattern(day)
    updated, count = pattern.subn(replacement.rstrip() + "\n\n", text, count=1)
    if count != 1:
        raise ValueError(f"Could not locate {day} in artifact")
    return updated


def email_path_for(root: Path, week_of: dt.date, day: str) -> Path:
    filename = (
        "email-1-mon-tue.md"
        if day in {"Monday", "Tuesday"}
        else "email-2-wed-thu-fri.md"
        if day in {"Wednesday", "Thursday", "Friday"}
        else "email-3-sat-sun.md"
    )
    return root / "email-outputs" / str(week_of.year) / week_of.isoformat() / filename


def override_section(
    day: str,
    date_label: str,
    override_type: str,
    title: str,
    note: str,
    original_recipe_id: str | None,
) -> str:
    label = title or override_type.replace("-", " ").title()
    return "\n".join(
        [
            f"## {day}, {date_label} - {label}",
            "",
            f"**Meal Override:** {override_type}",
            f"**Original Recipe:** {original_recipe_id or 'None'}",
            "**Planning Status:** Draft; revalidation required",
            "",
            note or "No additional details.",
        ]
    )


def write_grocery_adjustments(root: Path, week_of: dt.date, records: list[dict]) -> None:
    grocery_path = (
        root
        / "grocery-lists"
        / str(week_of.year)
        / f"{week_of.isoformat()}-grocery-list.md"
    )
    if not grocery_path.exists():
        return
    catalog, _, requirements = load_inventory(root)
    delta: collections.Counter[str] = collections.Counter()
    for record in records:
        original = record.get("original_recipe_id")
        replacement = record.get("replacement_recipe_id")
        for item in requirements.get(original, []):
            delta[item["item_id"]] -= float(item["quantity"])
        for item in requirements.get(replacement, []):
            delta[item["item_id"]] += float(item["quantity"])

    lines = [
        "## Meal Override Grocery Adjustments",
        "",
        "Apply these deltas to the original consolidated list before shopping:",
        "",
    ]
    for item_id, quantity in sorted(delta.items()):
        if abs(quantity) < 0.001 or item_id not in catalog:
            continue
        item = catalog[item_id]
        if item["class"] == "consumable":
            lines.append(f"- Recheck {item['name']} after overrides")
        elif quantity > 0:
            lines.append(f"- Add {quantity:g} {item['unit']} {item['name']}")
        else:
            lines.append(f"- Reduce by {abs(quantity):g} {item['unit']} {item['name']}")
    if len(lines) == 4:
        lines.append("- No grocery quantity changes")

    text = grocery_path.read_text(encoding="utf-8")
    text = re.sub(
        r"(?ms)\n## Meal Override Grocery Adjustments\n.*$",
        "",
        text,
    ).rstrip()
    grocery_path.write_text(
        text + "\n\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def apply_override(
    menu_path: Path,
    *,
    day: str,
    override_type: str,
    title: str,
    note: str,
    actor: str,
    replacement_recipe_id: str | None = None,
    root: Path = ROOT,
) -> Path:
    if day not in DAYS:
        raise ValueError(f"Unknown day: {day}")
    if override_type not in OVERRIDE_TYPES:
        raise ValueError(f"Unknown override type: {override_type}")
    if override_type == "alternate-recipe" and not replacement_recipe_id:
        raise ValueError("alternate-recipe requires a replacement recipe ID")

    metadata, _ = split_menu(menu_path)
    status = metadata["status"]
    if status in {"completed", "archived"}:
        raise ValueError(f"Cannot override a {status} week")
    if status != "draft":
        transition_menu(
            menu_path,
            "draft",
            actor,
            f"{day} meal override requested: {override_type}",
            run_validators=False,
        )

    week_of = dt.date.fromisoformat(metadata["week_of"])
    days = {entry["day"]: entry for entry in menu_days(menu_path)}
    if day not in days:
        raise ValueError(f"{day} is missing from the weekly menu")
    current = days[day]
    sidecar = (
        root
        / "overrides"
        / str(week_of.year)
        / f"{week_of.isoformat()}-overrides.json"
    )
    records: list[dict] = []
    if sidecar.exists():
        records = json.loads(sidecar.read_text(encoding="utf-8")).get("overrides", [])
    previous = next((record for record in records if record["day"] == day), None)
    original_recipe_id = (
        previous.get("original_recipe_id") if previous else current.get("recipe_id")
    )
    records = [record for record in records if record["day"] != day]
    record = {
        "day": day,
        "type": override_type,
        "title": title,
        "note": note,
        "actor": actor,
        "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "original_recipe_id": original_recipe_id,
        "replacement_recipe_id": replacement_recipe_id,
    }
    records.append(record)

    if override_type == "alternate-recipe":
        recipe_metadata, recipe_body = load_recipe(root, replacement_recipe_id)
        date_value = week_of + dt.timedelta(days=DAYS.index(day))
        recipe_metadata.setdefault("meal_scope", "complete-meal")
        season = (
            "summer"
            if week_of.month in {6, 7, 8}
            else "fall"
            if week_of.month in {9, 10, 11}
            else "winter"
            if week_of.month in {12, 1, 2}
            else "spring"
        )
        suggestions = suggest_sides(
            recipe_metadata,
            season=season,
            week_of=week_of,
            root=root,
        )
        replacement = recipe_week_section(
            recipe_metadata,
            recipe_body,
            date_value,
            suggestions,
        )
        replacement += (
            f"\n\n**Meal Override:** alternate-recipe  \n"
            f"**Original Recipe:** {original_recipe_id}  \n"
            f"**Override Note:** {note or 'Alternate recipe selected'}"
        )
    else:
        replacement = override_section(
            day,
            current["date"],
            override_type,
            title,
            note,
            original_recipe_id,
        )

    menu_text = replace_day_section(
        menu_path.read_text(encoding="utf-8"),
        day,
        replacement,
    )
    menu_path.write_text(menu_text, encoding="utf-8", newline="\n")

    email_path = email_path_for(root, week_of, day)
    if email_path.exists():
        email_text = replace_day_section(
            email_path.read_text(encoding="utf-8"),
            day,
            replacement,
        )
        email_path.write_text(email_text, encoding="utf-8", newline="\n")

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "week_of": week_of.isoformat(),
                "overrides": sorted(records, key=lambda item: DAYS.index(item["day"])),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_grocery_adjustments(root, week_of, records)
    return sidecar


def inspect_menu(menu_path: Path, root: Path = ROOT) -> dict:
    metadata, _ = split_menu(menu_path)
    recipes = []
    for path in sorted((root / "recipes").glob("*.md")):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        recipe_metadata, _ = load_recipe(root, re.search(
            r'(?m)^id = "(FDP-\d{4})"$',
            path.read_text(encoding="utf-8"),
        ).group(1))
        if recipe_metadata["status"] != "retired":
            recipes.append(
                {
                    "id": recipe_metadata["id"],
                    "name": recipe_metadata["name"],
                    "revision": recipe_metadata["revision"],
                    "status": recipe_metadata["status"],
                }
            )
    return {
        "week_of": metadata["week_of"],
        "status": metadata["status"],
        "days": menu_days(menu_path),
        "recipes": recipes,
    }


def validate_overrides(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    recipe_ids = {
        entry["recipe_id"]
        for menu in (root / "menus").glob("**/*.md")
        for entry in menu_days(menu)
        if entry.get("recipe_id")
    }
    for path in (root / "recipes").glob("*.md"):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        match = re.search(
            r'(?m)^id = "(FDP-\d{4})"$',
            path.read_text(encoding="utf-8"),
        )
        if match:
            recipe_ids.add(match.group(1))
    for path in sorted((root / "overrides").glob("**/*-overrides.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON: {exc}")
            continue
        seen_days: set[str] = set()
        for record in document.get("overrides", []):
            day = record.get("day")
            if day not in DAYS:
                errors.append(f"{path}: invalid day {day}")
            elif day in seen_days:
                errors.append(f"{path}: duplicate override for {day}")
            seen_days.add(day)
            if record.get("type") not in OVERRIDE_TYPES:
                errors.append(f"{path}: invalid override type")
            original = record.get("original_recipe_id")
            replacement = record.get("replacement_recipe_id")
            if original and original not in recipe_ids:
                errors.append(f"{path}: unknown original recipe {original}")
            if replacement and replacement not in recipe_ids:
                errors.append(f"{path}: unknown replacement recipe {replacement}")
            if record.get("type") == "alternate-recipe" and not replacement:
                errors.append(f"{path}: alternate recipe is missing replacement_recipe_id")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or override a weekly meal.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--menu", required=True, type=Path)
    subparsers.add_parser("validate")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--menu", required=True, type=Path)
    apply_parser.add_argument("--day", required=True, choices=DAYS)
    apply_parser.add_argument("--type", required=True, choices=OVERRIDE_TYPES)
    apply_parser.add_argument("--title", default="")
    apply_parser.add_argument("--note", default="")
    apply_parser.add_argument("--actor", required=True)
    apply_parser.add_argument("--recipe-id")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            errors = validate_overrides()
            if errors:
                for error in errors:
                    print(f"- {error}")
                return 1
            print("Meal override records are valid.")
            return 0
        if args.command == "inspect":
            print(json.dumps(inspect_menu(args.menu), indent=2))
            return 0
        sidecar = apply_override(
            args.menu,
            day=args.day,
            override_type=args.type,
            title=args.title,
            note=args.note,
            actor=args.actor,
            replacement_recipe_id=args.recipe_id,
            root=ROOT,
        )
        print(sidecar)
        return 0
    except (OSError, ValueError, MenuStatusError) as exc:
        print(f"Meal override failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
