from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReviewMealRepeatEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (
            ROOT / "scripts" / "recipe-feedback.ps1"
        ).read_text(encoding="utf-8")

    def test_successful_save_resets_instead_of_closing(self) -> None:
        save_handler = self.script.split(
            "$saveButton.Add_Click({",
            1,
        )[1].split("$form.Controls.Add($saveButton)", 1)[0]

        self.assertIn("Reset-ReviewEntry", save_handler)
        self.assertNotIn("$form.Close()", save_handler)
        self.assertIn(
            "The form is ready for another review.",
            save_handler,
        )

    def test_reset_clears_notes_refreshes_recipes_and_advances(self) -> None:
        self.assertIn("function Reset-ReviewEntry", self.script)
        self.assertIn("$keepText.Clear()", self.script)
        self.assertIn("$changeText.Clear()", self.script)
        self.assertIn("$updatedRecipes = Get-RecipeList", self.script)
        self.assertIn(
            "($recipeCombo.SelectedIndex + 1) % $recipeCombo.Items.Count",
            self.script,
        )

    def test_reviewer_can_open_complete_recipe_without_leaving_form(self) -> None:
        self.assertIn("$viewRecipeButton.Text = 'View Recipe'", self.script)
        self.assertIn("function Show-SelectedRecipe", self.script)
        self.assertIn(
            "[System.IO.File]::ReadAllText($recipe.Path)",
            self.script,
        )
        self.assertIn("-Title 'Recipe Card'", self.script)
        self.assertIn("[void]$dialog.ShowDialog($form)", self.script)

    def test_recipe_view_resolves_latest_revision_and_handles_large_cards(
        self,
    ) -> None:
        viewer = self.script.split(
            "function Show-SelectedRecipe",
            1,
        )[1].split("$viewRecipeButton.Add_Click", 1)[0]
        resolver = self.script.split(
            "function Get-CurrentSelectedRecipe",
            1,
        )[1].split("$printRecipeButton =", 1)[0]

        self.assertIn("$currentRecipes = @(", resolver)
        self.assertIn("Get-RecipeList |", resolver)
        self.assertIn(
            "$_.Id -eq $selectedRecipe.Id",
            resolver,
        )
        self.assertIn("$recipe = Get-CurrentSelectedRecipe", viewer)
        self.assertIn(
            "New-Object System.Windows.Forms.RichTextBox",
            viewer,
        )
        self.assertIn(
            "$recipeText.MaxLength = [int]::MaxValue",
            viewer,
        )
        self.assertIn(
            '"$($recipe.Id) | Revision $($recipe.Revision)',
            viewer,
        )

    def test_recipe_list_can_print_a_clean_paginated_card(self) -> None:
        self.assertIn("$printRecipeButton.Text = 'Print Recipe'", self.script)
        self.assertIn("function Get-PrintableRecipeLines", self.script)
        self.assertIn("function Print-SelectedRecipe", self.script)
        self.assertIn(
            "New-Object System.Drawing.Printing.PrintDocument",
            self.script,
        )
        self.assertIn(
            "New-Object System.Windows.Forms.PrintPreviewControl",
            self.script,
        )
        self.assertIn("$document.Add_BeginPrint", self.script)
        self.assertIn("$printButton.Text = 'Print'", self.script)
        self.assertIn(
            "New-Object System.Windows.Forms.PrintDialog",
            self.script,
        )
        self.assertIn("$eventArgs.HasMorePages = $true", self.script)
        self.assertIn(
            "'(?m)^## Family Notes\\s*$'",
            self.script,
        )
        self.assertIn("Serves $servings", self.script)

    def test_recipe_card_can_export_deterministic_printable_html(self) -> None:
        self.assertIn("$exportRecipeButton.Text = 'Export HTML'", self.script)
        self.assertIn("function Export-SelectedRecipeHtml", self.script)
        self.assertIn(
            "[System.Net.WebUtility]::HtmlEncode",
            self.script,
        )
        self.assertIn("<!doctype html>", self.script)
        self.assertIn("@media print", self.script)
        self.assertIn(
            "New-Object System.Windows.Forms.SaveFileDialog",
            self.script,
        )
        self.assertIn(
            "New-Object System.Text.UTF8Encoding($false)",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
