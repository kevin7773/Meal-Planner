from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.dry_run import generate_proposals
from scripts.meal_override import apply_override
from scripts.menu_status import split_menu, validate_menu


ROOT = Path(__file__).resolve().parents[1]


class MealOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in (
            "recipes",
            "inventory",
            "menus",
            "email-outputs",
            "grocery-lists",
        ):
            shutil.copytree(ROOT / directory, self.root / directory)
        active_email_week = (
            self.root / "email-outputs" / "2026" / "2026-06-29"
        )
        if not active_email_week.exists():
            archived_emails = (
                ROOT
                / "archive"
                / "2026"
                / "2026-06-29"
                / "completed-2026-06-27"
                / "email-outputs"
            )
            shutil.copytree(archived_emails, active_email_week)
        self.menu = self.root / "menus" / "2026" / "2026-06-29.md"
        text = self.menu.read_text(encoding="utf-8")
        validated_rows = list(
            re.finditer(
                r"(?m)^\| validated \| ([^|]+) \|[^|]+\|[^|]+\|$",
                text,
            )
        )
        self.assertTrue(validated_rows)
        latest_validated = validated_rows[-1]
        timestamp = latest_validated.group(1).strip()
        text = text[: latest_validated.end()] + "\n"
        text = re.sub(r'(?m)^status = ".*"$', 'status = "validated"', text, count=1)
        text = re.sub(
            r'(?m)^status_updated_at = ".*"$',
            f'status_updated_at = "{timestamp}"',
            text,
            count=1,
        )
        self.menu.write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_dining_out_override_updates_artifacts_and_returns_to_draft(self) -> None:
        sidecar = apply_override(
            self.menu,
            day="Thursday",
            override_type="dining-out",
            title="Dinner Out",
            note="Birthday dinner",
            actor="Kevin",
            root=self.root,
        )
        metadata, _ = split_menu(self.menu)
        self.assertEqual(metadata["status"], "draft")
        self.assertEqual(validate_menu(self.menu), [])
        self.assertIn("Dinner Out", self.menu.read_text(encoding="utf-8"))
        email = (
            self.root
            / "email-outputs"
            / "2026"
            / "2026-06-29"
            / "email-2-wed-thu-fri.md"
        )
        self.assertIn("Birthday dinner", email.read_text(encoding="utf-8"))
        records = json.loads(sidecar.read_text(encoding="utf-8"))["overrides"]
        self.assertEqual(records[0]["original_recipe_id"], "FDP-0006")
        grocery = (
            self.root
            / "grocery-lists"
            / "2026"
            / "2026-06-29-grocery-list.md"
        )
        self.assertIn("Meal Override Grocery Adjustments", grocery.read_text(encoding="utf-8"))
        proposals = generate_proposals(
            dt.date(2026, 6, 29),
            3,
            root=self.root,
        )
        self.assertTrue(
            all(proposal["meals"][3]["status"] == "override" for proposal in proposals)
        )

    def test_alternate_recipe_is_expanded_into_menu_and_email(self) -> None:
        apply_override(
            self.menu,
            day="Tuesday",
            override_type="alternate-recipe",
            title="",
            note="Use a family favorite",
            actor="Kevin",
            replacement_recipe_id="FDP-0002",
            root=self.root,
        )
        text = self.menu.read_text(encoding="utf-8")
        self.assertIn("**Recipe:** FDP-0002 rev 3 (candidate)", text)
        self.assertIn("**Original Recipe:** FDP-0008", text)

    def test_completed_week_cannot_be_overridden(self) -> None:
        text = self.menu.read_text(encoding="utf-8").replace(
            'status = "validated"',
            'status = "completed"',
            1,
        )
        self.menu.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Cannot override a completed week"):
            apply_override(
                self.menu,
                day="Friday",
                override_type="skip",
                title="No dinner needed",
                note="",
                actor="Kevin",
                root=self.root,
            )


if __name__ == "__main__":
    unittest.main()
