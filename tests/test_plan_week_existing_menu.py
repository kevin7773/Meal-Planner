from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PlanWeekExistingMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "plan-week.ps1"
        ).read_text(encoding="utf-8")

    def test_selected_week_checks_for_existing_menu(self) -> None:
        self.assertIn("function Get-SelectedMenuPath", self.script)
        self.assertIn("Test-Path -LiteralPath $path", self.script)
        self.assertIn("Existing plan found for this week", self.script)
        self.assertIn("$weekPicker.Add_ValueChanged", self.script)

    def test_existing_menu_can_be_viewed_before_generation(self) -> None:
        self.assertIn("$viewExistingButton.Add_Click", self.script)
        self.assertIn("EXISTING WEEKLY PLAN", self.script)
        self.assertIn(
            "[System.IO.File]::ReadAllText",
            self.script,
        )
        self.assertIn(
            "-replace '\\r?\\n', [Environment]::NewLine",
            self.script,
        )

    def test_generation_requires_confirmation_for_existing_week(self) -> None:
        self.assertIn("'Existing Meal Plan'", self.script)
        self.assertIn(
            "Generating dry runs will not change the existing plan",
            self.script,
        )

    def test_plan_week_collects_seven_daily_diner_counts(self) -> None:
        self.assertIn("$script:dinerInputs", self.script)
        self.assertIn("function Get-PlannedDiners", self.script)
        self.assertIn("function Set-PlannedDiners", self.script)
        self.assertIn("'--diners'", self.script)
        for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            self.assertIn(f"Name = '{day}'", self.script)
        self.assertIn(
            "[System.Windows.Forms.DialogResult]::Yes",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
