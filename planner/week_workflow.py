from __future__ import annotations

import datetime as dt
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from planner.constants import DAYS, ROOT
from scripts.build_week_artifacts import build_artifacts
from scripts.menu_status import split_menu, transition_menu


EMAIL_FILENAMES = (
    "email-1-mon-tue.md",
    "email-2-wed-thu-fri.md",
    "email-3-sat-sun.md",
)


def week_paths(
    week_of: dt.date,
    root: Path = ROOT,
) -> dict[str, Path | tuple[Path, ...]]:
    email_root = (
        root / "email-outputs" / str(week_of.year) / week_of.isoformat()
    )
    return {
        "menu": root / "menus" / str(week_of.year) / f"{week_of.isoformat()}.md",
        "grocery": (
            root
            / "grocery-lists"
            / str(week_of.year)
            / f"{week_of.isoformat()}-grocery-list.md"
        ),
        "email_root": email_root,
        "emails": tuple(email_root / name for name in EMAIL_FILENAMES),
        "delivery_log": email_root / "delivery-status.json",
    }


def markdown_to_text(text: str) -> str:
    text = re.sub(r"(?ms)\A\+\+\+\n.*?\n\+\+\+\n?", "", text)
    text = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"(?m)^\|(?:\s*:?-+:?\s*\|)+\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _field(section: str, label: str) -> str | None:
    match = re.search(
        rf"(?im)^(?:-\s+)?\*\*{re.escape(label)}:\*\*\s*(.+?)\s*$",
        section,
    )
    return match.group(1).strip() if match else None


def human_readable_menu(menu_text: str) -> str:
    metadata, _ = split_menu_text(menu_text)
    lines = [
        "WEEKLY DINNER PLAN",
        f"Week of: {metadata['week_of']}",
        f"Status: {metadata['status'].title()}",
    ]
    diner_match = re.search(
        r"(?im)^\*\*Diner Schedule:\*\*\s*(.+?)\s*$",
        menu_text,
    )
    if diner_match:
        lines.append(f"Diners: {diner_match.group(1).strip()}")
    lines.append("")

    day_pattern = re.compile(
        r"(?m)^## (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),"
        r"\s*(.+?)\s*-\s*(.+?)\s*$"
    )
    matches = list(day_pattern.finditer(menu_text))
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(menu_text)
        )
        section = menu_text[match.start() : end]
        lines.append(f"{match.group(1).upper()} - {match.group(3).strip()}")
        for label in (
            "Recipe",
            "Planned Diners",
            "Cooking Method",
            "Estimated Fiber",
            "Kid-Friendly Design",
            "Suggested Sides",
            "Kids' Quick Meal",
            "Meal Override",
            "Override Note",
        ):
            value = _field(section, label)
            if value:
                lines.append(f"  {label}: {markdown_to_text(value)}")
        if not _field(section, "Kids' Quick Meal"):
            quick_meal = re.search(
                r"(?ms)^### Kids' Quick Meal\s+(.+?)(?=^#{2,3} |\Z)",
                section,
            )
            if quick_meal:
                lines.append(
                    "  Kids' Quick Meal: "
                    + markdown_to_text(quick_meal.group(1))
                    .removeprefix("- ")
                )
        if not _field(section, "Suggested Sides"):
            sides = re.search(
                r"(?ms)^### Suggested Sides\s+(.+?)(?=^#{2,3} |\Z)",
                section,
            )
            if sides:
                lines.append(
                    "  Suggested Sides: "
                    + markdown_to_text(sides.group(1)).replace("\n", "; ")
                )
        lines.append("")

    summary = re.search(
        r"(?ms)^## Dry Run Summary\s*(.*?)(?=^## |\Z)",
        menu_text,
    )
    if summary:
        lines.extend(
            [
                "WEEKLY SUMMARY",
                markdown_to_text(summary.group(1)),
                "",
            ]
        )
    return "\n".join(lines).strip()


def split_menu_text(text: str) -> tuple[dict, str]:
    if not text.startswith("+++\n") or "\n+++\n" not in text[4:]:
        raise ValueError("menu is missing TOML front matter")
    import tomllib

    front_matter, body = text[4:].split("\n+++\n", 1)
    return tomllib.loads(front_matter), body


def _draft_recipe_ids(menu_text: str) -> list[str]:
    recipe_ids = re.findall(
        r"(?im)^\*\*Recipe:\*\*\s+([A-Z0-9-]+)",
        menu_text,
    )
    if len(recipe_ids) != 7:
        raise ValueError(
            f"weekly menu must contain seven recipe IDs; found {len(recipe_ids)}"
        )
    return [
        "OVERRIDE" if recipe_id.startswith("OVERRIDE-") else recipe_id
        for recipe_id in recipe_ids
    ]


def inspect_week(
    week_of: dt.date,
    root: Path = ROOT,
) -> dict:
    paths = week_paths(week_of, root)
    menu_path = paths["menu"]
    assert isinstance(menu_path, Path)
    if not menu_path.exists():
        raise FileNotFoundError(f"No weekly menu exists for {week_of.isoformat()}")

    menu_text = menu_path.read_text(encoding="utf-8")
    metadata, _ = split_menu(menu_path)
    grocery_path = paths["grocery"]
    email_paths = paths["emails"]
    assert isinstance(grocery_path, Path)
    assert isinstance(email_paths, tuple)
    grocery_text = (
        markdown_to_text(grocery_path.read_text(encoding="utf-8"))
        if grocery_path.exists()
        else "Grocery list has not been generated."
    )
    email_sections = []
    for path in email_paths:
        if path.exists():
            email_sections.append(
                f"{path.name}\n{'=' * len(path.name)}\n"
                + markdown_to_text(path.read_text(encoding="utf-8"))
            )
    return {
        "week_of": week_of.isoformat(),
        "status": metadata["status"],
        "menu_path": str(menu_path),
        "grocery_path": str(grocery_path),
        "email_paths": [str(path) for path in email_paths],
        "menu_summary": human_readable_menu(menu_text),
        "grocery_text": grocery_text,
        "email_text": (
            "\n\n".join(email_sections)
            if email_sections
            else "Email drafts have not been generated."
        ),
        "raw_menu": menu_text,
        "grocery_exists": grocery_path.exists(),
        "email_drafts_complete": all(path.exists() for path in email_paths),
    }


def generate_review_package(
    week_of: dt.date,
    *,
    root: Path = ROOT,
) -> dict:
    paths = week_paths(week_of, root)
    menu_path = paths["menu"]
    grocery_path = paths["grocery"]
    assert isinstance(menu_path, Path)
    assert isinstance(grocery_path, Path)
    metadata, _ = split_menu(menu_path)
    if metadata["status"] == "generated":
        package = inspect_week(week_of, root)
        if not package["grocery_exists"] or not package["email_drafts_complete"]:
            raise ValueError(
                "generated package is missing grocery or email artifacts"
            )
        transition_menu(
            menu_path,
            "validated",
            "Meal Planner",
            "Generated review package passed automated validation",
            root=root,
        )
        return inspect_week(week_of, root)
    if metadata["status"] != "draft":
        raise ValueError(
            f"review package requires draft status, found {metadata['status']}"
        )
    menu_text = menu_path.read_text(encoding="utf-8")
    build_artifacts(
        menu_path,
        grocery_path,
        _draft_recipe_ids(menu_text),
        metadata.get("planned_diners"),
    )
    transition_menu(
        menu_path,
        "generated",
        "Meal Planner",
        "Menu, grocery list, and three email drafts generated in Plan Week",
        root=root,
        run_validators=False,
    )
    transition_menu(
        menu_path,
        "validated",
        "Meal Planner",
        "Generated review package passed automated validation",
        root=root,
    )
    return inspect_week(week_of, root)


def approve_review_package(
    week_of: dt.date,
    *,
    actor: str,
    root: Path = ROOT,
) -> dict:
    paths = week_paths(week_of, root)
    menu_path = paths["menu"]
    assert isinstance(menu_path, Path)
    metadata, _ = split_menu(menu_path)
    if metadata["status"] == "validated":
        transition_menu(
            menu_path,
            "reviewed",
            actor,
            "Human reviewed menu, grocery list, and email drafts in Plan Week",
            root=root,
            run_validators=False,
        )
        metadata, _ = split_menu(menu_path)
    if metadata["status"] != "reviewed":
        raise ValueError(
            "approval requires validated or reviewed status, "
            f"found {metadata['status']}"
        )
    transition_menu(
        menu_path,
        "approved",
        actor,
        "Human explicitly approved the weekly package for email delivery",
        root=root,
        run_validators=False,
    )
    return inspect_week(week_of, root)


def parse_email_draft(path: Path) -> tuple[list[str], str, str]:
    text = path.read_text(encoding="utf-8")
    to_match = re.search(r"(?im)^To:\s*(.+?)\s*$", text)
    subject_match = re.search(r"(?im)^Subject:\s*(.+?)\s*$", text)
    if not to_match or not subject_match:
        raise ValueError(f"{path.name} is missing To or Subject")
    recipients = [
        item.strip()
        for item in re.split(r"[,;]", to_match.group(1))
        if item.strip()
    ]
    if not recipients:
        raise ValueError(f"{path.name} has no recipients")
    body = text[subject_match.end() :].strip()
    return recipients, subject_match.group(1).strip(), body


def _write_delivery_log(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def send_approved_emails(
    week_of: dt.date,
    *,
    actor: str,
    sender: str,
    password: str,
    root: Path = ROOT,
    smtp_factory=smtplib.SMTP_SSL,
) -> dict:
    paths = week_paths(week_of, root)
    menu_path = paths["menu"]
    email_paths = paths["emails"]
    delivery_path = paths["delivery_log"]
    assert isinstance(menu_path, Path)
    assert isinstance(email_paths, tuple)
    assert isinstance(delivery_path, Path)
    metadata, _ = split_menu(menu_path)
    if metadata["status"] != "approved":
        raise ValueError(
            f"email delivery requires approved status, found {metadata['status']}"
        )
    if not sender.strip():
        raise ValueError("sender email is required")
    if not password:
        raise ValueError("email app password is required")
    missing = [path.name for path in email_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing email drafts: " + ", ".join(missing))

    delivery = (
        json.loads(delivery_path.read_text(encoding="utf-8"))
        if delivery_path.exists()
        else {
            "schema_version": 1,
            "week_of": week_of.isoformat(),
            "messages": {},
        }
    )
    sent_now = []
    pending = [
        path
        for path in email_paths
        if path.name not in delivery.get("messages", {})
    ]
    host = os.environ.get("MEAL_PLANNER_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("MEAL_PLANNER_SMTP_PORT", "465"))
    if pending:
        context = ssl.create_default_context()
        with smtp_factory(
            host,
            port,
            context=context,
            timeout=30,
        ) as smtp:
            smtp.login(sender, password)
            for path in pending:
                recipients, subject, body = parse_email_draft(path)
                message = EmailMessage()
                message["From"] = sender
                message["To"] = ", ".join(recipients)
                message["Subject"] = subject
                message_id = make_msgid(
                    domain=sender.rsplit("@", 1)[-1]
                )
                message["Message-ID"] = message_id
                message.set_content(body)
                smtp.send_message(message)
                sent_at = dt.datetime.now(dt.timezone.utc).isoformat(
                    timespec="seconds"
                )
                delivery.setdefault("messages", {})[path.name] = {
                    "message_id": message_id,
                    "sent_at": sent_at,
                    "sender": sender,
                    "recipients": recipients,
                    "subject": subject,
                }
                _write_delivery_log(delivery_path, delivery)
                sent_now.append(path.name)

    if len(delivery.get("messages", {})) != len(EMAIL_FILENAMES):
        raise RuntimeError("Not all approved emails were delivered")
    message_ids = [
        delivery["messages"][name]["message_id"]
        for name in EMAIL_FILENAMES
    ]
    transition_menu(
        menu_path,
        "completed",
        actor,
        "Three approved emails sent successfully: " + ", ".join(message_ids),
        root=root,
        run_validators=False,
    )
    result = inspect_week(week_of, root)
    result["sent_now"] = sent_now
    result["message_ids"] = message_ids
    result["delivery_log"] = str(delivery_path)
    return result
