Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'gui-backup.ps1')
$importer = Join-Path $PSScriptRoot 'import_recipe.py'
$recipeEditor = Join-Path $PSScriptRoot 'edit_recipe.py'
$ideaManager = Join-Path $PSScriptRoot 'recipe_ideas.py'
$reviewModule = Join-Path $PSScriptRoot 'recipe-feedback.ps1'
$recipeAssetsRoot = Join-Path $projectRoot 'assets\recipes'

function Resolve-Python {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    throw 'Python 3.11 or newer is required.'
}
$python = Resolve-Python

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot 'gui-branding.ps1')
$colors = Get-MealPlannerPalette

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Recipe Cookbook'
$form.ClientSize = New-Object System.Drawing.Size(900, 820)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
Set-MealPlannerFormSurface -Form $form -Palette $colors

function Add-Label([string]$Text, [int]$X, [int]$Y, [int]$Width = 120) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($Width, 28)
    $label.TextAlign = 'MiddleLeft'
    $form.Controls.Add($label)
}

Add-Label 'File or URL' 20 20
$sourceText = New-Object System.Windows.Forms.TextBox
$sourceText.Location = New-Object System.Drawing.Point(140, 20)
$sourceText.Size = New-Object System.Drawing.Size(465, 28)
$form.Controls.Add($sourceText)
$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = 'Browse'
$browseButton.Location = New-Object System.Drawing.Point(615, 17)
$browseButton.Size = New-Object System.Drawing.Size(75, 34)
$form.Controls.Add($browseButton)
$pasteButton = New-Object System.Windows.Forms.Button
$pasteButton.Text = 'Paste Text'
$pasteButton.Location = New-Object System.Drawing.Point(700, 17)
$pasteButton.Size = New-Object System.Drawing.Size(90, 34)
$form.Controls.Add($pasteButton)
$previewButton = New-Object System.Windows.Forms.Button
$previewButton.Text = 'Preview'
$previewButton.Location = New-Object System.Drawing.Point(800, 17)
$previewButton.Size = New-Object System.Drawing.Size(80, 34)
$form.Controls.Add($previewButton)

$previewText = New-Object System.Windows.Forms.TextBox
$previewText.Location = New-Object System.Drawing.Point(20, 70)
$previewText.Size = New-Object System.Drawing.Size(860, 230)
$previewText.Multiline = $true
$previewText.ReadOnly = $true
$previewText.ScrollBars = 'Vertical'
$previewText.Font = New-Object System.Drawing.Font('Consolas', 9)
$form.Controls.Add($previewText)

Add-Label 'Recipe name' 20 325
$nameText = New-Object System.Windows.Forms.TextBox
$nameText.Location = New-Object System.Drawing.Point(140, 325)
$nameText.Size = New-Object System.Drawing.Size(350, 28)
$form.Controls.Add($nameText)

Add-Label 'Protein' 520 325 80
$proteinCombo = New-Object System.Windows.Forms.ComboBox
$proteinCombo.Location = New-Object System.Drawing.Point(600, 325)
$proteinCombo.Size = New-Object System.Drawing.Size(180, 28)
$proteinCombo.DropDownStyle = 'DropDownList'
@(
    'Select protein...',
    'chicken',
    'turkey',
    'beef',
    'seafood',
    'pork',
    'vegetarian',
    'other'
) | ForEach-Object { [void]$proteinCombo.Items.Add($_) }
$proteinCombo.SelectedIndex = 0
$form.Controls.Add($proteinCombo)

Add-Label 'Method' 20 370
$methodCombo = New-Object System.Windows.Forms.ComboBox
$methodCombo.Location = New-Object System.Drawing.Point(140, 370)
$methodCombo.Size = New-Object System.Drawing.Size(220, 28)
$methodCombo.DropDownStyle = 'DropDownList'
@('stovetop','oven','grill','smoker','blackstone','slow-cooker','minimal-cook','no-cook') | ForEach-Object { [void]$methodCombo.Items.Add($_) }
$methodCombo.SelectedIndex = 0
$form.Controls.Add($methodCombo)

Add-Label 'Fiber g' 390 370 70
$fiberInput = New-Object System.Windows.Forms.NumericUpDown
$fiberInput.Location = New-Object System.Drawing.Point(460, 370)
$fiberInput.Size = New-Object System.Drawing.Size(90, 28)
$fiberInput.DecimalPlaces = 1
$fiberInput.Maximum = 50
$fiberInput.Value = 8
$form.Controls.Add($fiberInput)

Add-Label 'Cost $' 580 370 65
$costInput = New-Object System.Windows.Forms.NumericUpDown
$costInput.Location = New-Object System.Drawing.Point(645, 370)
$costInput.Size = New-Object System.Drawing.Size(90, 28)
$costInput.DecimalPlaces = 2
$costInput.Maximum = 200
$costInput.Value = 20
$form.Controls.Add($costInput)

Add-Label 'Kid score' 760 370 70
$kidScore = New-Object System.Windows.Forms.ComboBox
$kidScore.Location = New-Object System.Drawing.Point(830, 370)
$kidScore.Size = New-Object System.Drawing.Size(50, 28)
$kidScore.DropDownStyle = 'DropDownList'
@('1','4','5') | ForEach-Object { [void]$kidScore.Items.Add($_) }
$kidScore.SelectedIndex = 1
$kidScore.Enabled = $false
$form.Controls.Add($kidScore)

Add-Label 'Kid-friendly reason' 20 415
$kidReason = New-Object System.Windows.Forms.ComboBox
$kidReason.Location = New-Object System.Drawing.Point(160, 415)
$kidReason.Size = New-Object System.Drawing.Size(330, 28)
$kidReason.DropDownStyle = 'DropDownList'
@(
    'Gray Loves It',
    'Both children like/love it',
    "One of Kellan's Favorites",
    'Not kid friendly - for the parents only'
) | ForEach-Object { [void]$kidReason.Items.Add($_) }
$kidReason.SelectedIndex = 0
$form.Controls.Add($kidReason)
$kidReason.Add_SelectedIndexChanged({
    switch ([string]$kidReason.SelectedItem) {
        'Both children like/love it' { $kidScore.SelectedItem = '5' }
        'Not kid friendly - for the parents only' { $kidScore.SelectedItem = '1' }
        default { $kidScore.SelectedItem = '4' }
    }
})

Add-Label 'Prep min' 510 415 70
$prepMinutes = New-Object System.Windows.Forms.NumericUpDown
$prepMinutes.Location = New-Object System.Drawing.Point(580, 415)
$prepMinutes.Size = New-Object System.Drawing.Size(80, 28)
$prepMinutes.Maximum = 1440
$form.Controls.Add($prepMinutes)

Add-Label 'Cook min' 680 415 70
$cookMinutes = New-Object System.Windows.Forms.NumericUpDown
$cookMinutes.Location = New-Object System.Drawing.Point(755, 415)
$cookMinutes.Size = New-Object System.Drawing.Size(125, 28)
$cookMinutes.Maximum = 1440
$form.Controls.Add($cookMinutes)

Add-Label 'Seasons' 20 460 80
$seasonButtons = @{}
$seasonOptions = @(
    @{ Key = 'spring'; Label = 'Spring'; X = 110; Width = 75 },
    @{ Key = 'summer'; Label = 'Summer'; X = 185; Width = 85 },
    @{ Key = 'fall'; Label = 'Fall'; X = 270; Width = 55 },
    @{ Key = 'winter'; Label = 'Winter'; X = 325; Width = 75 }
)
foreach ($option in $seasonOptions) {
    $button = New-Object System.Windows.Forms.CheckBox
    $button.Text = $option.Label
    $button.Location = New-Object System.Drawing.Point($option.X, 460)
    $button.Size = New-Object System.Drawing.Size($option.Width, 28)
    $button.Checked = $true
    $seasonButtons[$option.Key] = $button
    $form.Controls.Add($button)
}

Add-Label 'Meal coverage' 520 460 120
$mealScopeCombo = New-Object System.Windows.Forms.ComboBox
$mealScopeCombo.Location = New-Object System.Drawing.Point(640, 460)
$mealScopeCombo.Size = New-Object System.Drawing.Size(240, 28)
$mealScopeCombo.DropDownStyle = 'DropDownList'
@('complete-meal','entree') | ForEach-Object { [void]$mealScopeCombo.Items.Add($_) }
$mealScopeCombo.SelectedIndex = 0
$form.Controls.Add($mealScopeCombo)

$note = New-Object System.Windows.Forms.Label
$ideaLabel = New-Object System.Windows.Forms.Label
$ideaLabel.Text = 'Recipe idea'
$ideaLabel.Location = New-Object System.Drawing.Point(20, 505)
$ideaLabel.Size = New-Object System.Drawing.Size(120, 28)
$ideaLabel.TextAlign = 'MiddleLeft'
$form.Controls.Add($ideaLabel)

$ideaText = New-Object System.Windows.Forms.TextBox
$ideaText.Location = New-Object System.Drawing.Point(140, 505)
$ideaText.Size = New-Object System.Drawing.Size(740, 70)
$ideaText.Multiline = $true
$ideaText.ScrollBars = 'Vertical'
$form.Controls.Add($ideaText)

$mexicanMonday = New-Object System.Windows.Forms.CheckBox
$mexicanMonday.Text = 'Mexican Monday idea'
$mexicanMonday.Location = New-Object System.Drawing.Point(140, 580)
$mexicanMonday.Size = New-Object System.Drawing.Size(190, 28)
$form.Controls.Add($mexicanMonday)

$note.Location = New-Object System.Drawing.Point(20, 620)
$note.Size = New-Object System.Drawing.Size(860, 65)
$note.BorderStyle = 'FixedSingle'
$note.Padding = New-Object System.Windows.Forms.Padding(10)
$defaultNoteText = 'Imports are candidates. Review quantities, seasoning classification, and inventory mapping before scheduling.'
$note.Text = $defaultNoteText
$form.Controls.Add($note)

$editRecipeButton = New-Object System.Windows.Forms.Button
$editRecipeButton.Text = 'Edit Imported Recipe'
$editRecipeButton.Location = New-Object System.Drawing.Point(20, 735)
$editRecipeButton.Size = New-Object System.Drawing.Size(190, 42)
$editRecipeButton.Visible = $false
$form.Controls.Add($editRecipeButton)

$editCardButton = New-Object System.Windows.Forms.Button
$editCardButton.Text = 'Edit Recipe Card'
$editCardButton.Location = New-Object System.Drawing.Point(225, 735)
$editCardButton.Size = New-Object System.Drawing.Size(210, 42)
$editCardButton.Enabled = $false
$form.Controls.Add($editCardButton)

$saveIdeaButton = New-Object System.Windows.Forms.Button
$saveIdeaButton.Text = 'Save Recipe Idea'
$saveIdeaButton.Location = New-Object System.Drawing.Point(455, 735)
$saveIdeaButton.Size = New-Object System.Drawing.Size(150, 42)
$form.Controls.Add($saveIdeaButton)

$promoteButton = New-Object System.Windows.Forms.Button
$promoteButton.Text = 'Promote to Approved'
$promoteButton.Location = New-Object System.Drawing.Point(455, 735)
$promoteButton.Size = New-Object System.Drawing.Size(150, 42)
$promoteButton.Enabled = $false
$promoteButton.Visible = $false
$form.Controls.Add($promoteButton)

$importButton = New-Object System.Windows.Forms.Button
$importButton.Text = 'Import Candidate'
$importButton.Location = New-Object System.Drawing.Point(620, 735)
$importButton.Size = New-Object System.Drawing.Size(145, 42)
$importButton.Enabled = $false
$form.Controls.Add($importButton)
$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = 'Close'
$closeButton.Location = New-Object System.Drawing.Point(780, 735)
$closeButton.Size = New-Object System.Drawing.Size(100, 42)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$script:pastedText = ''
$script:editingRecipeId = $null
$script:editingOriginalRecipe = $null
$script:editingCardSections = $null
$script:cardModified = $false

function Reset-ImportForm {
    $script:pastedText = ''
    $script:editingRecipeId = $null
    $script:editingOriginalRecipe = $null
    $script:editingCardSections = $null
    $script:cardModified = $false
    $sourceText.Clear()
    $sourceText.ReadOnly = $false
    $previewText.Clear()
    $nameText.Clear()
    $ideaText.Clear()
    $kidReason.SelectedIndex = 0
    $proteinCombo.SelectedIndex = 0
    $methodCombo.SelectedIndex = 0
    $fiberInput.Value = 8
    $costInput.Value = 20
    $kidScore.SelectedItem = '4'
    $prepMinutes.Value = 0
    $cookMinutes.Value = 0
    foreach ($season in @('spring','summer','fall','winter')) {
        $seasonButtons[$season].Checked = $true
    }
    $mealScopeCombo.SelectedIndex = 0
    $mexicanMonday.Checked = $false
    $importButton.Enabled = $false
    $importButton.Text = 'Import Candidate'
    $editRecipeButton.Text = 'Edit Imported Recipe'
    $cookbookEditButton.Text = 'Edit'
    $editCardButton.Enabled = $false
    $browseButton.Enabled = $true
    $pasteButton.Enabled = $true
    $previewButton.Enabled = $true
    $ideaText.Enabled = $true
    $mexicanMonday.Enabled = $true
    $saveIdeaButton.Enabled = $true
    $saveIdeaButton.Visible = $true
    $promoteButton.Enabled = $false
    $promoteButton.Visible = $false
    $note.Text = $defaultNoteText
    $sourceText.Focus()
}

function Get-SelectedSeasons {
    $selected = New-Object System.Collections.Generic.List[string]
    foreach ($season in @('spring','summer','fall','winter')) {
        if ($seasonButtons[$season].Checked) { $selected.Add($season) }
    }
    if ($selected.Count -eq 0) { throw 'Select at least one season.' }
    return $selected -join ','
}

function Get-RecipeEditDiff {
    $original = $script:editingOriginalRecipe
    if ($null -eq $original) {
        throw 'The original recipe revision is unavailable.'
    }
    $lines = New-Object System.Collections.Generic.List[string]
    $comparisons = @(
        @('Name', [string]$original.name, $nameText.Text.Trim()),
        @('Protein', [string]$original.protein, [string]$proteinCombo.SelectedItem),
        @('Meal coverage', [string]$original.meal_scope, [string]$mealScopeCombo.SelectedItem),
        @('Prep time', "$([int]$original.prep_minutes) min", "$([int]$prepMinutes.Value) min"),
        @('Cook time', "$([int]$original.cook_minutes) min", "$([int]$cookMinutes.Value) min"),
        @('Fiber', "$([double]$original.fiber_grams) g", "$([double]$fiberInput.Value) g"),
        @('Cost', ('$' + ([double]$original.estimated_cost_usd).ToString('0.00')), ('$' + ([double]$costInput.Value).ToString('0.00'))),
        @('Kid-friendly reason', [string]$original.kid_friendly_reason, $kidReason.Text),
        @('Method', [string]$original.cooking_method, [string]$methodCombo.SelectedItem),
        @('Seasons', (@($original.seasons) -join ', '), ((Get-SelectedSeasons) -replace ',', ', '))
    )
    foreach ($comparison in $comparisons) {
        if ($comparison[1] -ne $comparison[2]) {
            $lines.Add(
                "$($comparison[0]): $($comparison[1]) -> $($comparison[2])"
            )
        }
    }
    $originalIngredients = (
        [string]$original.card_sections.ingredients
    ) -replace '\r\n', "`n"
    $editedIngredients = (
        [string]$script:editingCardSections.ingredients
    ) -replace '\r\n', "`n"
    if ($originalIngredients -ne $editedIngredients) {
        $lines.Add('Ingredients changed')
    }
    $originalDirections = (
        [string]$original.card_sections.directions
    ) -replace '\r\n', "`n"
    $editedDirections = (
        [string]$script:editingCardSections.directions
    ) -replace '\r\n', "`n"
    if ($originalDirections -ne $editedDirections) {
        $lines.Add('Directions changed')
    }
    if ($lines.Count -eq 0) {
        $lines.Add('No recipe fields changed')
    }
    $lines.Add(
        "Revision: $([int]$original.revision) -> $([int]$original.revision + 1)"
    )
    return $lines -join [Environment]::NewLine
}

function Show-PasteEditor {
    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = 'Paste Recipe Text'
    $dialog.ClientSize = New-Object System.Drawing.Size(700, 520)
    $dialog.StartPosition = 'CenterParent'
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $dialog -Palette $colors
    $editor = New-Object System.Windows.Forms.TextBox
    $editor.Location = New-Object System.Drawing.Point(15, 15)
    $editor.Size = New-Object System.Drawing.Size(670, 440)
    $editor.Multiline = $true
    $editor.AcceptsReturn = $true
    $editor.AcceptsTab = $true
    $editor.ScrollBars = 'Both'
    $editor.Text = $script:pastedText
    $dialog.Controls.Add($editor)
    $useButton = New-Object System.Windows.Forms.Button
    $useButton.Text = 'Use This Text'
    $useButton.Location = New-Object System.Drawing.Point(535, 470)
    $useButton.Size = New-Object System.Drawing.Size(150, 35)
    $useButton.DialogResult = 'OK'
    $dialog.Controls.Add($useButton)
    Set-MealPlannerButtonStyle -Button $useButton -Color $colors.Email
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = 'Cancel'
    $cancel.Location = New-Object System.Drawing.Point(420, 470)
    $cancel.Size = New-Object System.Drawing.Size(100, 35)
    $cancel.DialogResult = 'Cancel'
    $dialog.Controls.Add($cancel)
    Set-MealPlannerNeutralButtonStyle -Button $cancel -Palette $colors
    $dialog.AcceptButton = $useButton
    $dialog.CancelButton = $cancel
    if ($dialog.ShowDialog($form) -eq 'OK') {
        $script:pastedText = $editor.Text
        $sourceText.Text = "Pasted recipe text ($($script:pastedText.Length) characters)"
        $importButton.Enabled = $false
    }
}

function Get-ImportedRecipeList {
    $raw = & $python $recipeEditor list --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($raw -join [Environment]::NewLine)
    }
    $parsedRecipes = (
        $raw -join [Environment]::NewLine
    ) | ConvertFrom-Json
    return @($parsedRecipes | ForEach-Object { $_ })
}

function Select-ImportedRecipe {
    $recipes = @(Get-ImportedRecipeList)
    if ($recipes.Count -eq 0) {
        throw 'No imported recipes are available to edit.'
    }

    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = 'Select Imported Recipe'
    $dialog.ClientSize = New-Object System.Drawing.Size(680, 165)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $dialog -Palette $colors

    $label = New-Object System.Windows.Forms.Label
    $label.Text = 'Imported recipe'
    $label.Location = New-Object System.Drawing.Point(20, 22)
    $label.Size = New-Object System.Drawing.Size(130, 28)
    $dialog.Controls.Add($label)

    $combo = New-Object System.Windows.Forms.ComboBox
    $combo.Location = New-Object System.Drawing.Point(150, 20)
    $combo.Size = New-Object System.Drawing.Size(500, 28)
    $combo.DropDownStyle = 'DropDownList'
    $combo.DisplayMember = 'Display'
    foreach ($recipe in $recipes) {
        $warning = if ($recipe.kid_reason_is_current) {
            ''
        } else {
            ' [kid reason needs update]'
        }
        $recipe | Add-Member `
            -NotePropertyName Display `
            -NotePropertyValue "$($recipe.id) - $($recipe.name)$warning"
        [void]$combo.Items.Add($recipe)
    }
    $combo.SelectedIndex = 0
    $dialog.Controls.Add($combo)

    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = 'Cancel'
    $cancel.Location = New-Object System.Drawing.Point(435, 95)
    $cancel.Size = New-Object System.Drawing.Size(100, 36)
    $cancel.DialogResult = 'Cancel'
    $dialog.Controls.Add($cancel)
    Set-MealPlannerNeutralButtonStyle -Button $cancel -Palette $colors

    $load = New-Object System.Windows.Forms.Button
    $load.Text = 'Edit Selected'
    $load.Location = New-Object System.Drawing.Point(550, 95)
    $load.Size = New-Object System.Drawing.Size(100, 36)
    $load.DialogResult = 'OK'
    $dialog.Controls.Add($load)
    Set-MealPlannerButtonStyle -Button $load -Color $colors.Review
    $dialog.AcceptButton = $load
    $dialog.CancelButton = $cancel

    if ($dialog.ShowDialog($form) -eq 'OK') {
        return $combo.SelectedItem
    }
    return $null
}

function Load-ImportedRecipe {
    param($Recipe)

    $script:editingRecipeId = [string]$Recipe.id
    $script:editingOriginalRecipe = $Recipe
    $script:editingCardSections = [ordered]@{
        ingredients = [string]$Recipe.card_sections.ingredients
        directions = [string]$Recipe.card_sections.directions
    }
    $script:cardModified = $false
    $script:pastedText = ''
    $sourceText.Text = (
        "$($Recipe.id) rev $($Recipe.revision) | $($Recipe.source)"
    )
    $sourceText.ReadOnly = $true
    $nameText.Text = [string]$Recipe.name
    $proteinCombo.SelectedItem = [string]$Recipe.protein
    $methodCombo.SelectedItem = [string]$Recipe.cooking_method
    $mealScopeCombo.SelectedItem = [string]$Recipe.meal_scope
    $prepMinutes.Value = [decimal]$Recipe.prep_minutes
    $cookMinutes.Value = [decimal]$Recipe.cook_minutes
    $fiberInput.Value = [decimal]$Recipe.fiber_grams
    $costInput.Value = [decimal]$Recipe.estimated_cost_usd
    foreach ($season in @('spring','summer','fall','winter')) {
        $seasonButtons[$season].Checked = (
            @($Recipe.seasons) -contains $season
        )
    }
    if ($Recipe.kid_reason_is_current) {
        $kidReason.SelectedItem = [string]$Recipe.kid_friendly_reason
    } else {
        $kidReason.SelectedIndex = -1
    }

    $warning = if ($Recipe.kid_reason_is_current) {
        'All controlled values are within current guardrails.'
    } else {
        (
            "Legacy kid-friendly reason: " +
            "$($Recipe.kid_friendly_reason)`r`n" +
            'Choose a current reason before saving.'
        )
    }
    $previewText.Text = @(
        "EDITING $($Recipe.id) REV $($Recipe.revision)",
        "Status: $($Recipe.status)",
        "Source: $($Recipe.source)",
        '',
        $warning,
        '',
        'Use Edit Recipe Card to correct ingredients or directions.'
    ) -join [Environment]::NewLine
    $browseButton.Enabled = $false
    $pasteButton.Enabled = $false
    $previewButton.Enabled = $false
    $ideaText.Enabled = $false
    $mexicanMonday.Enabled = $false
    $saveIdeaButton.Enabled = $false
    $saveIdeaButton.Visible = $false
    $promoteButton.Visible = $true
    $promoteButton.Enabled = [string]$Recipe.status -eq 'candidate'
    $editCardButton.Enabled = $true
    $importButton.Text = 'Save Recipe Revision'
    $importButton.Enabled = $true
    $editRecipeButton.Text = 'Cancel Edit'
    $cookbookEditButton.Text = 'Cancel Edit'
    $note.Text = (
        "Saving creates revision $([int]$Recipe.revision + 1). " +
        'Recipe ID, source, ratings, and history are preserved.'
    )
}

function ConvertTo-RecipeEditorText {
    param([string]$Text)

    $normalized = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    return $normalized.Replace("`n", [Environment]::NewLine)
}

function Show-RecipeCardEditor {
    if (
        $null -eq $script:editingRecipeId -or
        $null -eq $script:editingCardSections
    ) {
        throw 'Select an imported recipe before editing its card.'
    }

    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = "Edit Recipe Card - $($script:editingRecipeId)"
    $dialog.ClientSize = New-Object System.Drawing.Size(820, 700)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $dialog -Palette $colors

    $help = New-Object System.Windows.Forms.Label
    $help.Text = (
        'Edit list items and steps directly. Keep the Main Ingredients and ' +
        'Seasonings subheadings. Long lines wrap visually; protected history ' +
        'and ratings are not shown.'
    )
    $help.Location = New-Object System.Drawing.Point(20, 18)
    $help.Size = New-Object System.Drawing.Size(780, 42)
    $help.ForeColor = $colors.Muted
    $dialog.Controls.Add($help)

    $ingredientsLabel = New-Object System.Windows.Forms.Label
    $ingredientsLabel.Text = 'Ingredients'
    $ingredientsLabel.Location = New-Object System.Drawing.Point(20, 68)
    $ingredientsLabel.Size = New-Object System.Drawing.Size(120, 24)
    $ingredientsLabel.ForeColor = $colors.Email
    $dialog.Controls.Add($ingredientsLabel)

    $ingredientsEditor = New-Object System.Windows.Forms.RichTextBox
    $ingredientsEditor.Location = New-Object System.Drawing.Point(20, 94)
    $ingredientsEditor.Size = New-Object System.Drawing.Size(780, 235)
    $ingredientsEditor.AcceptsTab = $false
    $ingredientsEditor.ScrollBars = 'Vertical'
    $ingredientsEditor.WordWrap = $true
    $ingredientsEditor.DetectUrls = $false
    $ingredientsEditor.Font = New-Object System.Drawing.Font('Segoe UI', 10.5)
    $ingredientsEditor.BackColor = $colors.SoftPantry
    $ingredientsEditor.Text = ConvertTo-RecipeEditorText `
        ([string]$script:editingCardSections.ingredients)
    $dialog.Controls.Add($ingredientsEditor)

    $directionsLabel = New-Object System.Windows.Forms.Label
    $directionsLabel.Text = 'Directions'
    $directionsLabel.Location = New-Object System.Drawing.Point(20, 345)
    $directionsLabel.Size = New-Object System.Drawing.Size(120, 24)
    $directionsLabel.ForeColor = $colors.Email
    $dialog.Controls.Add($directionsLabel)

    $directionsEditor = New-Object System.Windows.Forms.RichTextBox
    $directionsEditor.Location = New-Object System.Drawing.Point(20, 371)
    $directionsEditor.Size = New-Object System.Drawing.Size(780, 235)
    $directionsEditor.AcceptsTab = $false
    $directionsEditor.ScrollBars = 'Vertical'
    $directionsEditor.WordWrap = $true
    $directionsEditor.DetectUrls = $false
    $directionsEditor.Font = New-Object System.Drawing.Font('Segoe UI', 10.5)
    $directionsEditor.BackColor = $colors.SoftEmail
    $directionsEditor.Text = ConvertTo-RecipeEditorText `
        ([string]$script:editingCardSections.directions)
    $dialog.Controls.Add($directionsEditor)

    $saveCardButton = New-Object System.Windows.Forms.Button
    $saveCardButton.Text = 'Use Card Changes'
    $saveCardButton.Location = New-Object System.Drawing.Point(610, 630)
    $saveCardButton.Size = New-Object System.Drawing.Size(190, 42)
    $saveCardButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dialog.Controls.Add($saveCardButton)
    Set-MealPlannerButtonStyle -Button $saveCardButton -Color $colors.Email

    $cancelCardButton = New-Object System.Windows.Forms.Button
    $cancelCardButton.Text = 'Cancel'
    $cancelCardButton.Location = New-Object System.Drawing.Point(490, 630)
    $cancelCardButton.Size = New-Object System.Drawing.Size(105, 42)
    $cancelCardButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dialog.Controls.Add($cancelCardButton)
    Set-MealPlannerNeutralButtonStyle `
        -Button $cancelCardButton `
        -Palette $colors
    $dialog.CancelButton = $cancelCardButton
    Add-MealPlannerBranding `
        -Form $dialog `
        -Title 'Recipe Card Editor' `
        -Subtitle "$($script:editingRecipeId) ingredients and directions" `
        -IconName 'recipe-cookbook'

    if (
        $dialog.ShowDialog($form) -eq
        [System.Windows.Forms.DialogResult]::OK
    ) {
        if ([string]::IsNullOrWhiteSpace($ingredientsEditor.Text)) {
            throw 'Ingredients cannot be empty.'
        }
        if ([string]::IsNullOrWhiteSpace($directionsEditor.Text)) {
            throw 'Directions cannot be empty.'
        }
        $script:editingCardSections.ingredients = $ingredientsEditor.Text
        $script:editingCardSections.directions = $directionsEditor.Text
        $script:cardModified = $true
        $previewText.Text = (
            $previewText.Text.TrimEnd() +
            "`r`n`r`nRecipe card changes are staged for this revision."
        )
    }
}

function Show-PromotionDialog {
    if ($null -eq $script:editingOriginalRecipe) {
        throw 'Select an imported recipe before promotion.'
    }
    if ([string]$script:editingOriginalRecipe.status -ne 'candidate') {
        throw 'Only candidate recipes can be promoted.'
    }

    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = "Approve Recipe - $($script:editingRecipeId)"
    $dialog.ClientSize = New-Object System.Drawing.Size(560, 245)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $dialog -Palette $colors

    $actorLabel = New-Object System.Windows.Forms.Label
    $actorLabel.Text = 'Approved by'
    $actorLabel.Location = New-Object System.Drawing.Point(20, 25)
    $actorLabel.Size = New-Object System.Drawing.Size(110, 28)
    $dialog.Controls.Add($actorLabel)

    $actorInput = New-Object System.Windows.Forms.TextBox
    $actorInput.Location = New-Object System.Drawing.Point(135, 23)
    $actorInput.Size = New-Object System.Drawing.Size(400, 28)
    $actorInput.Text = $env:USERNAME
    $dialog.Controls.Add($actorInput)

    $reasonLabel = New-Object System.Windows.Forms.Label
    $reasonLabel.Text = 'Approval reason'
    $reasonLabel.Location = New-Object System.Drawing.Point(20, 70)
    $reasonLabel.Size = New-Object System.Drawing.Size(110, 28)
    $dialog.Controls.Add($reasonLabel)

    $reasonInput = New-Object System.Windows.Forms.TextBox
    $reasonInput.Location = New-Object System.Drawing.Point(135, 68)
    $reasonInput.Size = New-Object System.Drawing.Size(400, 90)
    $reasonInput.Multiline = $true
    $reasonInput.ScrollBars = 'Vertical'
    $dialog.Controls.Add($reasonInput)

    $approveButton = New-Object System.Windows.Forms.Button
    $approveButton.Text = 'Promote'
    $approveButton.Location = New-Object System.Drawing.Point(325, 185)
    $approveButton.Size = New-Object System.Drawing.Size(100, 38)
    $approveButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dialog.Controls.Add($approveButton)
    Set-MealPlannerButtonStyle -Button $approveButton -Color $colors.Planner

    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = 'Cancel'
    $cancel.Location = New-Object System.Drawing.Point(435, 185)
    $cancel.Size = New-Object System.Drawing.Size(100, 38)
    $cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dialog.Controls.Add($cancel)
    Set-MealPlannerNeutralButtonStyle -Button $cancel -Palette $colors

    $dialog.AcceptButton = $approveButton
    $dialog.CancelButton = $cancel
    if (
        $dialog.ShowDialog($form) -ne
        [System.Windows.Forms.DialogResult]::OK
    ) {
        return $null
    }
    if ([string]::IsNullOrWhiteSpace($actorInput.Text)) {
        throw 'Approved by is required.'
    }
    if ([string]::IsNullOrWhiteSpace($reasonInput.Text)) {
        throw 'Approval reason is required.'
    }
    return [pscustomobject]@{
        Actor = $actorInput.Text.Trim()
        Reason = $reasonInput.Text.Trim()
    }
}

$browseButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = 'Text and Markdown|*.txt;*.md|All files|*.*'
    if ($dialog.ShowDialog() -eq 'OK') {
        $script:pastedText = ''
        $sourceText.Text = $dialog.FileName
        $importButton.Enabled = $false
    }
})
$pasteButton.Add_Click({ Show-PasteEditor })
$editRecipeButton.Add_Click({
    try {
        if ($null -ne $script:editingRecipeId) {
            Reset-ImportForm
            return
        }
        $recipe = Select-ImportedRecipe
        if ($null -ne $recipe) {
            Load-ImportedRecipe -Recipe $recipe
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Load Imported Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})
$editCardButton.Add_Click({
    try {
        Show-RecipeCardEditor
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Edit Recipe Card',
            'OK',
            'Error'
        ) | Out-Null
    }
})
$promoteButton.Add_Click({
    try {
        $approval = Show-PromotionDialog
        if ($null -eq $approval) {
            return
        }
        New-MealPlannerGuiBackup `
            -ProjectRoot $projectRoot `
            -Operation "recipe-promote-$($script:editingRecipeId)" |
            Out-Null
        $result = & $python $recipeEditor promote `
            --id $script:editingRecipeId `
            --actor $approval.Actor `
            --note $approval.Reason 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ($result -join [Environment]::NewLine)
        }
        [System.Windows.Forms.MessageBox]::Show(
            (
                "Recipe promoted to approved:`r`n$($result -join '')`r`n`r`n" +
                'The status, revision history, and recipe index were updated.'
            ),
            'Recipe Approved',
            'OK',
            'Information'
        ) | Out-Null
        Reset-ImportForm
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Promote Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$previewButton.Add_Click({
    try {
        if ([string]::IsNullOrWhiteSpace($sourceText.Text)) { throw 'Choose a file or enter a URL.' }
        if (
            $sourceText.Text -like 'Pasted recipe text (*' -and
            -not [string]::IsNullOrWhiteSpace($script:pastedText)
        ) {
            $raw = $script:pastedText | & $python $importer preview --stdin --json 2>&1
        } else {
            $raw = & $python $importer preview --source $sourceText.Text --json 2>&1
        }
        if ($LASTEXITCODE -ne 0) { throw ($raw -join [Environment]::NewLine) }
        $preview = ($raw -join [Environment]::NewLine) | ConvertFrom-Json
        $nameText.Text = $preview.name
        if ([double]$preview.fiber_grams -gt 0) { $fiberInput.Value = [decimal]$preview.fiber_grams }
        if ([int]$preview.prep_minutes -gt 0) { $prepMinutes.Value = [decimal]$preview.prep_minutes }
        if ([int]$preview.cook_minutes -gt 0) { $cookMinutes.Value = [decimal]$preview.cook_minutes }
        $lines = @(
            "Parser: $($preview.parser)",
            "Name: $($preview.name)",
            "Servings: $($preview.servings)",
            "Prep: $($preview.prep_minutes) min; Cook: $($preview.cook_minutes) min",
            '',
            'INGREDIENTS',
            ($preview.ingredients | ForEach-Object { "- $_" }),
            '',
            'DIRECTIONS',
            ($preview.directions | ForEach-Object { "- $_" })
        )
        $previewText.Text = $lines -join [Environment]::NewLine
        $importButton.Enabled = $true
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Preview Failed','OK','Error') | Out-Null
    }
})

$importButton.Add_Click({
    try {
        if ([string]::IsNullOrWhiteSpace($nameText.Text)) { throw 'Recipe name is required.' }
        if ($proteinCombo.SelectedIndex -eq 0) { throw 'Select a protein.' }
        if ([string]::IsNullOrWhiteSpace($kidReason.Text)) { throw 'Kid-friendly reason is required.' }
        if ($null -ne $script:editingRecipeId) {
            $diff = Get-RecipeEditDiff
            $answer = [System.Windows.Forms.MessageBox]::Show(
                (
                    "Review changes before saving:`r`n`r`n$diff`r`n`r`n" +
                    'Create this recipe revision?'
                ),
                'Confirm Recipe Revision',
                'YesNo',
                'Warning'
            )
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
                return
            }
            $temporaryCardPath = $null
            $arguments = @(
                $recipeEditor,
                'update',
                '--id', $script:editingRecipeId,
                '--name', $nameText.Text,
                '--protein', [string]$proteinCombo.SelectedItem,
                '--meal-scope', [string]$mealScopeCombo.SelectedItem,
                '--prep-minutes', [string]$prepMinutes.Value,
                '--cook-minutes', [string]$cookMinutes.Value,
                '--fiber', [string]$fiberInput.Value,
                '--cost', [string]$costInput.Value,
                '--kid-reason', $kidReason.Text,
                '--method', [string]$methodCombo.SelectedItem,
                '--seasons', (Get-SelectedSeasons)
            )
            try {
                if ($script:cardModified) {
                    $temporaryCardPath = [System.IO.Path]::GetTempFileName()
                    $cardJson = $script:editingCardSections |
                        ConvertTo-Json -Depth 4
                    [System.IO.File]::WriteAllText(
                        $temporaryCardPath,
                        $cardJson,
                        (New-Object System.Text.UTF8Encoding($false))
                    )
                    $arguments += @(
                        '--card-file', $temporaryCardPath,
                        '--change-note',
                        'Updated imported recipe metadata and recipe card through the GUI'
                    )
                }
                New-MealPlannerGuiBackup `
                    -ProjectRoot $projectRoot `
                    -Operation "recipe-edit-$($script:editingRecipeId)" |
                    Out-Null
                $result = & $python @arguments 2>&1
            } finally {
                if (
                    $null -ne $temporaryCardPath -and
                    (Test-Path -LiteralPath $temporaryCardPath)
                ) {
                    Remove-Item -LiteralPath $temporaryCardPath
                }
            }
            if ($LASTEXITCODE -ne 0) {
                throw ($result -join [Environment]::NewLine)
            }
            [System.Windows.Forms.MessageBox]::Show(
                (
                    "Saved recipe revision:`n$($result -join '')`n`n" +
                    'The importer is ready for another entry.'
                ),
                'Recipe Revision Saved',
                'OK',
                'Information'
            ) | Out-Null
            Reset-ImportForm
            return
        }
        $arguments = @($importer,'apply')
        $usingPastedText = (
            $sourceText.Text -like 'Pasted recipe text (*' -and
            -not [string]::IsNullOrWhiteSpace($script:pastedText)
        )
        if ($usingPastedText) {
            $arguments += '--stdin'
        } else {
            $arguments += @('--source',$sourceText.Text)
        }
        $arguments += @(
            '--name',$nameText.Text,
            '--protein',[string]$proteinCombo.SelectedItem,
            '--meal-scope',[string]$mealScopeCombo.SelectedItem,
            '--method',[string]$methodCombo.SelectedItem,
            '--prep-minutes',[string]$prepMinutes.Value,
            '--cook-minutes',[string]$cookMinutes.Value,
            '--fiber',[string]$fiberInput.Value,
            '--cost',[string]$costInput.Value,
            '--kid-score',[string]$kidScore.SelectedItem,
            '--kid-reason',$kidReason.Text,
            '--seasons',(Get-SelectedSeasons)
        )
        New-MealPlannerGuiBackup `
            -ProjectRoot $projectRoot `
            -Operation 'recipe-import' | Out-Null
        if ($usingPastedText) {
            $result = $script:pastedText | & $python @arguments 2>&1
        } else {
            $result = & $python @arguments 2>&1
        }
        if ($LASTEXITCODE -ne 0) { throw ($result -join [Environment]::NewLine) }
        [System.Windows.Forms.MessageBox]::Show(
            "Imported candidate:`n$($result -join '')`n`nThe importer is ready for another recipe.",
            'Recipe Imported','OK','Information'
        ) | Out-Null
        Reset-ImportForm
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Import Failed','OK','Error') | Out-Null
    }
})

$saveIdeaButton.Add_Click({
    try {
        if ([string]::IsNullOrWhiteSpace($ideaText.Text)) { throw 'Enter a recipe idea.' }
        if ([string]::IsNullOrWhiteSpace($nameText.Text)) { throw 'Enter a short recipe name.' }
        if ($proteinCombo.SelectedIndex -eq 0) { throw 'Select a protein.' }
        if ([string]::IsNullOrWhiteSpace($kidReason.Text)) { throw 'Kid-friendly reason is required.' }
        $arguments = @(
            $ideaManager,'add',
            '--idea',$ideaText.Text,
            '--name',$nameText.Text,
            '--protein',[string]$proteinCombo.SelectedItem,
            '--meal-scope',[string]$mealScopeCombo.SelectedItem,
            '--method',[string]$methodCombo.SelectedItem,
            '--fiber',[string]$fiberInput.Value,
            '--cost',[string]$costInput.Value,
            '--kid-score',[string]$kidScore.SelectedItem,
            '--kid-reason',$kidReason.Text,
            '--seasons',(Get-SelectedSeasons)
        )
        if ($mexicanMonday.Checked) { $arguments += '--mexican-monday' }
        New-MealPlannerGuiBackup `
            -ProjectRoot $projectRoot `
            -Operation 'recipe-idea-save' | Out-Null
        $result = & $python @arguments 2>&1
        if ($LASTEXITCODE -ne 0) { throw ($result -join [Environment]::NewLine) }
        [System.Windows.Forms.MessageBox]::Show(
            "Saved recipe idea $($result -join ''). It will be prioritized in compatible dry runs.`n`nThe importer is ready for another entry.",
            'Recipe Idea Saved','OK','Information'
        ) | Out-Null
        Reset-ImportForm
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Unable to Save Idea','OK','Error') | Out-Null
    }
})

$form.CancelButton = $closeButton
$previewText.Height -= 100
foreach ($control in @($form.Controls)) {
    if ($control.Top -ge 310) {
        $control.Top -= 100
    }
}
$form.ClientSize = New-Object System.Drawing.Size(
    $form.ClientSize.Width,
    ($form.ClientSize.Height - 40)
)
Set-MealPlannerNeutralButtonStyle -Button $browseButton -Palette $colors
Set-MealPlannerButtonStyle -Button $pasteButton -Color $colors.Email
Set-MealPlannerButtonStyle -Button $previewButton -Color $colors.Planner
Set-MealPlannerButtonStyle -Button $editRecipeButton -Color $colors.Review
Set-MealPlannerButtonStyle -Button $editCardButton -Color $colors.Review
Set-MealPlannerButtonStyle -Button $promoteButton -Color $colors.Planner
Set-MealPlannerButtonStyle -Button $saveIdeaButton -Color $colors.Pantry
Set-MealPlannerButtonStyle -Button $importButton -Color $colors.Email
Set-MealPlannerNeutralButtonStyle -Button $closeButton -Palette $colors
$previewText.BackColor = $colors.SoftEmail
$previewText.ForeColor = $colors.Text
$ideaText.BackColor = $colors.SoftPantry
$note.BackColor = $colors.SoftEmail
$note.ForeColor = $colors.Email
$note.Padding = New-Object System.Windows.Forms.Padding(10)

$importControls = @($form.Controls)
$importPanel = New-Object System.Windows.Forms.Panel
$importPanel.Location = New-Object System.Drawing.Point(0, 58)
$importPanel.Size = New-Object System.Drawing.Size(900, 700)
$importPanel.AutoScroll = $true
$importPanel.Visible = $false
foreach ($control in $importControls) {
    $importPanel.Controls.Add($control)
}
$form.Controls.Add($importPanel)

function Get-CookbookRecipes {
    $json = @(
        & $reviewModule -ListRecipes -Json
    ) -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($json)) {
        return @()
    }
    $parsed = $json | ConvertFrom-Json
    $records = @($parsed | ForEach-Object { $_ })
    foreach ($record in $records) {
        $record | Add-Member `
            -NotePropertyName Display `
            -NotePropertyValue (
                "$($record.Id) - $($record.Name) " +
                "(rev $($record.Revision), $($record.Status))"
            ) `
            -Force
    }
    return $records
}

$cookbookLabel = New-Object System.Windows.Forms.Label
$cookbookLabel.Text = 'Recipe'
$cookbookLabel.Location = New-Object System.Drawing.Point(20, 20)
$cookbookLabel.Size = New-Object System.Drawing.Size(60, 30)
$cookbookLabel.TextAlign = 'MiddleLeft'
$form.Controls.Add($cookbookLabel)

$cookbookRecipeCombo = New-Object System.Windows.Forms.ComboBox
$cookbookRecipeCombo.Location = New-Object System.Drawing.Point(82, 20)
$cookbookRecipeCombo.Size = New-Object System.Drawing.Size(260, 28)
$cookbookRecipeCombo.DropDownStyle = 'DropDownList'
$cookbookRecipeCombo.DisplayMember = 'Display'
$form.Controls.Add($cookbookRecipeCombo)

function Refresh-CookbookRecipes {
    param([string]$SelectedId)

    $cookbookRecipeCombo.BeginUpdate()
    try {
        $cookbookRecipeCombo.Items.Clear()
        foreach ($recipe in Get-CookbookRecipes) {
            [void]$cookbookRecipeCombo.Items.Add($recipe)
        }
    } finally {
        $cookbookRecipeCombo.EndUpdate()
    }
    if ($cookbookRecipeCombo.Items.Count -eq 0) {
        return
    }
    $selectedIndex = 0
    if (-not [string]::IsNullOrWhiteSpace($SelectedId)) {
        for (
            $index = 0;
            $index -lt $cookbookRecipeCombo.Items.Count;
            $index++
        ) {
            if ($cookbookRecipeCombo.Items[$index].Id -eq $SelectedId) {
                $selectedIndex = $index
                break
            }
        }
    }
    $cookbookRecipeCombo.SelectedIndex = $selectedIndex
}

function Get-SelectedCookbookRecipeId {
    if ($null -eq $cookbookRecipeCombo.SelectedItem) {
        throw 'Select a recipe.'
    }
    return [string]$cookbookRecipeCombo.SelectedItem.Id
}

function Invoke-CookbookRecipeAction {
    param(
        [ValidateSet('View', 'Print', 'Export', 'Review')]
        [string]$Action
    )

    $recipeId = Get-SelectedCookbookRecipeId
    & $reviewModule -RecipeId $recipeId -InitialAction $Action
    if ($Action -eq 'Review') {
        Refresh-CookbookRecipes -SelectedId $recipeId
    }
}

function Set-ImportWorkspaceVisible {
    param([bool]$Visible)

    $importPanel.Visible = $Visible
    $libraryPreviewPanel.Visible = -not $Visible
    if ($Visible) {
        $showImportButton.Text = 'Hide Import'
        $form.ClientSize = New-Object System.Drawing.Size(900, 820)
    } else {
        $showImportButton.Text = 'Import Recipe'
        $form.ClientSize = New-Object System.Drawing.Size(900, 500)
    }
}

function Edit-SelectedCookbookRecipe {
    if ($null -ne $script:editingRecipeId) {
        Reset-ImportForm
        return
    }

    $selectedRecipe = $cookbookRecipeCombo.SelectedItem
    $recipeId = Get-SelectedCookbookRecipeId
    if ([string]$selectedRecipe.Status -eq 'approved') {
        throw (
            "$recipeId is approved and protected from direct editing. " +
            'Use Review to record requested changes before creating a new ' +
            'candidate revision.'
        )
    }
    $editableRecipes = @(Get-ImportedRecipeList)
    $recipe = @(
        $editableRecipes |
            Where-Object { [string]$_.id -eq $recipeId }
    ) | Select-Object -First 1
    if ($null -eq $recipe) {
        throw (
            "$recipeId could not be loaded by the guarded recipe editor. " +
            'Validate or repair its recipe-card structure before editing.'
        )
    }
    Load-ImportedRecipe -Recipe $recipe
    Set-ImportWorkspaceVisible -Visible $true
}

function New-CookbookButton {
    param(
        [string]$Text,
        [int]$X,
        [int]$Width,
        [System.Drawing.Color]$Color
    )

    $button = New-Object System.Windows.Forms.Button
    $button.Text = $Text
    $button.Location = New-Object System.Drawing.Point($X, 17)
    $button.Size = New-Object System.Drawing.Size($Width, 36)
    $form.Controls.Add($button)
    Set-MealPlannerButtonStyle -Button $button -Color $Color
    return $button
}

$cookbookFindButton = New-CookbookButton `
    -Text 'Find' -X 350 -Width 58 -Color $colors.Planner
$cookbookViewButton = New-CookbookButton `
    -Text 'View' -X 414 -Width 58 -Color $colors.Review
$cookbookPrintButton = New-CookbookButton `
    -Text 'Print' -X 478 -Width 58 -Color $colors.Pantry
$cookbookExportButton = New-CookbookButton `
    -Text 'Export' -X 542 -Width 64 -Color $colors.Email
$cookbookReviewButton = New-CookbookButton `
    -Text 'Review' -X 612 -Width 70 -Color $colors.Review
$cookbookEditButton = New-CookbookButton `
    -Text 'Edit' -X 688 -Width 70 -Color $colors.Planner
$showImportButton = New-CookbookButton `
    -Text 'Import Recipe' -X 764 -Width 116 -Color $colors.Email

$libraryPreviewPanel = New-Object System.Windows.Forms.Panel
$libraryPreviewPanel.Location = New-Object System.Drawing.Point(0, 58)
$libraryPreviewPanel.Size = New-Object System.Drawing.Size(900, 365)
$libraryPreviewPanel.BackColor = $colors.Surface
$form.Controls.Add($libraryPreviewPanel)

$cookbookPhoto = New-Object System.Windows.Forms.PictureBox
$cookbookPhoto.Location = New-Object System.Drawing.Point(20, 20)
$cookbookPhoto.Size = New-Object System.Drawing.Size(300, 270)
$cookbookPhoto.SizeMode = 'Zoom'
$cookbookPhoto.BorderStyle = 'FixedSingle'
$cookbookPhoto.BackColor = $colors.SoftMuted
$libraryPreviewPanel.Controls.Add($cookbookPhoto)

$cookbookTitle = New-Object System.Windows.Forms.Label
$cookbookTitle.Location = New-Object System.Drawing.Point(345, 22)
$cookbookTitle.Size = New-Object System.Drawing.Size(525, 48)
$cookbookTitle.Font = New-Object System.Drawing.Font(
    'Segoe UI Semibold',
    17,
    [System.Drawing.FontStyle]::Bold
)
$cookbookTitle.ForeColor = $colors.Text
$libraryPreviewPanel.Controls.Add($cookbookTitle)

$cookbookDetails = New-Object System.Windows.Forms.Label
$cookbookDetails.Location = New-Object System.Drawing.Point(345, 85)
$cookbookDetails.Size = New-Object System.Drawing.Size(525, 175)
$cookbookDetails.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$cookbookDetails.ForeColor = $colors.Text
$libraryPreviewPanel.Controls.Add($cookbookDetails)

$changeImageButton = New-Object System.Windows.Forms.Button
$changeImageButton.Text = 'Change Image'
$changeImageButton.Location = New-Object System.Drawing.Point(20, 305)
$changeImageButton.Size = New-Object System.Drawing.Size(140, 38)
$libraryPreviewPanel.Controls.Add($changeImageButton)
Set-MealPlannerButtonStyle -Button $changeImageButton -Color $colors.Email

$photoHint = New-Object System.Windows.Forms.Label
$photoHint.Text = 'JPG, PNG, or BMP'
$photoHint.Location = New-Object System.Drawing.Point(175, 312)
$photoHint.Size = New-Object System.Drawing.Size(145, 24)
$photoHint.ForeColor = $colors.Muted
$libraryPreviewPanel.Controls.Add($photoHint)

function Get-CookbookImagePath {
    param([string]$RecipeId)

    foreach ($extension in @('.png', '.jpg', '.jpeg', '.bmp')) {
        $path = Join-Path $recipeAssetsRoot "$RecipeId$extension"
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return $null
}

function Set-CookbookPhoto {
    param([string]$Path)

    if ($null -ne $cookbookPhoto.Image) {
        $cookbookPhoto.Image.Dispose()
        $cookbookPhoto.Image = $null
    }
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    $source = [System.Drawing.Image]::FromFile($Path)
    try {
        $cookbookPhoto.Image = New-Object System.Drawing.Bitmap($source)
    } finally {
        $source.Dispose()
    }
}

function Update-CookbookPreview {
    if ($null -eq $cookbookRecipeCombo.SelectedItem) {
        $cookbookTitle.Text = 'No recipes available'
        $cookbookDetails.Text = ''
        Set-CookbookPhoto -Path $null
        return
    }
    $recipe = $cookbookRecipeCombo.SelectedItem
    $cookbookTitle.Text = [string]$recipe.Name
    $rating = if ([double]$recipe.Rating -gt 0) {
        "$([double]$recipe.Rating) / 5"
    } else {
        'Not rated'
    }
    $cookbookDetails.Text = @(
        "Recipe ID: $($recipe.Id)",
        "Status: $($recipe.Status)",
        "Revision: $($recipe.Revision)",
        "Protein: $($recipe.Protein)",
        "Cooking method: $($recipe.Method)",
        "Seasons: $(@($recipe.Seasons) -join ', ')",
        "Family rating: $rating"
    ) -join [Environment]::NewLine
    Set-CookbookPhoto -Path (
        Get-CookbookImagePath -RecipeId ([string]$recipe.Id)
    )
}

$cookbookRecipeCombo.Add_SelectedIndexChanged({
    Update-CookbookPreview
})

$changeImageButton.Add_Click({
    try {
        $recipeId = Get-SelectedCookbookRecipeId
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = "Choose Image for $recipeId"
        $dialog.Filter = (
            'Recipe images|*.png;*.jpg;*.jpeg;*.bmp|' +
            'All files|*.*'
        )
        try {
            if (
                $dialog.ShowDialog($form) -ne
                [System.Windows.Forms.DialogResult]::OK
            ) {
                return
            }
            New-MealPlannerGuiBackup `
                -ProjectRoot $projectRoot `
                -Operation "recipe-image-$recipeId" `
                -Paths @('assets\recipes') | Out-Null
            [System.IO.Directory]::CreateDirectory(
                $recipeAssetsRoot
            ) | Out-Null
            $target = Join-Path $recipeAssetsRoot "$recipeId.png"
            $temporary = Join-Path $recipeAssetsRoot "$recipeId.new.png"
            $source = [System.Drawing.Image]::FromFile($dialog.FileName)
            try {
                $bitmap = New-Object System.Drawing.Bitmap($source)
            } finally {
                $source.Dispose()
            }
            try {
                $bitmap.Save(
                    $temporary,
                    [System.Drawing.Imaging.ImageFormat]::Png
                )
            } finally {
                $bitmap.Dispose()
            }
            Move-Item -LiteralPath $temporary -Destination $target -Force
            Set-CookbookPhoto -Path $target
        } finally {
            $dialog.Dispose()
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Change Recipe Image',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$cookbookFindButton.Add_Click({
    try {
        $selectedId = @(
            & $reviewModule -InitialAction Find
        ) | Select-Object -Last 1
        if (-not [string]::IsNullOrWhiteSpace($selectedId)) {
            Refresh-CookbookRecipes -SelectedId ([string]$selectedId)
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Find Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})
$cookbookViewButton.Add_Click({
    try { Invoke-CookbookRecipeAction -Action View }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'Unable to View Recipe', 'OK', 'Error'
        ) | Out-Null
    }
})
$cookbookPrintButton.Add_Click({
    try { Invoke-CookbookRecipeAction -Action Print }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'Unable to Print Recipe', 'OK', 'Error'
        ) | Out-Null
    }
})
$cookbookExportButton.Add_Click({
    try { Invoke-CookbookRecipeAction -Action Export }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'Unable to Export Recipe', 'OK', 'Error'
        ) | Out-Null
    }
})
$cookbookReviewButton.Add_Click({
    try { Invoke-CookbookRecipeAction -Action Review }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'Unable to Review Recipe', 'OK', 'Error'
        ) | Out-Null
    }
})
$cookbookEditButton.Add_Click({
    try { Edit-SelectedCookbookRecipe }
    catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'Unable to Edit Recipe', 'OK', 'Information'
        ) | Out-Null
    }
})
$showImportButton.Add_Click({
    Set-ImportWorkspaceVisible -Visible (-not $importPanel.Visible)
})

Refresh-CookbookRecipes
$form.Add_FormClosed({
    if ($null -ne $cookbookPhoto.Image) {
        $cookbookPhoto.Image.Dispose()
    }
})
$form.ClientSize = New-Object System.Drawing.Size(900, 500)
Add-MealPlannerBranding `
    -Form $form `
    -Title 'Recipe Cookbook' `
    -Subtitle 'Browse, import, edit, and approve family recipes' `
    -IconName 'recipe-cookbook' `
    -PreserveClientHeight
[void]$form.ShowDialog()
