from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from planner.commit import commit_assignments
from planner.week_workflow import (
    approve_review_package,
    generate_review_package,
    inspect_week,
    send_approved_emails,
)
from scripts.menu_status import split_menu


ROOT = Path(__file__).resolve().parents[1]
WEEK = dt.date(2026, 6, 29)
ASSIGNMENTS = [
    "FDP-0040",
    "FDP-0038",
    "FDP-0039",
    "OVERRIDE-20260629-THU",
    "FDP-0041",
    "FDP-0012",
    "FDP-0042",
]


class FakeSmtp:
    sent_messages = []
    fail_after = None

    def __init__(self, *args, **kwargs) -> None:
        self.login_args = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def login(self, sender: str, password: str) -> None:
        self.login_args = (sender, password)

    def send_message(self, message) -> None:
        if (
            self.fail_after is not None
            and len(self.sent_messages) >= self.fail_after
        ):
            raise OSError("simulated SMTP interruption")
        self.sent_messages.append(message)


class WeekWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in (
            "ideas",
            "inventory",
            "overrides",
            "planner-data",
            "preferences",
            "quick-meals",
            "recipes",
            "scripts",
            "sides",
        ):
            shutil.copytree(ROOT / directory, self.root / directory)
        for directory in ("menus", "grocery-lists", "email-outputs"):
            (self.root / directory).mkdir()
        commit_assignments(
            WEEK,
            ASSIGNMENTS,
            actor="Fixture Reviewer",
            planned_diners=[4, 4, 4, 3, 3, 3, 3],
            accept_warnings=True,
            root=self.root,
        )
        FakeSmtp.sent_messages = []
        FakeSmtp.fail_after = None

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_generate_package_supports_human_menu_and_grocery_views(self) -> None:
        draft = inspect_week(WEEK, self.root)
        self.assertEqual(draft["status"], "draft")
        self.assertIn("MONDAY - Grilled Chicken Caesar Salad", draft["menu_summary"])
        self.assertFalse(draft["grocery_exists"])

        package = generate_review_package(WEEK, root=self.root)

        self.assertEqual(package["status"], "validated")
        self.assertTrue(package["grocery_exists"])
        self.assertTrue(package["email_drafts_complete"])
        self.assertIn("FRESH PRODUCE", package["grocery_text"].upper())
        self.assertIn("EMAIL-1-MON-TUE.MD", package["email_text"].upper())

    def test_approval_records_human_review_and_authorization(self) -> None:
        generate_review_package(WEEK, root=self.root)

        package = approve_review_package(
            WEEK,
            actor="Fixture Reviewer",
            root=self.root,
        )

        self.assertEqual(package["status"], "approved")
        text = Path(package["menu_path"]).read_text(encoding="utf-8")
        self.assertIn("| reviewed |", text)
        self.assertIn("| approved |", text)
        self.assertIn("Fixture Reviewer", text)

    def test_partial_delivery_retry_sends_only_unsent_messages(self) -> None:
        generate_review_package(WEEK, root=self.root)
        approve_review_package(
            WEEK,
            actor="Fixture Reviewer",
            root=self.root,
        )
        FakeSmtp.fail_after = 1

        with self.assertRaisesRegex(OSError, "simulated SMTP"):
            send_approved_emails(
                WEEK,
                actor="Fixture Reviewer",
                sender="planner@example.com",
                password="app-password",
                root=self.root,
                smtp_factory=FakeSmtp,
            )

        delivery_path = (
            self.root
            / "email-outputs"
            / "2026"
            / "2026-06-29"
            / "delivery-status.json"
        )
        first_delivery = json.loads(
            delivery_path.read_text(encoding="utf-8")
        )
        self.assertEqual(len(first_delivery["messages"]), 1)
        self.assertEqual(
            split_menu(
                self.root / "menus" / "2026" / "2026-06-29.md"
            )[0]["status"],
            "approved",
        )

        FakeSmtp.fail_after = None
        completed = send_approved_emails(
            WEEK,
            actor="Fixture Reviewer",
            sender="planner@example.com",
            password="app-password",
            root=self.root,
            smtp_factory=FakeSmtp,
        )

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(FakeSmtp.sent_messages), 3)
        self.assertEqual(len(completed["sent_now"]), 2)
        self.assertEqual(len(completed["message_ids"]), 3)


if __name__ == "__main__":
    unittest.main()
