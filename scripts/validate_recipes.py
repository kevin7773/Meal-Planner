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


def validate_recipe(path: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    try:
        metadata, body = split_recipe(path)
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        return None, [str(exc)]

    missing = REQUIRED_FIELDS - metadata.keys()
    if missing:
        errors.append(f"missing metadata: {', '.join(sorted(missing))}")

    recipe_id = metadata.get("id")
    if not isinstance(recipe_id, str) or not re.fullmatch(r"FDP-\d{4}", recipe_id):
        errors.append("id must match FDP-NNNN")

    expected_slug = re.sub(r"[^a-z0-9]+", "-", str(metadata.get("name", "")).lower()).strip("-")
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

    return recipe_id if isinstance(recipe_id, str) else None, errors


def main() -> int:
    failures: list[str] = []
    seen_ids: dict[str, Path] = {}
    recipe_paths = sorted(
        path for path in RECIPES.glob("*.md") if not path.name.startswith("_")
        and path.name not in {"README.md", "index.md"}
    )

    for path in recipe_paths:
        recipe_id, errors = validate_recipe(path)
        if recipe_id in seen_ids:
            errors.append(f"duplicate id also used by {seen_ids[recipe_id].name}")
        elif recipe_id:
            seen_ids[recipe_id] = path
        failures.extend(f"{path.name}: {error}" for error in errors)

    index = (RECIPES / "index.md").read_text(encoding="utf-8")
    for recipe_id, path in seen_ids.items():
        if recipe_id not in index or f"({path.name})" not in index:
            failures.append(f"index.md: missing or incorrect entry for {recipe_id}")

    if failures:
        print("Recipe validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Validated {len(recipe_paths)} recipes with unique IDs and consistent metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
