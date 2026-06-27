Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$importer = Join-Path $PSScriptRoot 'import_recipe.py'
$ideaManager = Join-Path $PSScriptRoot 'recipe_ideas.py'

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

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Import Recipe'
$form.ClientSize = New-Object System.Drawing.Size(900, 820)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

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
@('chicken','turkey','beef','seafood','pork','vegetarian','other') | ForEach-Object { [void]$proteinCombo.Items.Add($_) }
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
$kidReason.Size = New-Object System.Drawing.Size(490, 28)
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

Add-Label 'Cook min' 670 415 70
$cookMinutes = New-Object System.Windows.Forms.NumericUpDown
$cookMinutes.Location = New-Object System.Drawing.Point(745, 415)
$cookMinutes.Size = New-Object System.Drawing.Size(135, 28)
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
$note.Text = 'Imports are candidates. Review quantities, seasoning classification, and inventory mapping before scheduling.'
$form.Controls.Add($note)

$saveIdeaButton = New-Object System.Windows.Forms.Button
$saveIdeaButton.Text = 'Save Recipe Idea'
$saveIdeaButton.Location = New-Object System.Drawing.Point(455, 735)
$saveIdeaButton.Size = New-Object System.Drawing.Size(150, 42)
$form.Controls.Add($saveIdeaButton)

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

function Reset-ImportForm {
    $script:pastedText = ''
    $sourceText.Clear()
    $previewText.Clear()
    $nameText.Clear()
    $ideaText.Clear()
    $kidReason.SelectedIndex = 0
    $proteinCombo.SelectedIndex = 0
    $methodCombo.SelectedIndex = 0
    $fiberInput.Value = 8
    $costInput.Value = 20
    $kidScore.SelectedItem = '4'
    $cookMinutes.Value = 0
    foreach ($season in @('spring','summer','fall','winter')) {
        $seasonButtons[$season].Checked = $true
    }
    $mealScopeCombo.SelectedIndex = 0
    $mexicanMonday.Checked = $false
    $importButton.Enabled = $false
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

function Show-PasteEditor {
    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = 'Paste Recipe Text'
    $dialog.ClientSize = New-Object System.Drawing.Size(700, 520)
    $dialog.StartPosition = 'CenterParent'
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
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
    $cancel = New-Object System.Windows.Forms.Button
    $cancel.Text = 'Cancel'
    $cancel.Location = New-Object System.Drawing.Point(420, 470)
    $cancel.Size = New-Object System.Drawing.Size(100, 35)
    $cancel.DialogResult = 'Cancel'
    $dialog.Controls.Add($cancel)
    $dialog.AcceptButton = $useButton
    $dialog.CancelButton = $cancel
    if ($dialog.ShowDialog($form) -eq 'OK') {
        $script:pastedText = $editor.Text
        $sourceText.Text = "Pasted recipe text ($($script:pastedText.Length) characters)"
        $importButton.Enabled = $false
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
        if ([string]::IsNullOrWhiteSpace($kidReason.Text)) { throw 'Kid-friendly reason is required.' }
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
            '--cook-minutes',[string]$cookMinutes.Value,
            '--fiber',[string]$fiberInput.Value,
            '--cost',[string]$costInput.Value,
            '--kid-score',[string]$kidScore.SelectedItem,
            '--kid-reason',$kidReason.Text,
            '--seasons',(Get-SelectedSeasons)
        )
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
[void]$form.ShowDialog()
