from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "plan-week.ps1": "plan-week",
    "inventory-gui.ps1": "kitchen-inventory",
    "import-recipe-gui.ps1": "import-recipe",
    "recipe-feedback.ps1": "review-meal",
    "meal-override-gui.ps1": "override-meal",
}


class GuiBrandingTests(unittest.TestCase):
    def test_each_gui_uses_shared_branded_header_and_artwork(self) -> None:
        for script_name, icon_name in MODULES.items():
            script = (ROOT / "scripts" / script_name).read_text(
                encoding="utf-8"
            )
            self.assertIn("gui-branding.ps1", script)
            self.assertIn("Add-MealPlannerBranding", script)
            self.assertIn(f"-IconName '{icon_name}'", script)
            self.assertTrue(
                (ROOT / "assets" / "icons" / f"{icon_name}.png").is_file()
            )
            self.assertTrue(
                (ROOT / "assets" / "icons" / f"{icon_name}.ico").is_file()
            )
        importer = (
            ROOT / "scripts" / "import-recipe-gui.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("-PreserveClientHeight", importer)

    def test_suite_has_primary_artwork_and_module_images(self) -> None:
        script = (
            ROOT / "scripts" / "meal-planner-suite.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("meal-planner-suite.ico", script)
        self.assertIn("$moduleArtwork", script)
        self.assertTrue(
            (
                ROOT
                / "assets"
                / "icons"
                / "meal-planner-suite.ico"
            ).is_file()
        )

    def test_shortcut_generator_covers_every_command(self) -> None:
        script = (
            ROOT / "scripts" / "create-launcher-shortcuts.ps1"
        ).read_text(encoding="utf-8")
        commands = {
            path.name
            for path in ROOT.glob("*.cmd")
        }

        for command in commands:
            self.assertIn(command, script)
        for shortcut in {
            "Family Meal Planner.lnk",
            "Plan Week.lnk",
            "Kitchen Inventory.lnk",
            "Import Recipe.lnk",
            "Review Meal.lnk",
            "Override Meal.lnk",
        }:
            self.assertTrue((ROOT / shortcut).is_file())


if __name__ == "__main__":
    unittest.main()
