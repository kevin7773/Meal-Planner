from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PlanWeekWorkflowGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "plan-week.ps1"
        ).read_text(encoding="utf-8")

    def test_existing_week_exposes_human_readable_views(self) -> None:
        for label in (
            "Menu Summary",
            "Grocery List",
            "Email Drafts",
            "Raw Markdown",
        ):
            self.assertIn(label, self.script)
        self.assertIn(
            "Show-WorkflowContent",
            self.script,
        )
        self.assertIn(
            "-Property 'menu_summary'",
            self.script,
        )
        self.assertIn(
            "-Property 'grocery_text'",
            self.script,
        )

    def test_lifecycle_actions_are_status_gated(self) -> None:
        self.assertIn("$generatePackageButton", self.script)
        self.assertIn("$approvePackageButton", self.script)
        self.assertIn("$sendEmailsButton", self.script)
        self.assertIn("$status -in @('draft', 'generated')", self.script)
        self.assertIn(
            "$status -in @('validated', 'reviewed')",
            self.script,
        )
        self.assertIn("$status -eq 'approved'", self.script)

    def test_overridden_draft_exposes_revalidation_action(self) -> None:
        self.assertIn(
            "$script:hasMealOverrides = Test-Path",
            self.script,
        )
        self.assertIn(
            "$generatePackageButton.Text = if (",
            self.script,
        )
        self.assertIn("'Revalidate Override'", self.script)
        self.assertIn(
            "click Revalidate Override before approval",
            self.script,
        )

    def test_workflow_controls_fit_above_taskbar(self) -> None:
        self.assertIn(
            "System.Drawing.Size(1060, 680)",
            self.script,
        )
        for control in (
            "$generatePackageButton",
            "$approvePackageButton",
            "$sendEmailsButton",
        ):
            block = self.script.split(
                f"{control} = New-Object",
                1,
            )[1].split("$form.Controls.Add", 1)[0]
            self.assertIn(
                "System.Drawing.Point(",
                block,
            )
            self.assertIn(", 615)", block)
            self.assertIn(
                "System.Drawing.Size(",
                block,
            )
            self.assertIn(", 40)", block)

    def test_commit_keeps_gui_open_for_review(self) -> None:
        commit_handler = self.script.split(
            "$commitButton.Add_Click({",
            1,
        )[1].split("$generatePackageButton.Add_Click({", 1)[0]

        self.assertNotIn("$form.Close()", commit_handler)
        self.assertIn(
            "-Title 'HUMAN-READABLE DRAFT MENU'",
            commit_handler,
        )

    def test_send_uses_transient_password_and_explicit_confirmation(self) -> None:
        self.assertIn("Show-EmailCredentialDialog", self.script)
        self.assertIn("UseSystemPasswordChar = $true", self.script)
        self.assertIn("MEAL_PLANNER_EMAIL_PASSWORD", self.script)
        self.assertIn("$credentials.Password = ''", self.script)
        self.assertIn(
            "This will immediately send all three approved weekly menu",
            self.script,
        )
        self.assertIn(
            "$appPassword = $passwordText.Text -replace '\\s', ''",
            self.script,
        )
        self.assertIn("$appPassword.Length -ne 16", self.script)
        self.assertIn("Password = $appPassword", self.script)

    def test_send_can_resolve_password_from_onepassword(self) -> None:
        self.assertIn("function Resolve-OnePasswordCli", self.script)
        self.assertIn("function Read-OnePasswordSecret", self.script)
        self.assertIn("& $op read $Reference --no-newline", self.script)
        self.assertIn("'1Password'", self.script)
        self.assertIn("'Enter manually'", self.script)
        self.assertIn(
            "'Example: op://Private/Meal Planner Gmail/password'",
            self.script,
        )

    def test_email_setup_can_be_tested_after_week_completion(self) -> None:
        self.assertIn("$testEmailButton.Text = 'Test Email Setup'", self.script)
        self.assertIn("$testEmailButton.Enabled = $true", self.script)
        self.assertIn(
            "Show-EmailCredentialDialog -TestOnly",
            self.script,
        )
        self.assertIn("-Command 'test-email'", self.script)
        self.assertIn("'No message was sent.'", self.script)
        self.assertIn("$credentials.Password = ''", self.script)

    def test_email_settings_store_reference_but_never_password(self) -> None:
        settings_writer = self.script.split(
            "function Save-EmailSettings",
            1,
        )[1].split("function Read-OnePasswordSecret", 1)[0]

        self.assertIn("schema_version = 1", settings_writer)
        self.assertIn("sender_email = $Sender", settings_writer)
        self.assertIn(
            "onepassword_reference = $OnePasswordReference",
            settings_writer,
        )
        self.assertNotIn("password =", settings_writer.lower())

    def test_uses_dashboard_section_palette(self) -> None:
        for color in (
            "#28765A",
            "#C5842C",
            "#48769A",
            "#8A5D86",
            "#A04E45",
        ):
            self.assertIn(color, self.script)
        self.assertIn("Set-SectionButtonStyle", self.script)
        self.assertIn(
            "-Button $viewGroceryButton -Color $colors.Pantry",
            self.script,
        )
        self.assertIn(
            "-Button $viewEmailsButton -Color $colors.Email",
            self.script,
        )
        self.assertIn(
            "-Button $approvePackageButton -Color $colors.Review",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
