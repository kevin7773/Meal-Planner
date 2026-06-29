from __future__ import annotations

import argparse
import datetime as dt
import html
import ipaddress
import json
import re
import socket
import sys
import tomllib
import urllib.parse
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

try:
    from planner.recipe_audit import write_recipe_audit
    from planner.recipe_cache import build_recipe_cache
    from scripts.inventory import validate_inventory
    from scripts.validate_recipes import validate_recipe
except ModuleNotFoundError:
    from planner.recipe_audit import write_recipe_audit
    from planner.recipe_cache import build_recipe_cache
    from inventory import validate_inventory
    from validate_recipes import validate_recipe


ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD_BYTES = 2_000_000


def safe_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("URL resolves to a private or non-public address")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RecipeHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_json_ld = False
        self.in_title = False
        self.json_ld: list[str] = []
        self.visible: list[str] = []
        self.title: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self.in_json_ld = True
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_json_ld = False
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_json_ld:
            self.json_ld.append(data)
        elif self.in_title:
            self.title.append(data)
        elif data.strip():
            self.visible.append(data.strip())


def fetch_url(url: str) -> str:
    safe_url(url)
    opener = urllib.request.build_opener(SafeRedirectHandler())
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FamilyDinnerPlanner/1.0 recipe importer"},
    )
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ValueError(f"Unsupported URL content type: {content_type}")
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Recipe page exceeds the 2 MB import limit")
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def find_recipe_node(value):
    if isinstance(value, list):
        for item in value:
            found = find_recipe_node(item)
            if found:
                return found
    if isinstance(value, dict):
        node_type = value.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "Recipe" in types:
            return value
        for key in ("@graph", "mainEntity", "itemListElement"):
            found = find_recipe_node(value.get(key))
            if found:
                return found
    return None


def duration_minutes(value: object) -> int:
    if not isinstance(value, str):
        return 0
    match = re.fullmatch(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?", value)
    if not match:
        return 0
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def instruction_text(value) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in re.split(r"\n+", value) if line.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(instruction_text(item))
        return result
    if isinstance(value, dict):
        if value.get("text"):
            return [str(value["text"]).strip()]
        return instruction_text(value.get("itemListElement", []))
    return []


def infer_cook_minutes(directions: list[str]) -> int:
    text = " ".join(directions).lower()
    hour_pattern = (
        r"(\d+(?:\s+\d+/\d+|\.\d+)?)\s*"
        r"(?:-|–|—|\?|to)\s*"
        r"(\d+(?:\s+\d+/\d+|\.\d+)?)\s*hours?"
    )
    match = re.search(r"low\s+for\s+" + hour_pattern, text)
    if not match:
        match = re.search(hour_pattern, text)
    if match:
        whole, fraction = (match.group(1).split() + ["0"])[:2]
        numerator, denominator = (
            fraction.split("/") if "/" in fraction else ("0", "1")
        )
        return round((float(whole) + int(numerator) / int(denominator)) * 60)
    match = re.search(r"(\d+)\s*(?:-|–|—|\?|to)\s*\d+\s*minutes?", text)
    return int(match.group(1)) if match else 0


def parse_html_recipe(text: str, source: str) -> dict:
    parser = RecipeHTMLParser()
    parser.feed(text)
    node = None
    for raw in parser.json_ld:
        try:
            node = find_recipe_node(json.loads(html.unescape(raw)))
        except json.JSONDecodeError:
            continue
        if node:
            break
    if node:
        ingredients = [str(item).strip() for item in node.get("recipeIngredient", [])]
        directions = instruction_text(node.get("recipeInstructions", []))
        nutrition = node.get("nutrition") if isinstance(node.get("nutrition"), dict) else {}
        fiber_match = re.search(r"\d+(?:\.\d+)?", str(nutrition.get("fiberContent", "")))
        cook_minutes = duration_minutes(node.get("cookTime"))
        return {
            "name": str(node.get("name") or "Imported Recipe").strip(),
            "servings": str(node.get("recipeYield") or "4"),
            "prep_minutes": duration_minutes(node.get("prepTime")),
            "cook_minutes": cook_minutes or infer_cook_minutes(directions),
            "fiber_grams": float(fiber_match.group()) if fiber_match else 0,
            "ingredients": ingredients,
            "directions": directions,
            "source": source,
            "parser": "schema.org Recipe JSON-LD",
        }
    title = " ".join(parser.title).strip() or "Imported Recipe"
    return parse_plain_text("\n".join([title, *parser.visible]), source)


def parse_plain_text(text: str, source: str) -> dict:
    lines = [html.unescape(line).strip() for line in text.splitlines()]
    nonempty = [line for line in lines if line]
    name = re.sub(r"^#+\s*", "", nonempty[0]) if nonempty else "Imported Recipe"
    ingredients: list[str] = []
    directions: list[str] = []
    mode = ""
    for line in lines[1:]:
        normalized = re.sub(r"[:#]+$", "", line).strip().lower()
        if normalized in {"ingredients", "ingredient"}:
            mode = "ingredients"
            continue
        if normalized in {"directions", "instructions", "method", "steps"}:
            mode = "directions"
            continue
        if not line:
            continue
        if mode == "ingredients":
            ingredients.append(re.sub(r"^[-*]\s*", "", line))
        elif mode == "directions":
            directions.append(re.sub(r"^\d+[.)]\s*", "", line))
    if not ingredients or not directions:
        raise ValueError(
            "Text import needs Ingredients and Directions/Instructions sections"
        )
    return {
        "name": name,
        "servings": "4",
        "prep_minutes": 0,
        "cook_minutes": infer_cook_minutes(directions),
        "fiber_grams": 0,
        "ingredients": ingredients,
        "directions": directions,
        "source": source,
        "parser": "plain text sections",
    }


def preview_source(source: str) -> dict:
    if re.match(r"^https?://", source, re.IGNORECASE):
        return parse_html_recipe(fetch_url(source), source)
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Recipe file not found: {path}")
    if path.stat().st_size > MAX_DOWNLOAD_BYTES:
        raise ValueError("Recipe file exceeds the 2 MB import limit")
    return parse_plain_text(path.read_text(encoding="utf-8"), str(path))


def preview_text(text: str) -> dict:
    if not text.strip():
        raise ValueError("Pasted recipe text is empty")
    if len(text.encode("utf-8")) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Pasted recipe exceeds the 2 MB import limit")
    return parse_plain_text(text, "pasted recipe text")


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def import_recipe(
    source: str,
    *,
    source_text: str | None = None,
    name: str,
    protein: str,
    meal_scope: str = "complete-meal",
    cooking_method: str,
    prep_minutes_override: int | None = None,
    cook_minutes_override: int | None = None,
    fiber_grams: float,
    estimated_cost_usd: float,
    kid_friendly_score: int,
    kid_friendly_reason: str,
    seasons: list[str],
    root: Path = ROOT,
) -> tuple[str, Path]:
    name = name.strip()
    kid_friendly_reason = kid_friendly_reason.strip()
    if not name:
        raise ValueError("Recipe name is required")
    if not kid_friendly_reason:
        raise ValueError("Kid-friendly reason is required")
    preview = preview_text(source_text) if source_text is not None else preview_source(source)
    ingredients = preview["ingredients"]
    directions = preview["directions"]
    if not ingredients or not directions:
        raise ValueError("Imported recipe must contain ingredients and directions")
    existing_ids = []
    for path in (root / "recipes").glob("*.md"):
        if path.name.startswith("_") or path.name in {"README.md", "index.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r'(?m)^id = "FDP-(\d{4})"$', text)
        if match:
            existing_ids.append(int(match.group(1)))
    number = max(existing_ids, default=0) + 1
    recipe_id = f"FDP-{number:04d}"
    slug = slugify(name)
    path = root / "recipes" / f"{slug}.md"
    if path.exists():
        raise ValueError(f"Recipe file already exists: {path.name}")
    today = dt.date.today().isoformat()
    servings_match = re.search(r"\d+", str(preview.get("servings", "4")))
    servings = int(servings_match.group()) if servings_match else 4
    prep_minutes = (
        int(prep_minutes_override)
        if prep_minutes_override is not None
        else int(preview.get("prep_minutes") or 0)
    )
    cook_minutes = (
        int(cook_minutes_override)
        if cook_minutes_override is not None
        else int(preview.get("cook_minutes") or 0)
    )
    if prep_minutes < 0 or cook_minutes < 0:
        raise ValueError("Prep and cook times cannot be negative")
    if cooking_method == "slow-cooker" and cook_minutes < 180:
        raise ValueError(
            "Slow-cooker recipes require at least 180 cook minutes. "
            "Add a duration to the directions or provide a cook-time override."
        )
    ingredient_lines = "\n".join(f"- {item}" for item in ingredients)
    direction_lines = "\n".join(
        f"{index}. {item}" for index, item in enumerate(directions, start=1)
    )
    tags = sorted({*seasons, protein, cooking_method, "imported"})
    revision_source = str(preview["source"]).replace("|", "/").replace("\n", " ")
    content = f"""+++
id = "{recipe_id}"
name = {toml_string(name)}
revision = 1
status = "candidate"
servings = {servings}
created = "{today}"
updated = "{today}"
rating_average = 0.0
ratings_count = 0
protein = "{protein}"
meal_scope = "{meal_scope}"
fiber_grams = {fiber_grams:g}
estimated_cost_usd = {estimated_cost_usd:g}
kid_friendly_score = {kid_friendly_score}
kid_friendly_reason = {toml_string(kid_friendly_reason)}
cooking_method = "{cooking_method}"
cook_time_minutes = {cook_minutes}
seasons = {json.dumps(seasons)}
leftover_recipe_ids = []
tags = {json.dumps(tags)}
source = {toml_string(preview["source"])}
+++

# {name}

## Recipe Card

- **Active prep:** {prep_minutes} minutes
- **Cook time:** {cook_minutes} minutes
- **Cooking method:** {cooking_method.replace("-", " ").title()}
- **Estimated fiber:** {fiber_grams:g} grams per serving
- **Kid-friendly design:** {kid_friendly_reason}
- **Best seasons:** {", ".join(season.title() for season in seasons)}
- **Schedule fit:** Imported candidate; review before scheduling

## Ingredients

### Main Ingredients

{ingredient_lines}

### Seasonings

- Review imported ingredients for seasoning classification

## Directions

{direction_lines}

## Leftover Plan

- Decide after the first family test.

## Family Notes

- **Verdict:** Imported candidate awaiting review
- **Keep:** Pending
- **Change next time:** Verify quantities, seasoning, and inventory mapping

## Ratings

| Date | Rating | Rater | Notes |
| --- | ---: | --- | --- |

## Revision History

| Revision | Date | Status | Change |
| ---: | --- | --- | --- |
| 1 | {today} | candidate | Imported from {revision_source} using {preview["parser"]} |
"""
    index_path = root / "recipes" / "index.md"
    requirements_path = root / "inventory" / "recipe-requirements.json"
    original_index = index_path.read_text(encoding="utf-8")
    original_requirements = requirements_path.read_text(encoding="utf-8")
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
        row = (
            f"| {recipe_id} | [{name}]({path.name}) | 1 | candidate | "
            "Unrated | Never |"
        )
        next_id_pattern = r"\*\*Next recipe ID:\*\* `FDP-\d{4}`"
        updated_index = re.sub(
            next_id_pattern,
            row + f"\n\n**Next recipe ID:** `FDP-{number + 1:04d}`",
            original_index,
        )
        index_path.write_text(updated_index, encoding="utf-8", newline="\n")
        requirements = json.loads(original_requirements)
        requirements["recipes"][recipe_id] = []
        requirements_path.write_text(
            json.dumps(requirements, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _, _, _, recipe_errors = validate_recipe(path)
        inventory_errors = validate_inventory(root)
        if recipe_errors or inventory_errors:
            raise ValueError("; ".join([*recipe_errors, *inventory_errors]))
        build_recipe_cache(root)
        write_recipe_audit(
            action="import",
            recipe_id=recipe_id,
            root=root,
            details={
                "name": name,
                "protein": protein,
                "meal_scope": meal_scope,
                "cooking_method": cooking_method,
                "source": str(preview["source"]),
                "parser": str(preview["parser"]),
                "path": path.name,
            },
        )
    except Exception:
        path.unlink(missing_ok=True)
        index_path.write_text(original_index, encoding="utf-8", newline="\n")
        requirements_path.write_text(
            original_requirements,
            encoding="utf-8",
            newline="\n",
        )
        raise
    return recipe_id, path


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or import a recipe.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preview_parser = subparsers.add_parser("preview")
    preview_source_group = preview_parser.add_mutually_exclusive_group(required=True)
    preview_source_group.add_argument("--source")
    preview_source_group.add_argument("--stdin", action="store_true")
    preview_parser.add_argument("--json", action="store_true")

    import_parser = subparsers.add_parser("apply")
    import_source_group = import_parser.add_mutually_exclusive_group(required=True)
    import_source_group.add_argument("--source")
    import_source_group.add_argument("--stdin", action="store_true")
    import_parser.add_argument("--name", required=True)
    import_parser.add_argument("--protein", required=True)
    import_parser.add_argument(
        "--meal-scope",
        choices=("entree", "complete-meal"),
        default="complete-meal",
    )
    import_parser.add_argument("--method", required=True)
    import_parser.add_argument("--prep-minutes", type=int)
    import_parser.add_argument("--cook-minutes", type=int)
    import_parser.add_argument("--fiber", required=True, type=float)
    import_parser.add_argument("--cost", required=True, type=float)
    import_parser.add_argument("--kid-score", required=True, type=int)
    import_parser.add_argument("--kid-reason", required=True)
    import_parser.add_argument("--seasons", required=True)
    args = parser.parse_args()

    try:
        if args.command == "preview":
            preview = preview_text(sys.stdin.read()) if args.stdin else preview_source(args.source)
            print(json.dumps(preview, indent=2) if args.json else preview["name"])
            return 0
        pasted_text = sys.stdin.read() if args.stdin else None
        recipe_id, path = import_recipe(
            args.source or "pasted recipe text",
            source_text=pasted_text,
            name=args.name,
            protein=args.protein,
            meal_scope=args.meal_scope,
            cooking_method=args.method,
            prep_minutes_override=args.prep_minutes,
            cook_minutes_override=args.cook_minutes,
            fiber_grams=args.fiber,
            estimated_cost_usd=args.cost,
            kid_friendly_score=args.kid_score,
            kid_friendly_reason=args.kid_reason,
            seasons=[item.strip() for item in args.seasons.split(",") if item.strip()],
        )
        print(f"{recipe_id}|{path}")
        return 0
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"Recipe import failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
