from __future__ import annotations

import json
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
            "meal-override-gui.ps1",
        }

        for script_name in expected_scripts:
            self.assertIn(script_name, script)
            self.assertTrue((ROOT / "scripts" / script_name).is_file())
        self.assertIn("CreateRunspace", script)
        self.assertIn("ApartmentState = 'STA'", script)
        self.assertNotIn("Start-Process", script)

    def test_cmd_entrypoint_starts_suite_in_sta_mode(self) -> None:
        command = (ROOT / "Meal Planner Suite.cmd").read_text(
            encoding="utf-8"
        )

        self.assertIn("-STA", command)
        self.assertIn("meal-planner-suite.ps1", command)

    def test_cookbook_is_primary_and_import_command_is_compatible(self) -> None:
        dashboard = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")
        cookbook = (ROOT / "Recipe Cookbook.cmd").read_text(
            encoding="utf-8"
        )
        legacy = (ROOT / "Import Recipe.cmd").read_text(
            encoding="utf-8"
        )

        self.assertIn("Name = 'Recipe Cookbook'", dashboard)
        self.assertNotIn("Name = 'Import Recipe'", dashboard)
        self.assertIn("-STA", cookbook)
        self.assertIn("import-recipe-gui.ps1", cookbook)
        self.assertIn("Recipe Cookbook.cmd", legacy)

        review_legacy = (ROOT / "Review Meal.cmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("Recipe Cookbook.cmd", review_legacy)
        self.assertNotIn("Name = 'Review Meal'", dashboard)

    def test_dashboard_shutdown_never_blocks_on_runspace_stop(self) -> None:
        script = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")
        shutdown = script.split(
            "$form.Add_FormClosed({",
            1,
        )[1].split("[void]$form.ShowDialog()", 1)[0]

        self.assertNotIn(".PowerShell.Stop()", shutdown)
        self.assertIn(".PowerShell.BeginStop(", shutdown)
        self.assertIn(".Invocation.IsCompleted", shutdown)

    def test_launcher_loads_daily_weather_and_kitchen_fact(self) -> None:
        script = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("daily_weather.py", script)
        self.assertIn("Start-WeatherRefresh", script)
        self.assertIn("Kitchen fact:", script)
        self.assertIn("kitchen-facts.json", script)
        self.assertIn("Get-Random", script)
        self.assertIn("$script:kitchenFactQueue", script)
        self.assertNotIn("DayOfYear", script)

        facts = json.loads(
            (ROOT / "planner-data" / "kitchen-facts.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(facts["schema_version"], 1)
        self.assertGreaterEqual(len(facts["facts"]), 15)
        self.assertLessEqual(len(facts["facts"]), 20)
        self.assertTrue(all(fact.strip() for fact in facts["facts"]))

    def test_dashboard_shows_asynchronous_operational_health(self) -> None:
        script = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("dashboard_status.py", script)
        self.assertIn("Operational Status", script)
        for label in (
            "Validation",
            "Simulation",
            "Recipe Library",
            "Inventory",
            "Next Menu",
            "Latest Backup",
        ):
            self.assertIn(f"Label = '{label}'", script)
        self.assertIn("Start-OperationalRefresh", script)
        self.assertIn("$operationsTimer", script)
        self.assertIn("$script:operationsSession", script)
        self.assertIn(".PowerShell.BeginStop(", script)


if __name__ == "__main__":
    unittest.main()
