from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "recipes"
REQUIRED_FIELDS = {
    "id",
    "name",
    "revision",
    "status",
    "servings",
    "created",
    "updated",
    "rating_average",
    "ratings_count",
    "protein",
    "fiber_grams",
    "estimated_cost_usd",
    "kid_friendly_score",
    "kid_friendly_reason",
    "cooking_method",
    "cook_time_minutes",
    "seasons",
    "leftover_recipe_ids",
    "tags",
}
REQUIRED_HEADINGS = {
    "## Recipe Card",
    "## Ingredients",
    "### Main Ingredients",
    "### Seasonings",
    "## Directions",
    "## Leftover Plan",
    "## Family Notes",
    "## Ratings",
    "## Revision History",
}
VALID_STATUSES = {"candidate", "approved", "retired"}
VALID_PROTEINS = {
    "chicken",
    "turkey",
    "beef",
    "seafood",
    "pork",
    "vegetarian",
    "other",
}
MEXICAN_MONDAY_PROTEINS = {"chicken", "turkey", "beef", "seafood"}
VALID_SEASONS = {"spring", "summer", "fall", "winter"}
SUMMER_FORBIDDEN_WORDS = {"soup", "chili", "stew"}
RECIPE_ID_PATTERN = re.compile(r"FDP-\d{4}")
SEASONING_PATTERN = re.compile(
    r"^- (?:\d+(?: \d+/\d+)?|\d+/\d+)\s+"
    r"(?:teaspoons?|tablespoons?|cups?|ounces?|cloves?|pinches?)\s+"
    r"(.+?)(?:,\s.*)?$",
    re.MULTILINE,
)


def split_recipe(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++\n"):
        raise ValueError("missing opening TOML front matter")
    try:
        raw_metadata, body = text[4:].split("\n+++\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing TOML front matter") from exc
    return tomllib.loads(raw_metadata), body


def section(body: str, heading: str, next_heading_level: str = "##") -> str:
    start = body.find(heading)
    if start < 0:
        return ""
    content_start = start + len(heading)
    match = re.search(rf"(?m)^{re.escape(next_heading_level)}\s", body[content_start:])
    end = content_start + match.start() if match else len(body)
    return body[content_start:end]


def rating_values(body: str) -> list[int]:
    ratings = section(body, "## Ratings")
    values: list[int] = []
    for line in ratings.splitlines():
        match = re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*([1-5])\s*\|", line)
        if match:
            values.append(int(match.group(1)))
    return values


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def recipe_card_value(body: str, label: str) -> str | None:
    match = re.search(
        rf"(?mi)^-\s+\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$",
        section(body, "## Recipe Card"),
    )
    return match.group(1).strip() if match else None


def reported_cook_minutes(body: str) -> int | None:
    value = recipe_card_value(body, "Cook time")
    if value is None:
        return None
    match = re.fullmatch(r"(\d+)(?:\s*-\s*\d+)?\s+(minutes?|hours?)", value.lower())
    if not match:
        return None
    amount = int(match.group(1))
    return amount * 60 if match.group(2).startswith("hour") else amount


def reported_fiber_grams(body: str) -> float | None:
    value = recipe_card_value(body, "Estimated fiber")
    if value is None:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)\s+grams?\s+per serving", value.lower())
    return float(match.group(1)) if match else None


def semantic_errors(metadata: dict, body: str, all_recipe_ids: set[str]) -> list[str]:
    errors: list[str] = []
    recipe_id = metadata.get("id")
    name = metadata.get("name", "")
    tags = metadata.get("tags", [])
    protein = metadata.get("protein")
    meal_scope = metadata.get("meal_scope", "complete-meal")
    fiber_grams = metadata.get("fiber_grams")
    estimated_cost_usd = metadata.get("estimated_cost_usd")
    kid_friendly_score = metadata.get("kid_friendly_score")
    kid_friendly_reason = metadata.get("kid_friendly_reason")
    cooking_method = metadata.get("cooking_method")
    cook_time_minutes = metadata.get("cook_time_minutes")
    seasons = metadata.get("seasons")
    declared_leftovers = metadata.get("leftover_recipe_ids")

    if protein not in VALID_PROTEINS:
        errors.append(f"protein must be one of {sorted(VALID_PROTEINS)}")
    if meal_scope not in {"entree", "complete-meal"}:
        errors.append("meal_scope must be entree or complete-meal")
    if not isinstance(fiber_grams, (int, float)) or isinstance(fiber_grams, bool) or fiber_grams < 0:
        errors.append("fiber_grams must be a non-negative number")
    if (
        not isinstance(estimated_cost_usd, (int, float))
        or isinstance(estimated_cost_usd, bool)
        or estimated_cost_usd < 0
    ):
        errors.append("estimated_cost_usd must be a non-negative number")
    if (
        not isinstance(kid_friendly_score, int)
        or isinstance(kid_friendly_score, bool)
        or not 1 <= kid_friendly_score <= 5
    ):
        errors.append("kid_friendly_score must be an integer from 1 to 5")
    elif (
        kid_friendly_score == 1
        and kid_friendly_reason != "Not kid friendly - for the parents only"
    ):
        errors.append("kid_friendly_score 1 is reserved for parents-only recipes")
    elif (
        kid_friendly_reason == "Not kid friendly - for the parents only"
        and kid_friendly_score != 1
    ):
        errors.append("parents-only recipes must use kid_friendly_score 1")
    elif (
        metadata.get("status") != "retired"
        and kid_friendly_score < 4
        and kid_friendly_reason != "Not kid friendly - for the parents only"
    ):
        errors.append("active recipes require kid_friendly_score of at least 4")
    if not isinstance(kid_friendly_reason, str) or not kid_friendly_reason.strip():
        errors.append("kid_friendly_reason must explain the family-friendly design")
    if not isinstance(cooking_method, str) or not cooking_method:
        errors.append("cooking_method must be a non-empty string")
    if (
        not isinstance(cook_time_minutes, int)
        or isinstance(cook_time_minutes, bool)
        or cook_time_minutes < 0
    ):
        errors.append("cook_time_minutes must be a non-negative integer")
    if (
        not isinstance(seasons, list)
        or not seasons
        or any(season not in VALID_SEASONS for season in seasons)
    ):
        errors.append(f"seasons must contain only {sorted(VALID_SEASONS)}")
        seasons = []
    if not isinstance(declared_leftovers, list) or any(
        not isinstance(item, str) or not RECIPE_ID_PATTERN.fullmatch(item)
        for item in declared_leftovers
    ):
        errors.append("leftover_recipe_ids must contain only FDP-NNNN IDs")
        declared_leftovers = []

    card_method = recipe_card_value(body, "Cooking method")
    if card_method is None:
        errors.append("recipe card must report a cooking method")
    elif isinstance(cooking_method, str) and slugify(cooking_method) not in slugify(card_method):
        errors.append("cooking_method does not match the recipe card")

    card_cook_minutes = reported_cook_minutes(body)
    if card_cook_minutes is None:
        errors.append("recipe card cook time must use minutes or hours")
    elif isinstance(cook_time_minutes, int) and card_cook_minutes != cook_time_minutes:
        errors.append(
            f"cook_time_minutes is {cook_time_minutes}, but recipe card minimum is "
            f"{card_cook_minutes}"
        )

    card_fiber = reported_fiber_grams(body)
    if card_fiber is None:
        errors.append("recipe card must report fiber as grams per serving")
    elif isinstance(fiber_grams, (int, float)) and card_fiber != fiber_grams:
        errors.append(f"fiber_grams is {fiber_grams}, but recipe card reports {card_fiber}")

    card_kid_reason = recipe_card_value(body, "Kid-friendly design")
    if card_kid_reason is None:
        errors.append("recipe card must report its kid-friendly design")
    elif isinstance(kid_friendly_reason, str) and card_kid_reason != kid_friendly_reason:
        errors.append("kid_friendly_reason does not match the recipe card")

    if isinstance(tags, list) and "mexican-monday" in tags:
        if protein not in MEXICAN_MONDAY_PROTEINS:
            errors.append(
                "mexican-monday recipes require chicken, turkey, beef, or seafood"
            )
        if not isinstance(fiber_grams, (int, float)) or fiber_grams < 8:
            errors.append("mexican-monday recipes require at least 8 fiber grams")

    if cooking_method == "slow-cooker" and (
        not isinstance(cook_time_minutes, int) or cook_time_minutes < 180
    ):
        errors.append("slow-cooker recipes require at least 180 cook_time_minutes")

    if "summer" in seasons:
        searchable = " ".join([str(name), *(str(tag) for tag in tags)]).lower()
        found = sorted(
            word for word in SUMMER_FORBIDDEN_WORDS
            if re.search(rf"\b{re.escape(word)}\b", searchable)
        )
        if found:
            errors.append(f"summer recipes cannot be soup, chili, or stew: {', '.join(found)}")

    leftover_body = section(body, "## Leftover Plan")
    body_leftovers = set(RECIPE_ID_PATTERN.findall(leftover_body))
    declared_set = set(declared_leftovers)
    for leftover_id in sorted(declared_set | body_leftovers):
        if leftover_id == recipe_id:
            errors.append(f"leftover reference cannot point to itself: {leftover_id}")
        elif leftover_id not in all_recipe_ids:
            errors.append(f"leftover recipe does not exist: {leftover_id}")
    for leftover_id in sorted(body_leftovers - declared_set):
        errors.append(f"leftover plan ID missing from leftover_recipe_ids: {leftover_id}")
    for leftover_id in sorted(declared_set - body_leftovers):
        errors.append(f"leftover_recipe_ids ID missing from Leftover Plan: {leftover_id}")

    return errors


def validate_recipe(path: Path) -> tuple[str | None, dict, str, list[str]]:
    errors: list[str] = []
    try:
        metadata, body = split_recipe(path)
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        return None, {}, "", [str(exc)]

    missing = REQUIRED_FIELDS - metadata.keys()
    if missing:
        errors.append(f"missing metadata: {', '.join(sorted(missing))}")

    recipe_id = metadata.get("id")
    if not isinstance(recipe_id, str) or not re.fullmatch(r"FDP-\d{4}", recipe_id):
        errors.append("id must match FDP-NNNN")

    expected_slug = slugify(str(metadata.get("name", "")))
    if path.stem != expected_slug:
        errors.append(f"filename should be {expected_slug}.md")

    if metadata.get("status") not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")
    if not isinstance(metadata.get("revision"), int) or metadata.get("revision", 0) < 1:
        errors.append("revision must be a positive integer")
    if not isinstance(metadata.get("servings"), int) or metadata.get("servings", 0) < 1:
        errors.append("servings must be a positive integer")
    if not isinstance(metadata.get("tags"), list) or not metadata.get("tags"):
        errors.append("tags must be a non-empty array")

    for heading in REQUIRED_HEADINGS:
        if heading not in body:
            errors.append(f"missing heading: {heading}")

    current_revision = metadata.get("revision")
    if isinstance(current_revision, int) and not re.search(
        rf"(?m)^\|\s*{current_revision}\s*\|", section(body, "## Revision History")
    ):
        errors.append(f"revision history has no row for revision {current_revision}")

    ratings = rating_values(body)
    if metadata.get("ratings_count") != len(ratings):
        errors.append("ratings_count does not match Ratings table")
    expected_average = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    if metadata.get("rating_average") != expected_average:
        errors.append(f"rating_average should be {expected_average}")

    seasonings = section(body, "### Seasonings", "###")
    directions = re.sub(r"\s+", " ", section(body, "## Directions").lower())
    for seasoning in SEASONING_PATTERN.findall(seasonings):
        normalized_seasoning = re.sub(r"\s+", " ", seasoning.lower())
        if normalized_seasoning not in directions:
            errors.append(f"seasoning not named in directions: {seasoning}")

    return recipe_id if isinstance(recipe_id, str) else None, metadata, body, errors


def main() -> int:
    failures: list[str] = []
    seen_ids: dict[str, Path] = {}
    parsed_recipes: list[tuple[Path, dict, str]] = []
    recipe_paths = sorted(
        path for path in RECIPES.glob("*.md") if not path.name.startswith("_")
        and path.name not in {"README.md", "index.md"}
    )

    for path in recipe_paths:
        recipe_id, metadata, body, errors = validate_recipe(path)
        if recipe_id in seen_ids:
            errors.append(f"duplicate id also used by {seen_ids[recipe_id].name}")
        elif recipe_id:
            seen_ids[recipe_id] = path
        parsed_recipes.append((path, metadata, body))
        failures.extend(f"{path.name}: {error}" for error in errors)

    all_recipe_ids = set(seen_ids)
    for path, metadata, body in parsed_recipes:
        failures.extend(
            f"{path.name}: {error}"
            for error in semantic_errors(metadata, body, all_recipe_ids)
        )

    index = (RECIPES / "index.md").read_text(encoding="utf-8")
    for recipe_id, path in seen_ids.items():
        if recipe_id not in index or f"({path.name})" not in index:
            failures.append(f"index.md: missing or incorrect entry for {recipe_id}")

    if failures:
        print("Recipe validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        f"Validated {len(recipe_paths)} recipes against structural and semantic rules."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
