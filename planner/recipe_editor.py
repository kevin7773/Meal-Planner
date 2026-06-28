from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from planner.constants import ROOT
from scripts.validate_recipes import (
    VALID_PROTEINS,
    VALID_SEASONS,
    semantic_errors,
    slugify,
    split_recipe,
    validate_recipe,
)


VALID_KID_REASONS = {
    "Gray Loves It": 4,
    "Both children like/love it": 5,
    "One of Kellan's Favorites": 4,
    "Not kid friendly - for the parents only": 1,
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
VALID_MEAL_SCOPES = {"complete-meal", "entree"}
CONTROLLED_TAGS = {
    *VALID_PROTEINS,
    *VALID_SEASONS,
    *VALID_METHODS,
}


def imported_recipes(root: Path = ROOT) -> list[dict]:
    records = []
    for path in sorted((root / "recipes").glob("*.md")):
        if path.name.startswith("_") or path.name in {
            "README.md",
            "index.md",
        }:
            continue
        try:
            metadata, body = split_recipe(path)
        except ValueError:
            continue
        if "imported" not in metadata.get("tags", []):
            continue
        records.append(recipe_payload(path, metadata, body))
    return sorted(records, key=lambda item: item["id"])


def find_imported_recipe(recipe_id: str, root: Path = ROOT) -> dict:
    for recipe in imported_recipes(root):
        if recipe["id"] == recipe_id:
            return recipe
    raise ValueError(f"Imported recipe not found: {recipe_id}")


def recipe_payload(path: Path, metadata: dict, body: str) -> dict:
    prep_match = re.search(
        r"(?mi)^-\s+\*\*Active prep:\*\*\s*(\d+)\s+minutes?\s*$",
        body,
    )
    kid_reason = str(metadata.get("kid_friendly_reason", ""))
    return {
        "id": metadata["id"],
        "name": metadata["name"],
        "revision": metadata["revision"],
        "status": metadata["status"],
        "protein": metadata["protein"],
        "meal_scope": metadata.get("meal_scope", "complete-meal"),
        "prep_minutes": int(prep_match.group(1)) if prep_match else 0,
        "cook_minutes": metadata["cook_time_minutes"],
        "fiber_grams": metadata["fiber_grams"],
        "estimated_cost_usd": metadata["estimated_cost_usd"],
        "kid_friendly_score": metadata["kid_friendly_score"],
        "kid_friendly_reason": kid_reason,
        "kid_reason_is_current": kid_reason in VALID_KID_REASONS,
        "cooking_method": metadata["cooking_method"],
        "seasons": metadata["seasons"],
        "source": metadata.get("source", "Unknown import source"),
        "path": str(path),
        "card_sections": {
            "ingredients": _body_section(
                body,
                "## Ingredients",
                "## Directions",
            ),
            "directions": _body_section(
                body,
                "## Directions",
                "## Leftover Plan",
            ),
        },
    }


def update_imported_recipe(
    recipe_id: str,
    *,
    name: str,
    protein: str,
    meal_scope: str,
    prep_minutes: int,
    cook_minutes: int,
    fiber_grams: float,
    estimated_cost_usd: float,
    kid_friendly_reason: str,
    cooking_method: str,
    seasons: list[str],
    card_sections: dict[str, str] | None = None,
    change_note: str = "Updated imported recipe metadata",
    root: Path = ROOT,
) -> tuple[int, Path]:
    current = find_imported_recipe(recipe_id, root)
    original_path = Path(current["path"])
    original_text = original_path.read_text(encoding="utf-8")
    metadata, _ = split_recipe(original_path)
    index_path = root / "recipes" / "index.md"
    original_index = index_path.read_text(encoding="utf-8")

    name = name.strip()
    change_note = _safe_table_text(change_note)
    if not name:
        raise ValueError("Recipe name is required")
    if protein not in VALID_PROTEINS:
        raise ValueError(f"Protein must be one of {sorted(VALID_PROTEINS)}")
    if meal_scope not in VALID_MEAL_SCOPES:
        raise ValueError(
            f"Meal scope must be one of {sorted(VALID_MEAL_SCOPES)}"
        )
    if cooking_method not in VALID_METHODS:
        raise ValueError(
            f"Cooking method must be one of {sorted(VALID_METHODS)}"
        )
    if kid_friendly_reason not in VALID_KID_REASONS:
        raise ValueError("Select a current kid-friendly reason")
    if not seasons or set(seasons) - VALID_SEASONS:
        raise ValueError(
            f"Seasons must contain only {sorted(VALID_SEASONS)}"
        )
    if prep_minutes < 0 or cook_minutes < 0:
        raise ValueError("Prep and cook times cannot be negative")
    if cooking_method == "slow-cooker" and cook_minutes < 180:
        raise ValueError(
            "Slow-cooker recipes require at least 180 cook minutes"
        )
    if fiber_grams < 0 or estimated_cost_usd < 0:
        raise ValueError("Fiber and estimated cost cannot be negative")

    revision = int(metadata["revision"]) + 1
    today = dt.date.today().isoformat()
    target_path = root / "recipes" / f"{slugify(name)}.md"
    if target_path != original_path and target_path.exists():
        raise ValueError(f"Recipe file already exists: {target_path.name}")

    tags = sorted(
        {
            *(
                tag
                for tag in metadata.get("tags", [])
                if tag not in CONTROLLED_TAGS
            ),
            *seasons,
            protein,
            cooking_method,
            "imported",
        }
    )
    updates = {
        "name": json.dumps(name, ensure_ascii=True),
        "revision": str(revision),
        "updated": json.dumps(today),
        "protein": json.dumps(protein),
        "meal_scope": json.dumps(meal_scope),
        "fiber_grams": f"{fiber_grams:g}",
        "estimated_cost_usd": f"{estimated_cost_usd:g}",
        "kid_friendly_score": str(
            VALID_KID_REASONS[kid_friendly_reason]
        ),
        "kid_friendly_reason": json.dumps(
            kid_friendly_reason,
            ensure_ascii=True,
        ),
        "cooking_method": json.dumps(cooking_method),
        "cook_time_minutes": str(cook_minutes),
        "seasons": json.dumps(seasons),
        "tags": json.dumps(tags),
    }
    content = original_text
    for field, value in updates.items():
        content = _set_front_matter(content, field, value)

    content = re.sub(
        r"(?m)^# .+$",
        f"# {name}",
        content,
        count=1,
    )
    card_updates = {
        "Active prep": f"{prep_minutes} minutes",
        "Cook time": f"{cook_minutes} minutes",
        "Cooking method": cooking_method.replace("-", " ").title(),
        "Estimated fiber": f"{fiber_grams:g} grams per serving",
        "Kid-friendly design": kid_friendly_reason,
        "Best seasons": ", ".join(
            season.title() for season in seasons
        ),
    }
    for label, value in card_updates.items():
        content = _set_card_value(content, label, value)
    if card_sections is not None:
        ingredients = _editable_card_section(
            card_sections,
            "ingredients",
        )
        directions = _editable_card_section(
            card_sections,
            "directions",
        )
        content = _set_body_section(
            content,
            "## Ingredients",
            "## Directions",
            ingredients,
        )
        content = _set_body_section(
            content,
            "## Directions",
            "## Leftover Plan",
            directions,
        )
    content = _add_revision_row(
        content,
        revision,
        today,
        metadata["status"],
        change_note or "Updated imported recipe metadata",
    )
    updated_index = _update_index(
        original_index,
        recipe_id,
        name,
        target_path.name,
        revision,
        metadata["status"],
    )

    try:
        target_path.write_text(content, encoding="utf-8", newline="\n")
        if target_path != original_path:
            original_path.unlink()
        index_path.write_text(
            updated_index,
            encoding="utf-8",
            newline="\n",
        )
        parsed_id, parsed_metadata, body, errors = validate_recipe(
            target_path
        )
        all_ids = {
            recipe["id"]
            for recipe in imported_recipes(root)
        }
        for path in (root / "recipes").glob("*.md"):
            match = re.search(
                r'(?m)^id = "(FDP-\d{4})"$',
                path.read_text(encoding="utf-8"),
            )
            if match:
                all_ids.add(match.group(1))
        errors.extend(
            semantic_errors(parsed_metadata, body, all_ids)
        )
        if parsed_id != recipe_id or errors:
            raise ValueError("; ".join(errors))
    except Exception:
        if target_path != original_path:
            target_path.unlink(missing_ok=True)
        original_path.write_text(
            original_text,
            encoding="utf-8",
            newline="\n",
        )
        index_path.write_text(
            original_index,
            encoding="utf-8",
            newline="\n",
        )
        raise
    return revision, target_path


def _body_section(
    body: str,
    heading: str,
    next_heading: str,
) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}\s*\n(.*?)(?=^{re.escape(next_heading)}\s*$)",
        body,
    )
    if match is None:
        raise ValueError(f"Recipe body is missing {heading}")
    return match.group(1).strip()


def _editable_card_section(
    sections: dict[str, str],
    name: str,
) -> str:
    value = str(sections.get(name, "")).replace("\r\n", "\n").strip()
    if not value:
        raise ValueError(f"Recipe card {name} cannot be empty")
    if re.search(r"(?m)^##\s+", value):
        raise ValueError(
            f"Recipe card {name} cannot add top-level recipe sections"
        )
    return value


def _set_body_section(
    content: str,
    heading: str,
    next_heading: str,
    value: str,
) -> str:
    pattern = (
        rf"(?ms)(^{re.escape(heading)}\s*\n)"
        rf".*?(?=^{re.escape(next_heading)}\s*$)"
    )
    if re.search(pattern, content) is None:
        raise ValueError(f"Recipe body is missing {heading}")
    return re.sub(
        pattern,
        lambda match: match.group(1) + "\n" + value + "\n\n",
        content,
        count=1,
    )


def _set_front_matter(content: str, field: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(field)} = .+$"
    replacement = f"{field} = {value}"
    if re.search(pattern, content):
        return re.sub(pattern, replacement, content, count=1)
    closing = content.find("\n+++\n", 4)
    if closing < 0:
        raise ValueError("Recipe has invalid TOML front matter")
    return content[:closing] + f"\n{replacement}" + content[closing:]


def _set_card_value(content: str, label: str, value: str) -> str:
    pattern = rf"(?mi)^-\s+\*\*{re.escape(label)}:\*\*\s*.*$"
    replacement = f"- **{label}:** {value}"
    if not re.search(pattern, content):
        raise ValueError(f"Recipe card is missing {label}")
    return re.sub(pattern, replacement, content, count=1)


def _add_revision_row(
    content: str,
    revision: int,
    date: str,
    status: str,
    note: str,
) -> str:
    heading = content.find("## Revision History")
    if heading < 0:
        raise ValueError("Recipe is missing Revision History")
    separator = re.search(
        r"(?m)^\|\s*---:\s*\|\s*---\s*\|\s*---\s*\|\s*---\s*\|\s*$",
        content[heading:],
    )
    if separator is None:
        raise ValueError("Revision History table is malformed")
    insert_at = heading + separator.end()
    row = f"\n| {revision} | {date} | {status} | {note} |"
    return content[:insert_at] + row + content[insert_at:]


def _update_index(
    index: str,
    recipe_id: str,
    name: str,
    filename: str,
    revision: int,
    status: str,
) -> str:
    pattern = rf"(?m)^\|\s*{re.escape(recipe_id)}\s*\|.*$"
    match = re.search(pattern, index)
    if match is None:
        raise ValueError(f"Recipe index is missing {recipe_id}")
    cells = [cell.strip() for cell in match.group().split("|")]
    rating = cells[5] if len(cells) > 5 else "Unrated"
    last_served = cells[6] if len(cells) > 6 else "Never"
    row = (
        f"| {recipe_id} | [{name}]({filename}) | {revision} | "
        f"{status} | {rating} | {last_served} |"
    )
    return index[: match.start()] + row + index[match.end() :]


def _safe_table_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "/")).strip()
