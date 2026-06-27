from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

try:
    from scripts.schema_version import CURRENT_SCHEMA_VERSION, schema_version_errors
except ModuleNotFoundError:
    from schema_version import CURRENT_SCHEMA_VERSION, schema_version_errors


ROOT = Path(__file__).resolve().parents[1]
VALID_CATEGORIES = {"normal", "warm", "hot", "extreme-heat"}


def load_weather_rules(root: Path = ROOT) -> dict:
    return json.loads(
        (root / "preferences" / "weather-rules.json").read_text(encoding="utf-8")
    )


def weather_path(week_of: dt.date, root: Path = ROOT) -> Path:
    return root / "weather" / str(week_of.year) / f"{week_of.isoformat()}.json"


def load_weather_context(week_of: dt.date, root: Path = ROOT) -> dict:
    path = weather_path(week_of, root)
    if not path.exists():
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "week_of": week_of.isoformat(),
            "category": "normal",
            "forecast_high_f": None,
            "source": "No weekly forecast context",
            "note": "",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def is_heat_friendly(recipe: dict, rules: dict) -> bool:
    return (
        recipe.get("status") == "override"
        or recipe.get("cooking_method") in rules["heat_friendly_methods"]
        or "cold-meal" in recipe.get("tags", [])
        or "heat-friendly" in recipe.get("tags", [])
    )


def validate_weather(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        rules = load_weather_rules(root)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        return [f"Unable to load weather rules: {exc}"]
    errors.extend(
        schema_version_errors(rules, "preferences/weather-rules.json")
    )
    if errors:
        return errors
    categories = rules.get("categories", {})
    if set(categories) != VALID_CATEGORIES:
        errors.append("weather rules must define normal, warm, hot, and extreme-heat")
    methods = rules.get("heat_friendly_methods")
    if not isinstance(methods, list) or not methods:
        errors.append("heat_friendly_methods must be a non-empty list")
    for category, rule in categories.items():
        minimum = rule.get("minimum_heat_friendly_meals")
        if not isinstance(minimum, int) or not 0 <= minimum <= 7:
            errors.append(f"{category}: invalid minimum_heat_friendly_meals")
        if not isinstance(rule.get("exclude_tags"), list):
            errors.append(f"{category}: exclude_tags must be a list")

    for path in sorted((root / "weather").glob("**/*.json")):
        try:
            context = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid weather context: {exc}")
            continue
        version_errors = schema_version_errors(
            context,
            str(path.relative_to(root)).replace("\\", "/"),
        )
        if version_errors:
            errors.extend(version_errors)
            continue
        try:
            week = dt.date.fromisoformat(context.get("week_of", ""))
        except (TypeError, ValueError) as exc:
            errors.append(f"{path}: invalid weather context: {exc}")
            continue
        if path.stem != week.isoformat():
            errors.append(f"{path}: filename must match week_of")
        if context.get("category") not in VALID_CATEGORIES:
            errors.append(f"{path}: invalid category")
        forecast_high = context.get("forecast_high_f")
        if forecast_high is not None and not isinstance(forecast_high, (int, float)):
            errors.append(f"{path}: forecast_high_f must be numeric or null")
        if not str(context.get("source", "")).strip():
            errors.append(f"{path}: source is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate weekly weather context.")
    parser.add_argument("command", choices=("validate", "show"))
    parser.add_argument("--week")
    args = parser.parse_args()
    errors = validate_weather()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.command == "show":
        if not args.week:
            parser.error("show requires --week")
        print(
            json.dumps(
                load_weather_context(dt.date.fromisoformat(args.week)),
                indent=2,
            )
        )
    else:
        print("Weather rules and weekly contexts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
