from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SuiteLauncherTests(unittest.TestCase):
    def test_launcher_exposes_every_existing_gui_module(self) -> None:
        script = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")
        expected_scripts = {
            "plan-week.ps1",
            "inventory-gui.ps1",
            "import-recipe-gui.ps1",
            "recipe-feedback.ps1",
            "meal-override-gui.ps1",
        }

        for script_name in expected_scripts:
            self.assertIn(script_name, script)
            self.assertTrue((ROOT / "scripts" / script_name).is_file())

    def test_cmd_entrypoint_starts_suite_in_sta_mode(self) -> None:
        command = (ROOT / "Meal Planner Suite.cmd").read_text(
            encoding="utf-8"
        )

        self.assertIn("-STA", command)
        self.assertIn("meal-planner-suite.ps1", command)


if __name__ == "__main__":
    unittest.main()
