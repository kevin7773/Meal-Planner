Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'gui-backup.ps1')
$overrideScript = Join-Path $PSScriptRoot 'meal_override.py'

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
$form.Text = 'Override Planned Meal'
$form.ClientSize = New-Object System.Drawing.Size(760, 570)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
Set-MealPlannerFormSurface -Form $form -Palette $colors

function Add-Label([string]$Text, [int]$X, [int]$Y, [int]$Width = 130) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($Width, 28)
    $label.TextAlign = 'MiddleLeft'
    $form.Controls.Add($label)
}

Add-Label 'Weekly menu' 20 25
$menuCombo = New-Object System.Windows.Forms.ComboBox
$menuCombo.Location = New-Object System.Drawing.Point(150, 25)
$menuCombo.Size = New-Object System.Drawing.Size(580, 28)
$menuCombo.DropDownStyle = 'DropDownList'
$menuFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'menus') -Recurse -File -Filter '*.md' |
    Sort-Object LastWriteTime -Descending
foreach ($file in $menuFiles) {
    [void]$menuCombo.Items.Add($file)
}
$menuCombo.DisplayMember = 'FullName'
$form.Controls.Add($menuCombo)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(20, 70)
$statusLabel.Size = New-Object System.Drawing.Size(710, 42)
$statusLabel.BorderStyle = 'FixedSingle'
$statusLabel.Padding = New-Object System.Windows.Forms.Padding(8)
$form.Controls.Add($statusLabel)

Add-Label 'Day' 20 130
$dayCombo = New-Object System.Windows.Forms.ComboBox
$dayCombo.Location = New-Object System.Drawing.Point(150, 130)
$dayCombo.Size = New-Object System.Drawing.Size(580, 28)
$dayCombo.DropDownStyle = 'DropDownList'
$dayCombo.DisplayMember = 'Display'
$form.Controls.Add($dayCombo)

Add-Label 'Override type' 20 175
$typeCombo = New-Object System.Windows.Forms.ComboBox
$typeCombo.Location = New-Object System.Drawing.Point(150, 175)
$typeCombo.Size = New-Object System.Drawing.Size(220, 28)
$typeCombo.DropDownStyle = 'DropDownList'
@('dining-out','special-occasion','skip','custom','alternate-recipe') |
    ForEach-Object { [void]$typeCombo.Items.Add($_) }
$typeCombo.SelectedIndex = 0
$form.Controls.Add($typeCombo)

Add-Label 'Replacement' 400 175 100
$recipeCombo = New-Object System.Windows.Forms.ComboBox
$recipeCombo.Location = New-Object System.Drawing.Point(500, 175)
$recipeCombo.Size = New-Object System.Drawing.Size(230, 28)
$recipeCombo.DropDownStyle = 'DropDownList'
$recipeCombo.DisplayMember = 'Display'
$recipeCombo.Enabled = $false
$form.Controls.Add($recipeCombo)

Add-Label 'Display title' 20 220
$titleText = New-Object System.Windows.Forms.TextBox
$titleText.Location = New-Object System.Drawing.Point(150, 220)
$titleText.Size = New-Object System.Drawing.Size(580, 28)
$form.Controls.Add($titleText)

Add-Label 'Details' 20 265
$noteText = New-Object System.Windows.Forms.TextBox
$noteText.Location = New-Object System.Drawing.Point(150, 265)
$noteText.Size = New-Object System.Drawing.Size(580, 110)
$noteText.Multiline = $true
$noteText.ScrollBars = 'Vertical'
$form.Controls.Add($noteText)

Add-Label 'Changed by' 20 400
$actorText = New-Object System.Windows.Forms.TextBox
$actorText.Location = New-Object System.Drawing.Point(150, 400)
$actorText.Size = New-Object System.Drawing.Size(220, 28)
$actorText.Text = $env:USERNAME
$form.Controls.Add($actorText)

$warningLabel = New-Object System.Windows.Forms.Label
$warningLabel.Location = New-Object System.Drawing.Point(20, 450)
$warningLabel.Size = New-Object System.Drawing.Size(710, 48)
$warningLabel.Text = 'Overrides preserve the original meal, update its email draft, add grocery deltas, and return the week to draft.'
$warningLabel.ForeColor = [System.Drawing.Color]::DarkGoldenrod
$form.Controls.Add($warningLabel)

$applyButton = New-Object System.Windows.Forms.Button
$applyButton.Text = 'Apply Override'
$applyButton.Location = New-Object System.Drawing.Point(485, 510)
$applyButton.Size = New-Object System.Drawing.Size(130, 38)
$applyButton.Enabled = $false
$form.Controls.Add($applyButton)
$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = 'Close'
$closeButton.Location = New-Object System.Drawing.Point(630, 510)
$closeButton.Size = New-Object System.Drawing.Size(100, 38)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$script:inspection = $null
function Load-Menu {
    try {
        if ($null -eq $menuCombo.SelectedItem) { return }
        $raw = & $python $overrideScript inspect --menu $menuCombo.SelectedItem.FullName 2>&1
        if ($LASTEXITCODE -ne 0) { throw ($raw -join [Environment]::NewLine) }
        $script:inspection = ($raw -join [Environment]::NewLine) | ConvertFrom-Json
        $statusLabel.Text = "Week of $($script:inspection.week_of) | Status: $($script:inspection.status)"
        $dayCombo.Items.Clear()
        foreach ($day in $script:inspection.days) {
            $day | Add-Member -NotePropertyName Display -NotePropertyValue "$($day.day): $($day.title)"
            [void]$dayCombo.Items.Add($day)
        }
        if ($dayCombo.Items.Count -gt 0) { $dayCombo.SelectedIndex = 0 }
        $recipeCombo.Items.Clear()
        foreach ($recipe in $script:inspection.recipes) {
            $recipe | Add-Member -NotePropertyName Display -NotePropertyValue "$($recipe.id) - $($recipe.name)"
            [void]$recipeCombo.Items.Add($recipe)
        }
        if ($recipeCombo.Items.Count -gt 0) { $recipeCombo.SelectedIndex = 0 }
        $applyButton.Enabled = $script:inspection.status -notin @('completed','archived')
        if (-not $applyButton.Enabled) {
            $statusLabel.Text += ' | Closed weeks cannot be overridden'
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Unable to Load Menu','OK','Error') | Out-Null
    }
}

$menuCombo.Add_SelectedIndexChanged({ Load-Menu })
$typeCombo.Add_SelectedIndexChanged({
    $recipeCombo.Enabled = [string]$typeCombo.SelectedItem -eq 'alternate-recipe'
})

$applyButton.Add_Click({
    try {
        if ($null -eq $dayCombo.SelectedItem) { throw 'Select a day.' }
        if ([string]::IsNullOrWhiteSpace($actorText.Text)) { throw 'Changed by is required.' }
        $arguments = @(
            $overrideScript,'apply',
            '--menu',$menuCombo.SelectedItem.FullName,
            '--day',$dayCombo.SelectedItem.day,
            '--type',[string]$typeCombo.SelectedItem,
            '--actor',$actorText.Text
        )
        if (-not [string]::IsNullOrWhiteSpace($titleText.Text)) {
            $arguments += @('--title', $titleText.Text)
        }
        if (-not [string]::IsNullOrWhiteSpace($noteText.Text)) {
            $arguments += @('--note', $noteText.Text)
        }
        if ([string]$typeCombo.SelectedItem -eq 'alternate-recipe') {
            if ($null -eq $recipeCombo.SelectedItem) { throw 'Select a replacement recipe.' }
            $arguments += @('--recipe-id',$recipeCombo.SelectedItem.id)
        }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            'Apply this override and return the week to draft for revalidation?',
            'Confirm Meal Override','YesNo','Question'
        )
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
        New-MealPlannerGuiBackup `
            -ProjectRoot $projectRoot `
            -Operation "meal-override-$($dayCombo.SelectedItem.day)" |
            Out-Null
        $result = & $python @arguments 2>&1
        if ($LASTEXITCODE -ne 0) { throw ($result -join [Environment]::NewLine) }
        [System.Windows.Forms.MessageBox]::Show(
            "Override saved. The week is now draft and requires regeneration and validation.",
            'Meal Overridden','OK','Information'
        ) | Out-Null
        $form.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Override Failed','OK','Error') | Out-Null
    }
})

if ($menuCombo.Items.Count -gt 0) { $menuCombo.SelectedIndex = 0 }
$form.CancelButton = $closeButton
Set-MealPlannerButtonStyle -Button $applyButton -Color $colors.Override
Set-MealPlannerNeutralButtonStyle -Button $closeButton -Palette $colors
$statusLabel.BackColor = $colors.SoftOverride
$statusLabel.ForeColor = $colors.Override
$statusLabel.Padding = New-Object System.Windows.Forms.Padding(10)
$warningLabel.BackColor = $colors.SoftPantry
$warningLabel.ForeColor = $colors.PantryText
$warningLabel.Padding = New-Object System.Windows.Forms.Padding(10, 0, 10, 0)
$noteText.BackColor = $colors.Surface
Add-MealPlannerBranding `
    -Form $form `
    -Title 'Override Meal' `
    -Subtitle 'Schedule changes and meal substitutions' `
    -IconName 'override-meal'
[void]$form.ShowDialog()
