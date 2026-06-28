from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MealOverrideGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "meal-override-gui.ps1"
        ).read_text(encoding="utf-8")

    def test_blank_optional_fields_are_not_sent_to_native_cli(self) -> None:
        handler = self.script.split(
            "$applyButton.Add_Click({",
            1,
        )[1].split("$result = & $python @arguments", 1)[0]
        base_arguments = handler.split(
            "if (-not [string]::IsNullOrWhiteSpace($titleText.Text))",
            1,
        )[0]

        self.assertNotIn("'--title'", base_arguments)
        self.assertNotIn("'--note'", base_arguments)
        self.assertIn(
            "$arguments += @('--title', $titleText.Text)",
            handler,
        )
        self.assertIn(
            "$arguments += @('--note', $noteText.Text)",
            handler,
        )


if __name__ == "__main__":
    unittest.main()
