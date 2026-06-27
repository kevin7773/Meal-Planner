from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUSES = (
    "draft",
    "generated",
    "validated",
    "reviewed",
    "approved",
    "completed",
    "archived",
)
ALLOWED_TRANSITIONS = {
    "draft": {"generated"},
    "generated": {"validated", "draft"},
    "validated": {"reviewed", "draft"},
    "reviewed": {"approved", "draft"},
    "approved": {"completed", "draft"},
    "completed": {"archived", "draft"},
    "archived": set(),
}
HUMAN_STATES = {"reviewed", "approved"}
NON_HUMAN_ACTORS = {"ai", "automation", "codex"}
HISTORY_HEADING = "## Planning Status History"
HISTORY_ROW = re.compile(
    r"^\|\s*(draft|generated|validated|reviewed|approved|completed|archived)"
    r"\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|$"
)


class MenuStatusError(ValueError):
    pass


def split_menu(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++\n"):
        raise MenuStatusError("missing opening TOML front matter")
    try:
        raw_metadata, body = text[4:].split("\n+++\n", 1)
    except ValueError as exc:
        raise MenuStatusError("missing closing TOML front matter") from exc
    try:
        metadata = tomllib.loads(raw_metadata)
    except tomllib.TOMLDecodeError as exc:
        raise MenuStatusError(f"invalid TOML front matter: {exc}") from exc
    return metadata, body


def parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def history_rows(body: str) -> list[tuple[str, str, str, str]]:
    if HISTORY_HEADING not in body:
        return []
    rows: list[tuple[str, str, str, str]] = []
    for line in body.splitlines():
        match = HISTORY_ROW.match(line.strip())
        if match:
            rows.append(tuple(value.strip() for value in match.groups()))
    return rows


def validate_menu(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        metadata, body = split_menu(path)
    except MenuStatusError as exc:
        return [str(exc)]

    week_of = metadata.get("week_of")
    try:
        week_date = dt.date.fromisoformat(week_of) if isinstance(week_of, str) else None
    except ValueError:
        week_date = None
    if week_date is None:
        errors.append("week_of must be an ISO date")
    elif week_date.weekday() != 0:
        errors.append("week_of must be a Monday")

    status = metadata.get("status")
    if status not in STATUSES:
        errors.append(f"status must be one of {list(STATUSES)}")
    if parse_timestamp(metadata.get("status_updated_at")) is None:
        errors.append("status_updated_at must be a timezone-aware ISO timestamp")

    rows = history_rows(body)
    if not rows:
        errors.append("Planning Status History must contain at least one status row")
    else:
        if rows[0][0] != "draft":
            errors.append("Planning Status History must begin with draft")
        if status in STATUSES and rows[-1][0] != status:
            errors.append("latest history status must match front matter status")
        for row_status, timestamp, actor, note in rows:
            if parse_timestamp(timestamp) is None:
                errors.append(f"history timestamp is invalid for {row_status}")
            if not actor:
                errors.append(f"history actor is missing for {row_status}")
            if not note:
                errors.append(f"history note is missing for {row_status}")
        for previous, current in zip(rows, rows[1:]):
            if current[0] not in ALLOWED_TRANSITIONS[previous[0]]:
                errors.append(f"invalid history transition: {previous[0]} -> {current[0]}")

    return errors


def safe_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "/")).strip()


def replace_metadata(text: str, name: str, value: str) -> str:
    pattern = rf'(?m)^{re.escape(name)} = ".*"$'
    replacement = f'{name} = "{value}"'
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise MenuStatusError(f"missing {name} metadata")
    return updated


def run_recipe_validation() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_recipes.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stdout.strip() or result.stderr.strip()
        raise MenuStatusError(f"recipe validation failed:\n{detail}")


def transition_menu(
    path: Path,
    target: str,
    actor: str,
    note: str,
    *,
    now: dt.datetime | None = None,
    run_validators: bool = True,
    allow_reopen: bool = False,
) -> None:
    errors = validate_menu(path)
    if errors:
        raise MenuStatusError("; ".join(errors))

    metadata, _ = split_menu(path)
    current = metadata["status"]
    if target not in STATUSES:
        raise MenuStatusError(f"unknown target status: {target}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise MenuStatusError(f"transition not allowed: {current} -> {target}")
    if current == "completed" and target == "draft" and not allow_reopen:
        raise MenuStatusError(
            "reopening a completed week requires the explicit reopen option"
        )

    actor = safe_cell(actor)
    note = safe_cell(note)
    if not actor:
        raise MenuStatusError("actor is required")
    if target in HUMAN_STATES and actor.lower() in NON_HUMAN_ACTORS:
        raise MenuStatusError(f"{target} must be attributed to a human reviewer")
    if target == "draft" and not note:
        raise MenuStatusError("returning to draft requires a reason")
    if target in {"completed", "archived"} and not note:
        raise MenuStatusError(f"{target} requires an audit note")

    if target == "validated" and run_validators:
        run_recipe_validation()

    timestamp = (now or dt.datetime.now(dt.timezone.utc)).astimezone(
        dt.timezone.utc
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    text = path.read_text(encoding="utf-8")
    text = replace_metadata(text, "status", target)
    text = replace_metadata(text, "status_updated_at", timestamp)
    row = f"| {target} | {timestamp} | {actor} | {note or 'Status advanced'} |"
    text = text.rstrip() + "\n" + row + "\n"

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)

    post_errors = validate_menu(path)
    if post_errors:
        raise MenuStatusError("transition produced invalid menu: " + "; ".join(post_errors))


def check_all() -> int:
    menu_paths = sorted((ROOT / "menus").glob("**/*.md"))
    failures: list[str] = []
    for path in menu_paths:
        failures.extend(f"{path}: {error}" for error in validate_menu(path))
    if failures:
        print("Weekly menu validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Validated planning status for {len(menu_paths)} weekly menus.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and advance weekly menu status.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("menu", type=Path)

    subparsers.add_parser("check-all")

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("menu", type=Path)
    transition_parser.add_argument("status", choices=STATUSES)
    transition_parser.add_argument("--actor", required=True)
    transition_parser.add_argument("--note", default="")
    transition_parser.add_argument("--reopen", action="store_true")

    args = parser.parse_args()
    if args.command == "check-all":
        return check_all()
    if args.command == "check":
        errors = validate_menu(args.menu)
        if errors:
            for error in errors:
                print(f"- {error}")
            return 1
        metadata, _ = split_menu(args.menu)
        print(f"{args.menu}: {metadata['status']}")
        return 0

    try:
        transition_menu(
            args.menu,
            args.status,
            args.actor,
            args.note,
            allow_reopen=args.reopen,
        )
    except MenuStatusError as exc:
        print(f"Unable to update menu status: {exc}", file=sys.stderr)
        return 1
    print(f"{args.menu}: advanced to {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
