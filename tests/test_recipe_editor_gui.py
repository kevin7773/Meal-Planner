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

    def test_edit_mode_can_stage_ingredients_and_directions(self) -> None:
        self.assertIn("$editCardButton.Text = 'Edit Recipe Card'", self.script)
        self.assertIn("function Show-RecipeCardEditor", self.script)
        self.assertIn(
            "$Recipe.card_sections.ingredients",
            self.script,
        )
        self.assertIn(
            "$Recipe.card_sections.directions",
            self.script,
        )
        self.assertIn("Recipe card changes are staged", self.script)

    def test_card_editor_wraps_long_recipe_text_for_readability(self) -> None:
        self.assertIn("function ConvertTo-RecipeEditorText", self.script)
        self.assertGreaterEqual(
            self.script.count(
                "New-Object System.Windows.Forms.RichTextBox"
            ),
            2,
        )
        self.assertGreaterEqual(
            self.script.count(".ScrollBars = 'Vertical'"),
            2,
        )
        self.assertGreaterEqual(
            self.script.count(".WordWrap = $true"),
            2,
        )
        self.assertIn("Long lines wrap visually", self.script)

    def test_cookbook_browses_recipes_and_hides_import_workspace(self) -> None:
        self.assertIn("$cookbookRecipeCombo", self.script)
        self.assertIn("-Text 'Find'", self.script)
        self.assertIn("-Text 'View'", self.script)
        self.assertIn("-Text 'Print'", self.script)
        self.assertIn("-Text 'Export'", self.script)
        self.assertIn("-Text 'Review'", self.script)
        self.assertIn("-Text 'Edit'", self.script)
        self.assertIn("-Text 'Import Recipe'", self.script)
        self.assertIn("$importPanel.Visible = $false", self.script)
        self.assertIn(
            "& $reviewModule -RecipeId $recipeId -InitialAction $Action",
            self.script,
        )

    def test_cookbook_edit_loads_the_selected_recipe_directly(self) -> None:
        self.assertIn("function Edit-SelectedCookbookRecipe", self.script)
        self.assertIn("$recipeId = Get-SelectedCookbookRecipeId", self.script)
        self.assertIn("Load-ImportedRecipe -Recipe $recipe", self.script)
        self.assertIn(
            "Set-ImportWorkspaceVisible -Visible $true",
            self.script,
        )
        self.assertIn(
            "is approved and protected from direct editing",
            self.script,
        )
        self.assertIn("$cookbookEditButton.Text = 'Cancel Edit'", self.script)
        self.assertIn("$editRecipeButton.Visible = $false", self.script)

    def test_cookbook_has_roomy_preview_and_replaceable_image(self) -> None:
        self.assertIn(
            "$form.ClientSize = New-Object System.Drawing.Size(900, 500)",
            self.script,
        )
        self.assertIn("$libraryPreviewPanel", self.script)
        self.assertIn("$cookbookPhoto", self.script)
        self.assertIn("$changeImageButton.Text = 'Change Image'", self.script)
        self.assertIn("function Update-CookbookPreview", self.script)
        self.assertIn('-Operation "recipe-image-$recipeId"', self.script)
        self.assertIn("-Paths @('assets\\recipes')", self.script)
        self.assertIn("$recipeId.png", self.script)
        self.assertIn("*.webp", self.script)

    def test_card_save_uses_guarded_temporary_json(self) -> None:
        self.assertIn("'--card-file'", self.script)
        self.assertIn("[System.IO.Path]::GetTempFileName()", self.script)
        self.assertIn(
            "Remove-Item -LiteralPath $temporaryCardPath",
            self.script,
        )
        self.assertIn("protected history", self.script)
        self.assertIn("and ratings are not shown", self.script)

    def test_edit_save_shows_prewrite_revision_diff(self) -> None:
        self.assertIn("function Get-RecipeEditDiff", self.script)
        self.assertIn("'Ingredients changed'", self.script)
        self.assertIn("'Directions changed'", self.script)
        self.assertIn('"Revision: $([int]$original.revision) ->', self.script)
        self.assertIn("'Confirm Recipe Revision'", self.script)
        diff_index = self.script.index("$diff = Get-RecipeEditDiff")
        backup_index = self.script.index(
            '-Operation "recipe-edit-',
            diff_index,
        )
        write_index = self.script.index(
            "$result = & $python @arguments",
            backup_index,
        )
        self.assertLess(diff_index, backup_index)
        self.assertLess(backup_index, write_index)

    def test_candidate_can_be_promoted_outside_feedback(self) -> None:
        self.assertIn(
            "$promoteButton.Text = 'Promote to Approved'",
            self.script,
        )
        self.assertIn("function Show-PromotionDialog", self.script)
        self.assertIn("'Approved by is required.'", self.script)
        self.assertIn("'Approval reason is required.'", self.script)
        self.assertIn("$recipeEditor promote", self.script)
        self.assertIn("recipe-promote-", self.script)


if __name__ == "__main__":
    unittest.main()
