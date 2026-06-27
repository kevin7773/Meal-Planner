from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from scripts.menu_status import MenuStatusError, transition_menu, validate_menu


INITIAL_MENU = """+++
week_of = "2026-06-29"
status = "draft"
status_updated_at = "2026-06-26T12:00:00Z"
+++

# Weekly Dinner Menu

## Planning Status History

| Status | Timestamp | Actor | Note |
| --- | --- | --- | --- |
| draft | 2026-06-26T12:00:00Z | Codex | Weekly planning started |
"""


class MenuStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.menu = Path(self.temporary_directory.name) / "2026-06-29.md"
        self.menu.write_text(INITIAL_MENU, encoding="utf-8")
        self.now = dt.datetime(2026, 6, 26, 13, 0, tzinfo=dt.timezone.utc)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def transition(
        self,
        target: str,
        actor: str = "Codex",
        note: str = "Status advanced",
    ) -> None:
        transition_menu(
            self.menu,
            target,
            actor,
            note,
            now=self.now,
            run_validators=False,
        )
        self.now += dt.timedelta(minutes=1)

    def test_full_lifecycle(self) -> None:
        self.transition("generated")
        self.transition("validated")
        self.transition("reviewed", actor="Kevin")
        self.transition("approved", actor="Kevin")
        self.transition("completed", note="All three emails sent")
        self.transition("archived", actor="Kevin", note="Feedback collected")
        self.assertEqual(validate_menu(self.menu), [])
        self.assertIn('status = "archived"', self.menu.read_text(encoding="utf-8"))

    def test_cannot_skip_status(self) -> None:
        with self.assertRaisesRegex(MenuStatusError, "transition not allowed"):
            self.transition("validated")

    def test_review_requires_human_actor(self) -> None:
        self.transition("generated")
        self.transition("validated")
        with self.assertRaisesRegex(MenuStatusError, "human reviewer"):
            self.transition("reviewed", actor="Codex")

    def test_return_to_draft_requires_reason(self) -> None:
        self.transition("generated")
        with self.assertRaisesRegex(MenuStatusError, "requires a reason"):
            self.transition("draft", note="")

    def test_week_must_start_on_monday(self) -> None:
        text = self.menu.read_text(encoding="utf-8").replace(
            'week_of = "2026-06-29"',
            'week_of = "2026-06-30"',
        )
        self.menu.write_text(text, encoding="utf-8")
        self.assertIn("week_of must be a Monday", validate_menu(self.menu))

    def test_completed_week_requires_explicit_reopen(self) -> None:
        self.transition("generated")
        self.transition("validated")
        self.transition("reviewed", actor="Kevin")
        self.transition("approved", actor="Kevin")
        self.transition("completed", note="Emails sent")
        with self.assertRaisesRegex(MenuStatusError, "explicit reopen"):
            self.transition("draft", actor="Kevin", note="Rebuild requested")
        transition_menu(
            self.menu,
            "draft",
            "Kevin",
            "Rebuild requested after archival",
            now=self.now,
            run_validators=False,
            allow_reopen=True,
        )
        self.assertEqual(validate_menu(self.menu), [])


if __name__ == "__main__":
    unittest.main()
