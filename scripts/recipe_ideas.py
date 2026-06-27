from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

try:
    from scripts.schema_version import schema_version_errors
except ModuleNotFoundError:
    from schema_version import schema_version_errors


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"queued", "selected", "converted", "retired"}
VALID_PROTEINS = {
    "chicken",
    "turkey",
    "beef",
    "seafood",
    "pork",
    "vegetarian",
    "other",
}
VALID_METHODS = {
    "stovetop",
    "oven",
    "grill",
    "smoker",
    "blackstone",
    "slow-cooker",
    "minimal-cook",
    "no-cook",
}
VALID_SEASONS = {"spring", "summer", "fall", "winter"}


def idea_path(root: Path = ROOT) -> Path:
    return root / "ideas" / "recipe-ideas.json"


def load_ideas(root: Path = ROOT) -> dict:
    return json.loads(idea_path(root).read_text(encoding="utf-8"))


def validate_ideas(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        document = load_ideas(root)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unable to load recipe ideas: {exc}"]
    errors.extend(schema_version_errors(document, "ideas/recipe-ideas.json"))
    if errors:
        return errors
    if not isinstance(document.get("next_id"), int) or document["next_id"] < 1:
        errors.append("recipe idea next_id must be a positive integer")
    ideas = document.get("ideas")
    if not isinstance(ideas, list):
        return [*errors, "recipe ideas must be an array"]
    seen: set[str] = set()
    for idea in ideas:
        idea_id = idea.get("id")
        if not isinstance(idea_id, str) or not idea_id.startswith("IDEA-USER-"):
            errors.append("recipe idea has an invalid ID")
        elif idea_id in seen:
            errors.append(f"duplicate recipe idea ID: {idea_id}")
        seen.add(idea_id)
        if not isinstance(idea.get("idea"), str) or not idea["idea"].strip():
            errors.append(f"{idea_id}: idea text is required")
        if not isinstance(idea.get("name"), str) or not idea["name"].strip():
            errors.append(f"{idea_id}: name is required")
        if idea.get("status") not in VALID_STATUSES:
            errors.append(f"{idea_id}: invalid status")
        if idea.get("protein") not in VALID_PROTEINS:
            errors.append(f"{idea_id}: invalid protein")
        if idea.get("meal_scope", "complete-meal") not in {"entree", "complete-meal"}:
            errors.append(f"{idea_id}: invalid meal_scope")
        if idea.get("cooking_method") not in VALID_METHODS:
            errors.append(f"{idea_id}: invalid cooking method")
        if (
            not isinstance(idea.get("fiber_grams"), (int, float))
            or idea["fiber_grams"] < 0
        ):
            errors.append(f"{idea_id}: fiber_grams must be non-negative")
        if (
            not isinstance(idea.get("estimated_cost_usd"), (int, float))
            or idea["estimated_cost_usd"] < 0
        ):
            errors.append(f"{idea_id}: estimated_cost_usd must be non-negative")
        kid_score = idea.get("kid_friendly_score")
        kid_reason = str(idea.get("kid_friendly_reason", "")).strip()
        if kid_score not in {1, 4, 5}:
            errors.append(f"{idea_id}: kid_friendly_score must be 1, 4, or 5")
        elif kid_score == 1 and kid_reason != "Not kid friendly - for the parents only":
            errors.append(f"{idea_id}: score 1 is reserved for parents-only ideas")
        if not kid_reason:
            errors.append(f"{idea_id}: kid_friendly_reason is required")
        seasons = idea.get("seasons")
        if (
            not isinstance(seasons, list)
            or not seasons
            or any(season not in VALID_SEASONS for season in seasons)
        ):
            errors.append(f"{idea_id}: invalid seasons")
    return errors


def add_idea(
    idea: str,
    *,
    name: str,
    protein: str,
    meal_scope: str = "complete-meal",
    cooking_method: str,
    fiber_grams: float,
    estimated_cost_usd: float,
    kid_friendly_score: int,
    kid_friendly_reason: str,
    seasons: list[str],
    mexican_monday: bool = False,
    root: Path = ROOT,
) -> str:
    document = load_ideas(root)
    number = int(document["next_id"])
    idea_id = f"IDEA-USER-{number:04d}"
    lowered_idea = f"{idea} {name}".lower()
    heat_friendly = cooking_method in {
        "no-cook",
        "minimal-cook",
        "grill",
        "blackstone",
        "smoker",
    }
    cold_meal = cooking_method == "no-cook" or any(
        term in lowered_idea
        for term in ("cold ", "chilled ", "salad", "deli ", "snack board")
    )
    tags = sorted(
        {
            *seasons,
            protein,
            cooking_method,
            "user-idea",
            *(["mexican-monday"] if mexican_monday else []),
            *(["heat-friendly"] if heat_friendly else []),
            *(["cold-meal"] if cold_meal else []),
        }
    )
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    document["ideas"].append(
        {
            "id": idea_id,
            "status": "queued",
            "idea": idea.strip(),
            "name": name.strip(),
            "protein": protein,
            "meal_scope": meal_scope,
            "cooking_method": cooking_method,
            "fiber_grams": fiber_grams,
            "estimated_cost_usd": estimated_cost_usd,
            "kid_friendly_score": kid_friendly_score,
            "kid_friendly_reason": kid_friendly_reason.strip(),
            "seasons": seasons,
            "tags": tags,
            "created_at": now,
            "converted_recipe_id": None,
        }
    )
    document["next_id"] = number + 1
    output = idea_path(root)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    errors = validate_ideas(root)
    if errors:
        raise ValueError("; ".join(errors))
    return idea_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage user recipe ideas.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")
    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--idea", required=True)
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--protein", required=True, choices=sorted(VALID_PROTEINS))
    add_parser.add_argument(
        "--meal-scope",
        choices=("entree", "complete-meal"),
        default="complete-meal",
    )
    add_parser.add_argument("--method", required=True, choices=sorted(VALID_METHODS))
    add_parser.add_argument("--fiber", required=True, type=float)
    add_parser.add_argument("--cost", required=True, type=float)
    add_parser.add_argument("--kid-score", required=True, type=int, choices=(1, 4, 5))
    add_parser.add_argument("--kid-reason", required=True)
    add_parser.add_argument("--seasons", required=True)
    add_parser.add_argument("--mexican-monday", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            errors = validate_ideas()
            if errors:
                for error in errors:
                    print(f"- {error}")
                return 1
            print("Recipe idea backlog is valid.")
            return 0
        if args.command == "list":
            document = load_ideas()
            if args.json:
                print(json.dumps(document["ideas"], indent=2))
            else:
                for idea in document["ideas"]:
                    print(f"{idea['id']} [{idea['status']}] {idea['idea']}")
            return 0
        idea_id = add_idea(
            args.idea,
            name=args.name,
            protein=args.protein,
            meal_scope=args.meal_scope,
            cooking_method=args.method,
            fiber_grams=args.fiber,
            estimated_cost_usd=args.cost,
            kid_friendly_score=args.kid_score,
            kid_friendly_reason=args.kid_reason,
            seasons=[value.strip() for value in args.seasons.split(",") if value.strip()],
            mexican_monday=args.mexican_monday,
        )
        print(idea_id)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Recipe idea operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
