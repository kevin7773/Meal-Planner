from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RecipeEditorGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "import-recipe-gui.ps1"
        ).read_text(encoding="utf-8")

    def test_gui_can_select_and_load_imported_recipe(self) -> None:
        self.assertIn("'Edit Imported Recipe'", self.script)
        self.assertIn("function Select-ImportedRecipe", self.script)
        self.assertIn("function Load-ImportedRecipe", self.script)
        self.assertIn("$recipeEditor list --json", self.script)
        self.assertIn("[kid reason needs update]", self.script)

    def test_gui_collects_prep_time_for_imports_and_edits(self) -> None:
        self.assertIn("$prepMinutes", self.script)
        self.assertGreaterEqual(
            self.script.count("'--prep-minutes'"),
            2,
        )

    def test_edit_save_uses_revision_backend(self) -> None:
        self.assertIn("$recipeEditor,\n                'update'", self.script)
        self.assertIn("'Save Recipe Revision'", self.script)
        self.assertIn("'Recipe Revision Saved'", self.script)


if __name__ == "__main__":
    unittest.main()
