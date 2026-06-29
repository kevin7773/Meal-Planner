from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from planner.constants import ROOT
from scripts.validate_recipes import split_recipe


SCHEMA_VERSION = 1
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")


def recipe_image_metadata_path(root: Path = ROOT) -> Path:
    return root / "planner-data" / "recipe-images.json"


def load_recipe_image_metadata(root: Path = ROOT) -> dict:
    path = recipe_image_metadata_path(root)
    if not path.exists():
        return build_recipe_image_metadata(root)
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != SCHEMA_VERSION:
        return build_recipe_image_metadata(root)
    return document


def build_recipe_image_metadata(root: Path = ROOT) -> dict:
    path = recipe_image_metadata_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    recipe_names = recipe_name_by_id(root)
    recipes = {}
    for recipe_id, image_path in recipe_image_index(root).items():
        recipes[recipe_id] = default_image_record(
            recipe_id=recipe_id,
            image_path=image_path,
            recipe_name=recipe_names.get(recipe_id, recipe_id),
            root=root,
            source_type="placeholder-generated",
            source="placeholder-library",
            prompt=f"Placeholder photo for {recipe_names.get(recipe_id, recipe_id)}",
        )
    document = {"schema_version": SCHEMA_VERSION, "recipes": recipes}
    path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def record_recipe_image(
    recipe_id: str,
    *,
    root: Path = ROOT,
    source_type: str,
    source: str,
    prompt: str | None = None,
    primary: bool = True,
    captured_on: str | None = None,
) -> dict:
    images = recipe_image_index(root)
    image_path = images.get(recipe_id)
    if image_path is None:
        raise ValueError(f"No image file found for recipe {recipe_id}")
    names = recipe_name_by_id(root)
    document = load_recipe_image_metadata(root)
    document.setdefault("recipes", {})
    document["recipes"][recipe_id] = default_image_record(
        recipe_id=recipe_id,
        image_path=image_path,
        recipe_name=names.get(recipe_id, recipe_id),
        root=root,
        source_type=source_type,
        source=source,
        prompt=prompt,
        primary=primary,
        captured_on=captured_on,
    )
    path = recipe_image_metadata_path(root)
    path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document["recipes"][recipe_id]


def recipe_image_index(root: Path = ROOT) -> dict[str, Path]:
    result: dict[str, Path] = {}
    assets_root = root / "assets" / "recipes"
    if not assets_root.exists():
        return result
    for path in sorted(assets_root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        result[path.stem] = path
    return result


def recipe_name_by_id(root: Path = ROOT) -> dict[str, str]:
    result = {}
    excluded = {"README.md", "index.md", "_template.md"}
    for recipe_path in sorted((root / "recipes").glob("*.md")):
        if recipe_path.name in excluded or recipe_path.name.startswith("_"):
            continue
        metadata, _ = split_recipe(recipe_path)
        result[metadata["id"]] = metadata["name"]
    return result


def default_image_record(
    *,
    recipe_id: str,
    image_path: Path,
    recipe_name: str,
    root: Path,
    source_type: str,
    source: str,
    prompt: str | None = None,
    primary: bool = True,
    captured_on: str | None = None,
) -> dict:
    stat = image_path.stat()
    return {
        "recipe_id": recipe_id,
        "primary": bool(primary),
        "relative_path": str(image_path.relative_to(root)).replace("\\", "/"),
        "filename": image_path.name,
        "source_type": source_type,
        "source": source,
        "prompt": prompt or f"Recipe image for {recipe_name}",
        "captured_on": captured_on,
        "updated": dt.datetime.fromtimestamp(
            stat.st_mtime,
            tz=dt.timezone.utc,
        ).isoformat().replace("+00:00", "Z"),
    }
