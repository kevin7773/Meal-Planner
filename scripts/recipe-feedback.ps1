param(
    [switch]$ListRecipes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$recipesRoot = Join-Path $projectRoot 'recipes'
$feedbackRoot = Join-Path $projectRoot 'feedback'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-MetadataValue {
    param(
        [string]$Text,
        [string]$Name
    )

    $match = [regex]::Match($Text, "(?m)^$([regex]::Escape($Name)) = `"([^`"]*)`"$")
    if (-not $match.Success) {
        throw "Recipe metadata is missing '$Name'."
    }
    return $match.Groups[1].Value
}

function Get-MetadataInteger {
    param(
        [string]$Text,
        [string]$Name
    )

    $match = [regex]::Match($Text, "(?m)^$([regex]::Escape($Name)) = (\d+)$")
    if (-not $match.Success) {
        throw "Recipe metadata is missing numeric '$Name'."
    }
    return [int]$match.Groups[1].Value
}

function Get-RecipeList {
    $excluded = @('README.md', 'index.md', '_template.md')
    $records = foreach ($file in Get-ChildItem -LiteralPath $recipesRoot -Filter '*.md' -File) {
        if ($excluded -contains $file.Name) {
            continue
        }

        $text = [System.IO.File]::ReadAllText($file.FullName)
        $id = Get-MetadataValue -Text $text -Name 'id'
        $name = Get-MetadataValue -Text $text -Name 'name'
        $status = Get-MetadataValue -Text $text -Name 'status'
        $revision = Get-MetadataInteger -Text $text -Name 'revision'

        [pscustomobject]@{
            Id = $id
            Name = $name
            Revision = $revision
            Status = $status
            Path = $file.FullName
            FileName = $file.Name
            Display = "$id - $name (rev $revision, $status)"
        }
    }
    return @($records | Sort-Object Id)
}

function ConvertTo-SafeCell {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'None'
    }
    return (($Value -replace '\|', '/') -replace '\s+', ' ').Trim()
}

function Set-MetadataLine {
    param(
        [string]$Text,
        [string]$Name,
        [string]$Value,
        [switch]$Quoted
    )

    $pattern = "(?m)^$([regex]::Escape($Name)) = .*$"
    $replacement = if ($Quoted) { "$Name = `"$Value`"" } else { "$Name = $Value" }
    return [regex]::Replace($Text, $pattern, $replacement, 1)
}

function Save-RecipeFeedback {
    param(
        [pscustomobject]$Recipe,
        [datetime]$MealDate,
        [int]$Rating,
        [string]$ExactAgain,
        [string]$KidResponse,
        [string]$Effort,
        [string]$Rater,
        [string]$KeepNotes,
        [string]$ChangeNotes,
        [string]$RecommendedStatus
    )

    $dateText = $MealDate.ToString('yyyy-MM-dd')
    $text = [System.IO.File]::ReadAllText($Recipe.Path)
    $safeRater = ConvertTo-SafeCell $Rater
    $safeKeep = ConvertTo-SafeCell $KeepNotes
    $safeChange = ConvertTo-SafeCell $ChangeNotes
    $safeKidResponse = ConvertTo-SafeCell $KidResponse
    $safeEffort = ConvertTo-SafeCell $Effort
    $safeExactAgain = ConvertTo-SafeCell $ExactAgain
    $ratingNotes = "Again: $safeExactAgain; Kids: $safeKidResponse; Effort: $safeEffort; Keep: $safeKeep; Change: $safeChange"
    $ratingRow = "| $dateText | $Rating | $safeRater | $ratingNotes |"

    $revisionHeading = $text.IndexOf('## Revision History')
    if ($revisionHeading -lt 0) {
        throw "$($Recipe.Id) has no Revision History section."
    }
    $beforeRevision = $text.Substring(0, $revisionHeading).TrimEnd()
    $afterRevision = $text.Substring($revisionHeading)
    $text = "$beforeRevision`r`n$ratingRow`r`n`r`n$afterRevision"

    $ratingMatches = [regex]::Matches(
        $text,
        '(?m)^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*([1-5])\s*\|'
    )
    $ratingValues = @($ratingMatches | ForEach-Object { [int]$_.Groups[1].Value })
    $ratingCount = $ratingValues.Count
    $ratingAverage = [math]::Round(
        ($ratingValues | Measure-Object -Average).Average,
        2
    )

    $newStatus = $Recipe.Status
    if ($Recipe.Status -eq 'candidate' -and $RecommendedStatus -in @('approved', 'retired')) {
        $newStatus = $RecommendedStatus
    }

    $text = Set-MetadataLine $text 'updated' $dateText -Quoted
    $text = Set-MetadataLine $text 'status' $newStatus -Quoted
    $text = Set-MetadataLine $text 'ratings_count' ([string]$ratingCount)
    $text = Set-MetadataLine $text 'rating_average' $ratingAverage.ToString('0.##', [cultureinfo]::InvariantCulture)

    $verdict = switch ($newStatus) {
        'approved' { "Family-approved on $dateText" }
        'retired' { "Retired after family feedback on $dateText" }
        default {
            if ($safeChange -ne 'None') {
                "Tested on $dateText; changes requested before approval"
            } else {
                "Tested on $dateText; remains a candidate"
            }
        }
    }
    $text = [regex]::Replace(
        $text,
        '(?m)^- \*\*Verdict:\*\*.*$',
        "- **Verdict:** $verdict",
        1
    )
    $text = [regex]::Replace(
        $text,
        '(?m)^- \*\*Keep:\*\*.*$',
        "- **Keep:** $safeKeep",
        1
    )
    $text = [regex]::Replace(
        $text,
        '(?m)^- \*\*Change next time:\*\*.*$',
        "- **Change next time:** $safeChange",
        1
    )
    [System.IO.File]::WriteAllText($Recipe.Path, $text, $utf8NoBom)

    $indexPath = Join-Path $recipesRoot 'index.md'
    $indexText = [System.IO.File]::ReadAllText($indexPath)
    $ratingDisplay = $ratingAverage.ToString('0.00', [cultureinfo]::InvariantCulture) + " / 5 ($ratingCount)"
    $indexRow = "| $($Recipe.Id) | [$($Recipe.Name)]($($Recipe.FileName)) | $($Recipe.Revision) | $newStatus | $ratingDisplay | $dateText |"
    $indexPattern = "(?m)^\|\s*$([regex]::Escape($Recipe.Id))\s*\|.*$"
    if (-not [regex]::IsMatch($indexText, $indexPattern)) {
        throw "Recipe index has no row for $($Recipe.Id)."
    }
    $indexText = [regex]::Replace($indexText, $indexPattern, $indexRow, 1)
    [System.IO.File]::WriteAllText($indexPath, $indexText, $utf8NoBom)

    $yearFolder = Join-Path $feedbackRoot $MealDate.ToString('yyyy')
    [System.IO.Directory]::CreateDirectory($yearFolder) | Out-Null
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $feedbackPath = Join-Path $yearFolder "$dateText-$($Recipe.Id)-$timestamp.json"
    $feedback = [ordered]@{
        schema_version = 1
        recipe_id = $Recipe.Id
        recipe_revision = $Recipe.Revision
        recipe_name = $Recipe.Name
        meal_date = $dateText
        submitted_at = (Get-Date).ToString('o')
        rater = $Rater
        overall_rating = $Rating
        make_exact_recipe_again = $ExactAgain
        kid_response = $KidResponse
        effort = $Effort
        keep = $KeepNotes
        change_next_time = $ChangeNotes
        disposition = $newStatus
    }
    $json = $feedback | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($feedbackPath, $json, $utf8NoBom)

    return [pscustomobject]@{
        Status = $newStatus
        RatingAverage = $ratingAverage
        RatingCount = $ratingCount
        FeedbackPath = $feedbackPath
    }
}

$recipes = Get-RecipeList
if ($ListRecipes) {
    $recipes | Select-Object Id, Name, Revision, Status, FileName | Format-Table -AutoSize
    return
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot 'gui-branding.ps1')
$colors = Get-MealPlannerPalette

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Family Recipe Review'
$form.ClientSize = New-Object System.Drawing.Size(720, 700)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
Set-MealPlannerFormSurface -Form $form -Palette $colors

function Add-Label {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width = 155)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($Width, 26)
    $label.TextAlign = 'MiddleLeft'
    $form.Controls.Add($label)
    return $label
}

Add-Label 'Recipe' 20 22 | Out-Null
$recipeCombo = New-Object System.Windows.Forms.ComboBox
$recipeCombo.Location = New-Object System.Drawing.Point(180, 22)
$recipeCombo.Size = New-Object System.Drawing.Size(220, 28)
$recipeCombo.DropDownStyle = 'DropDownList'
$recipeCombo.DisplayMember = 'Display'
foreach ($recipe in $recipes) {
    [void]$recipeCombo.Items.Add($recipe)
}
if ($recipeCombo.Items.Count -gt 0) {
    $recipeCombo.SelectedIndex = 0
}
$form.Controls.Add($recipeCombo)

$viewRecipeButton = New-Object System.Windows.Forms.Button
$viewRecipeButton.Text = 'View Recipe'
$viewRecipeButton.Location = New-Object System.Drawing.Point(410, 19)
$viewRecipeButton.Size = New-Object System.Drawing.Size(85, 34)
$form.Controls.Add($viewRecipeButton)
Set-MealPlannerButtonStyle -Button $viewRecipeButton -Color $colors.Review

function Get-CurrentSelectedRecipe {
    if ($null -eq $recipeCombo.SelectedItem) {
        throw 'Select a recipe.'
    }
    $selectedRecipe = $recipeCombo.SelectedItem
    $currentRecipes = @(
        Get-RecipeList |
            Where-Object { $_.Id -eq $selectedRecipe.Id }
    )
    if ($currentRecipes.Count -ne 1) {
        throw "Could not resolve the current recipe card for $($selectedRecipe.Id)."
    }
    return $currentRecipes[0]
}

$printRecipeButton = New-Object System.Windows.Forms.Button
$printRecipeButton.Text = 'Print Recipe'
$printRecipeButton.Location = New-Object System.Drawing.Point(505, 19)
$printRecipeButton.Size = New-Object System.Drawing.Size(85, 34)
$form.Controls.Add($printRecipeButton)
Set-MealPlannerButtonStyle -Button $printRecipeButton -Color $colors.Pantry

$exportRecipeButton = New-Object System.Windows.Forms.Button
$exportRecipeButton.Text = 'Export HTML'
$exportRecipeButton.Location = New-Object System.Drawing.Point(600, 19)
$exportRecipeButton.Size = New-Object System.Drawing.Size(90, 34)
$form.Controls.Add($exportRecipeButton)
Set-MealPlannerButtonStyle -Button $exportRecipeButton -Color $colors.Email

function Get-PrintableRecipeLines {
    param([pscustomobject]$Recipe)

    $text = [System.IO.File]::ReadAllText($recipe.Path)
    $servings = Get-MetadataInteger -Text $text -Name 'servings'
    $body = [regex]::Replace(
        $text,
        '(?s)\A\+\+\+\r?\n.*?\r?\n\+\+\+\s*',
        ''
    )
    $familyNotes = [regex]::Match(
        $body,
        '(?m)^## Family Notes\s*$'
    )
    if ($familyNotes.Success) {
        $body = $body.Substring(0, $familyNotes.Index).TrimEnd()
    }
    $body = [regex]::Replace(
        $body,
        '(?m)^# .+\r?\n+',
        '',
        1
    )

    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add([pscustomobject]@{
        Kind = 'Title'
        Text = $Recipe.Name
    })
    [void]$lines.Add([pscustomobject]@{
        Kind = 'Meta'
        Text = (
            "$($Recipe.Id) | Revision $($Recipe.Revision) | " +
            "Serves $servings"
        )
    })
    [void]$lines.Add([pscustomobject]@{ Kind = 'Spacer'; Text = '' })

    foreach ($rawLine in ($body -split '\r?\n')) {
        $line = $rawLine.TrimEnd()
        if ([string]::IsNullOrWhiteSpace($line)) {
            [void]$lines.Add(
                [pscustomobject]@{ Kind = 'Spacer'; Text = '' }
            )
            continue
        }
        $heading = [regex]::Match($line, '^#{2,6}\s+(.+)$')
        $kind = if ($heading.Success) { 'Heading' } else { 'Body' }
        if ($heading.Success) {
            $line = $heading.Groups[1].Value
        }
        $line = [regex]::Replace($line, '\[([^\]]+)\]\([^)]+\)', '$1')
        $line = $line -replace '\*\*', ''
        $line = $line -replace '`', ''
        [void]$lines.Add([pscustomobject]@{
            Kind = $kind
            Text = $line
        })
    }
    return @($lines)
}

function Print-SelectedRecipe {
    $recipe = Get-CurrentSelectedRecipe
    $lines = Get-PrintableRecipeLines -Recipe $recipe
    $document = New-Object System.Drawing.Printing.PrintDocument
    $document.DocumentName = "$($recipe.Id) - $($recipe.Name)"
    $document.DefaultPageSettings.Margins = (
        New-Object System.Drawing.Printing.Margins(55, 55, 55, 55)
    )

    $titleFont = New-Object System.Drawing.Font(
        'Segoe UI',
        18,
        [System.Drawing.FontStyle]::Bold
    )
    $headingFont = New-Object System.Drawing.Font(
        'Segoe UI',
        12,
        [System.Drawing.FontStyle]::Bold
    )
    $bodyFont = New-Object System.Drawing.Font('Segoe UI', 10)
    $metaFont = New-Object System.Drawing.Font(
        'Segoe UI',
        9,
        [System.Drawing.FontStyle]::Italic
    )
    $footerFont = New-Object System.Drawing.Font('Segoe UI', 8)
    $brush = [System.Drawing.Brushes]::Black
    $state = [pscustomobject]@{ Index = 0; Page = 0 }

    $document.Add_BeginPrint({
        $state.Index = 0
        $state.Page = 0
    })
    $document.Add_PrintPage({
        param($sender, $eventArgs)

        $state.Page++
        $bounds = $eventArgs.MarginBounds
        $y = [single]$bounds.Top
        if ($state.Page -gt 1) {
            $continuation = "$($recipe.Name) - continued"
            $eventArgs.Graphics.DrawString(
                $continuation,
                $metaFont,
                $brush,
                [single]$bounds.Left,
                $y
            )
            $y += 28
        }

        while ($state.Index -lt $lines.Count) {
            $line = $lines[$state.Index]
            $font = switch ($line.Kind) {
                'Title' { $titleFont }
                'Heading' { $headingFont }
                'Meta' { $metaFont }
                default { $bodyFont }
            }
            $height = if ($line.Kind -eq 'Spacer') {
                8
            } else {
                [Math]::Ceiling(
                    $eventArgs.Graphics.MeasureString(
                        $line.Text,
                        $font,
                        $bounds.Width
                    ).Height
                ) + 3
            }
            if ($y + $height -gt $bounds.Bottom - 18) {
                $eventArgs.HasMorePages = $true
                break
            }
            if ($line.Kind -ne 'Spacer') {
                $layout = New-Object System.Drawing.RectangleF(
                    [single]$bounds.Left,
                    $y,
                    [single]$bounds.Width,
                    [single]$height
                )
                $eventArgs.Graphics.DrawString(
                    $line.Text,
                    $font,
                    $brush,
                    $layout
                )
            }
            $y += $height
            $state.Index++
        }

        $footer = "$($recipe.Id) | Page $($state.Page)"
        $eventArgs.Graphics.DrawString(
            $footer,
            $footerFont,
            [System.Drawing.Brushes]::DimGray,
            [single]$bounds.Left,
            [single]($bounds.Bottom + 12)
        )
        if ($state.Index -ge $lines.Count) {
            $eventArgs.HasMorePages = $false
        }
    })

    $previewForm = New-Object System.Windows.Forms.Form
    $previewForm.Text = "Print Preview - $($recipe.Name)"
    $previewForm.ClientSize = New-Object System.Drawing.Size(960, 680)
    $previewForm.StartPosition = 'CenterParent'
    $previewForm.MinimumSize = New-Object System.Drawing.Size(760, 560)
    $previewForm.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $previewForm -Palette $colors

    $preview = New-Object System.Windows.Forms.PrintPreviewControl
    $preview.Location = New-Object System.Drawing.Point(0, 0)
    $preview.Size = New-Object System.Drawing.Size(960, 620)
    $preview.Anchor = 'Top,Bottom,Left,Right'
    $preview.AutoZoom = $true
    $preview.UseAntiAlias = $true
    $preview.Document = $document
    $previewForm.Controls.Add($preview)

    $printButton = New-Object System.Windows.Forms.Button
    $printButton.Text = 'Print'
    $printButton.Location = New-Object System.Drawing.Point(730, 632)
    $printButton.Size = New-Object System.Drawing.Size(100, 36)
    $printButton.Anchor = 'Bottom,Right'
    $previewForm.Controls.Add($printButton)
    Set-MealPlannerButtonStyle -Button $printButton -Color $colors.Pantry

    $closePreviewButton = New-Object System.Windows.Forms.Button
    $closePreviewButton.Text = 'Close'
    $closePreviewButton.Location = New-Object System.Drawing.Point(840, 632)
    $closePreviewButton.Size = New-Object System.Drawing.Size(100, 36)
    $closePreviewButton.Anchor = 'Bottom,Right'
    $closePreviewButton.Add_Click({ $previewForm.Close() })
    $previewForm.Controls.Add($closePreviewButton)
    Set-MealPlannerNeutralButtonStyle `
        -Button $closePreviewButton `
        -Palette $colors

    $printButton.Add_Click({
        $printDialog = New-Object System.Windows.Forms.PrintDialog
        $printDialog.Document = $document
        $printDialog.UseEXDialog = $true
        try {
            if (
                $printDialog.ShowDialog($previewForm) -eq
                [System.Windows.Forms.DialogResult]::OK
            ) {
                $document.Print()
            }
        } catch {
            [System.Windows.Forms.MessageBox]::Show(
                $_.Exception.Message,
                'Unable to Print Recipe',
                'OK',
                'Error'
            ) | Out-Null
        } finally {
            $printDialog.Dispose()
        }
    })

    $previewForm.CancelButton = $closePreviewButton
    try {
        [void]$previewForm.ShowDialog($form)
    } finally {
        $preview.Dispose()
        $previewForm.Dispose()
        $document.Dispose()
        $titleFont.Dispose()
        $headingFont.Dispose()
        $bodyFont.Dispose()
        $metaFont.Dispose()
        $footerFont.Dispose()
    }
}

function Export-SelectedRecipeHtml {
    $recipe = Get-CurrentSelectedRecipe
    $lines = Get-PrintableRecipeLines -Recipe $recipe
    $htmlBody = New-Object System.Text.StringBuilder
    foreach ($line in $lines) {
        $encoded = [System.Net.WebUtility]::HtmlEncode(
            [string]$line.Text
        )
        switch ($line.Kind) {
            'Title' {
                [void]$htmlBody.AppendLine("<h1>$encoded</h1>")
            }
            'Meta' {
                [void]$htmlBody.AppendLine(
                    "<div class=`"meta`">$encoded</div>"
                )
            }
            'Heading' {
                [void]$htmlBody.AppendLine("<h2>$encoded</h2>")
            }
            'Spacer' {
                [void]$htmlBody.AppendLine('<div class="spacer"></div>')
            }
            default {
                [void]$htmlBody.AppendLine(
                    "<div class=`"body-line`">$encoded</div>"
                )
            }
        }
    }
    $title = [System.Net.WebUtility]::HtmlEncode($recipe.Name)
    $html = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0 auto;
      max-width: 8in;
      padding: 0.45in;
      color: #202624;
      background: #fff;
      font: 11pt/1.42 "Segoe UI", Arial, sans-serif;
    }
    h1 { margin: 0 0 0.08in; font-size: 24pt; }
    h2 {
      margin: 0.22in 0 0.08in;
      border-bottom: 1px solid #cfd8d4;
      padding-bottom: 0.04in;
      font-size: 14pt;
      break-after: avoid;
    }
    .meta { color: #5c6662; font-style: italic; }
    .body-line { margin: 0.035in 0; white-space: pre-wrap; }
    .spacer { height: 0.08in; }
    @page { margin: 0.55in; }
    @media print {
      body { max-width: none; padding: 0; }
      h1, h2 { break-after: avoid; }
      .body-line { orphans: 2; widows: 2; }
    }
  </style>
</head>
<body>
$($htmlBody.ToString())
</body>
</html>
"@

    $safeName = ($recipe.Name -replace '[^A-Za-z0-9]+', '-').Trim('-')
    $saveDialog = New-Object System.Windows.Forms.SaveFileDialog
    $saveDialog.Title = 'Export Printable Recipe Card'
    $saveDialog.Filter = 'HTML document (*.html)|*.html'
    $saveDialog.DefaultExt = 'html'
    $saveDialog.AddExtension = $true
    $saveDialog.FileName = "$($recipe.Id)-$safeName.html"
    try {
        if (
            $saveDialog.ShowDialog($form) -eq
            [System.Windows.Forms.DialogResult]::OK
        ) {
            [System.IO.File]::WriteAllText(
                $saveDialog.FileName,
                $html,
                (New-Object System.Text.UTF8Encoding($false))
            )
            [System.Windows.Forms.MessageBox]::Show(
                "Printable recipe exported:`r`n$($saveDialog.FileName)",
                'Recipe Exported',
                'OK',
                'Information'
            ) | Out-Null
        }
    } finally {
        $saveDialog.Dispose()
    }
}

function Show-SelectedRecipe {
    $recipe = Get-CurrentSelectedRecipe
    $text = [System.IO.File]::ReadAllText($recipe.Path)
    $body = [regex]::Replace(
        $text,
        '(?s)\A\+\+\+\r?\n.*?\r?\n\+\+\+\s*',
        ''
    )
    $body = $body -replace '(?m)^#{1,6}\s*', ''
    $body = $body -replace '\*\*', ''
    $body = $body -replace '`', ''
    $body = $body -replace '\r?\n', [Environment]::NewLine

    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = "Recipe - $($recipe.Name)"
    $dialog.ClientSize = New-Object System.Drawing.Size(780, 650)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    Set-MealPlannerFormSurface -Form $dialog -Palette $colors

    $recipeText = New-Object System.Windows.Forms.RichTextBox
    $recipeText.Location = New-Object System.Drawing.Point(20, 20)
    $recipeText.Size = New-Object System.Drawing.Size(740, 555)
    $recipeText.ReadOnly = $true
    $recipeText.ScrollBars = 'Vertical'
    $recipeText.WordWrap = $true
    $recipeText.DetectUrls = $true
    $recipeText.MaxLength = [int]::MaxValue
    $recipeText.BackColor = $colors.Surface
    $recipeText.ForeColor = $colors.Text
    $recipeText.Text = (
        "$($recipe.Name)`r`n" +
        "$($recipe.Id) | Revision $($recipe.Revision) | " +
        "Status: $($recipe.Status)`r`n`r`n" +
        $body
    )
    $recipeText.SelectionStart = 0
    $dialog.Controls.Add($recipeText)

    $closeRecipeButton = New-Object System.Windows.Forms.Button
    $closeRecipeButton.Text = 'Close'
    $closeRecipeButton.Location = New-Object System.Drawing.Point(650, 590)
    $closeRecipeButton.Size = New-Object System.Drawing.Size(110, 38)
    $closeRecipeButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dialog.Controls.Add($closeRecipeButton)
    Set-MealPlannerNeutralButtonStyle `
        -Button $closeRecipeButton `
        -Palette $colors

    $dialog.AcceptButton = $closeRecipeButton
    $dialog.CancelButton = $closeRecipeButton
    Add-MealPlannerBranding `
        -Form $dialog `
        -Title 'Recipe Card' `
        -Subtitle "$($recipe.Id) rev $($recipe.Revision) | $($recipe.Status)" `
        -IconName 'review-meal'
    [void]$dialog.ShowDialog($form)
}

$viewRecipeButton.Add_Click({
    try {
        Show-SelectedRecipe
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to View Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$printRecipeButton.Add_Click({
    try {
        Print-SelectedRecipe
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Print Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$exportRecipeButton.Add_Click({
    try {
        Export-SelectedRecipeHtml
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Export Recipe',
            'OK',
            'Error'
        ) | Out-Null
    }
})

Add-Label 'Meal date' 20 64 | Out-Null
$mealDatePicker = New-Object System.Windows.Forms.DateTimePicker
$mealDatePicker.Location = New-Object System.Drawing.Point(180, 64)
$mealDatePicker.Size = New-Object System.Drawing.Size(220, 28)
$mealDatePicker.Value = Get-Date
$form.Controls.Add($mealDatePicker)

Add-Label 'Overall rating' 20 106 | Out-Null
$ratingCombo = New-Object System.Windows.Forms.ComboBox
$ratingCombo.Location = New-Object System.Drawing.Point(180, 106)
$ratingCombo.Size = New-Object System.Drawing.Size(220, 28)
$ratingCombo.DropDownStyle = 'DropDownList'
1..5 | ForEach-Object { [void]$ratingCombo.Items.Add("$_ / 5") }
$ratingCombo.SelectedIndex = 3
$form.Controls.Add($ratingCombo)

Add-Label 'Exact recipe again?' 20 148 | Out-Null
$againCombo = New-Object System.Windows.Forms.ComboBox
$againCombo.Location = New-Object System.Drawing.Point(180, 148)
$againCombo.Size = New-Object System.Drawing.Size(220, 28)
$againCombo.DropDownStyle = 'DropDownList'
@('Yes', 'Not sure', 'No') | ForEach-Object { [void]$againCombo.Items.Add($_) }
$againCombo.SelectedIndex = 1
$form.Controls.Add($againCombo)

Add-Label 'Kid response' 20 190 | Out-Null
$kidCombo = New-Object System.Windows.Forms.ComboBox
$kidCombo.Location = New-Object System.Drawing.Point(180, 190)
$kidCombo.Size = New-Object System.Drawing.Size(330, 28)
$kidCombo.DropDownStyle = 'DropDownList'
@('Both enjoyed it', 'Both ate it', 'Mixed response', 'Tried it', 'Mostly refused', 'Not applicable') |
    ForEach-Object { [void]$kidCombo.Items.Add($_) }
$kidCombo.SelectedIndex = 0
$form.Controls.Add($kidCombo)

Add-Label 'Effort' 20 232 | Out-Null
$effortCombo = New-Object System.Windows.Forms.ComboBox
$effortCombo.Location = New-Object System.Drawing.Point(180, 232)
$effortCombo.Size = New-Object System.Drawing.Size(220, 28)
$effortCombo.DropDownStyle = 'DropDownList'
@('Easy', 'Fine', 'Too much') | ForEach-Object { [void]$effortCombo.Items.Add($_) }
$effortCombo.SelectedIndex = 1
$form.Controls.Add($effortCombo)

Add-Label 'Rater' 20 274 | Out-Null
$raterText = New-Object System.Windows.Forms.TextBox
$raterText.Location = New-Object System.Drawing.Point(180, 274)
$raterText.Size = New-Object System.Drawing.Size(220, 28)
$raterText.Text = 'Family'
$form.Controls.Add($raterText)

Add-Label 'What should stay?' 20 316 | Out-Null
$keepText = New-Object System.Windows.Forms.TextBox
$keepText.Location = New-Object System.Drawing.Point(180, 316)
$keepText.Size = New-Object System.Drawing.Size(510, 90)
$keepText.Multiline = $true
$keepText.ScrollBars = 'Vertical'
$form.Controls.Add($keepText)

Add-Label 'Change next time?' 20 424 | Out-Null
$changeText = New-Object System.Windows.Forms.TextBox
$changeText.Location = New-Object System.Drawing.Point(180, 424)
$changeText.Size = New-Object System.Drawing.Size(510, 90)
$changeText.Multiline = $true
$changeText.ScrollBars = 'Vertical'
$form.Controls.Add($changeText)

$outcomeLabel = New-Object System.Windows.Forms.Label
$outcomeLabel.Location = New-Object System.Drawing.Point(20, 535)
$outcomeLabel.Size = New-Object System.Drawing.Size(670, 58)
$outcomeLabel.BorderStyle = 'FixedSingle'
$outcomeLabel.Padding = New-Object System.Windows.Forms.Padding(10)
$form.Controls.Add($outcomeLabel)

$script:recommendedStatus = 'candidate'
function Update-Outcome {
    if ($null -eq $recipeCombo.SelectedItem) {
        return
    }
    $recipe = $recipeCombo.SelectedItem
    $rating = $ratingCombo.SelectedIndex + 1
    $again = [string]$againCombo.SelectedItem
    $hasChanges = -not [string]::IsNullOrWhiteSpace($changeText.Text)

    if ($recipe.Status -eq 'approved') {
        $script:recommendedStatus = 'approved'
        $outcomeLabel.Text = 'Outcome: Remains approved. Feedback is recorded; requested changes require a new candidate revision.'
    } elseif ($recipe.Status -eq 'retired') {
        $script:recommendedStatus = 'retired'
        $outcomeLabel.Text = 'Outcome: Remains retired. Feedback is recorded for history.'
    } elseif ($again -eq 'Yes' -and $rating -ge 4 -and -not $hasChanges) {
        $script:recommendedStatus = 'approved'
        $outcomeLabel.Text = 'Outcome: APPROVE. Rating is 4-5, the exact recipe is wanted again, and no changes are requested.'
    } elseif ($again -eq 'No' -and $rating -le 2) {
        $script:recommendedStatus = 'retired'
        $outcomeLabel.Text = 'Outcome: RETIRE. The recipe is not wanted again and scored 1-2.'
    } else {
        $script:recommendedStatus = 'candidate'
        $outcomeLabel.Text = 'Outcome: KEEP AS CANDIDATE. More testing or a revised recipe is needed.'
    }
    switch ($script:recommendedStatus) {
        'approved' {
            $outcomeLabel.BackColor = $colors.SoftPlanner
            $outcomeLabel.ForeColor = $colors.Planner
        }
        'retired' {
            $outcomeLabel.BackColor = $colors.SoftOverride
            $outcomeLabel.ForeColor = $colors.Override
        }
        default {
            $outcomeLabel.BackColor = $colors.SoftPantry
            $outcomeLabel.ForeColor = $colors.PantryText
        }
    }
}

function Reset-ReviewEntry {
    $nextIndex = if ($recipeCombo.Items.Count -gt 0) {
        ($recipeCombo.SelectedIndex + 1) % $recipeCombo.Items.Count
    } else {
        0
    }
    $ratingCombo.SelectedIndex = 3
    $againCombo.SelectedIndex = 1
    $kidCombo.SelectedIndex = 0
    $effortCombo.SelectedIndex = 1
    $keepText.Clear()
    $changeText.Clear()

    $updatedRecipes = Get-RecipeList
    $recipeCombo.BeginUpdate()
    try {
        $recipeCombo.Items.Clear()
        foreach ($recipe in $updatedRecipes) {
            [void]$recipeCombo.Items.Add($recipe)
        }
    } finally {
        $recipeCombo.EndUpdate()
    }
    if ($recipeCombo.Items.Count -gt 0) {
        $recipeCombo.SelectedIndex = [Math]::Min(
            $nextIndex,
            $recipeCombo.Items.Count - 1
        )
    }
    Update-Outcome
    $recipeCombo.Focus()
}

$recipeCombo.Add_SelectedIndexChanged({ Update-Outcome })
$ratingCombo.Add_SelectedIndexChanged({ Update-Outcome })
$againCombo.Add_SelectedIndexChanged({ Update-Outcome })
$changeText.Add_TextChanged({ Update-Outcome })

$saveButton = New-Object System.Windows.Forms.Button
$saveButton.Text = 'Save Review'
$saveButton.Location = New-Object System.Drawing.Point(470, 620)
$saveButton.Size = New-Object System.Drawing.Size(105, 38)
$saveButton.Add_Click({
    try {
        if ($null -eq $recipeCombo.SelectedItem) {
            throw 'Select a recipe.'
        }
        if ([string]::IsNullOrWhiteSpace($raterText.Text)) {
            throw 'Enter a rater name or use Family.'
        }
        $result = Save-RecipeFeedback `
            -Recipe $recipeCombo.SelectedItem `
            -MealDate $mealDatePicker.Value `
            -Rating ($ratingCombo.SelectedIndex + 1) `
            -ExactAgain ([string]$againCombo.SelectedItem) `
            -KidResponse ([string]$kidCombo.SelectedItem) `
            -Effort ([string]$effortCombo.SelectedItem) `
            -Rater $raterText.Text `
            -KeepNotes $keepText.Text `
            -ChangeNotes $changeText.Text `
            -RecommendedStatus $script:recommendedStatus
        [System.Windows.Forms.MessageBox]::Show(
            (
                "Review saved.`nStatus: $($result.Status)`n" +
                "Rating: $($result.RatingAverage) / 5 from " +
                "$($result.RatingCount) review(s).`n`n" +
                'The form is ready for another review.'
            ),
            'Recipe Review Saved',
            'OK',
            'Information'
        ) | Out-Null
        Reset-ReviewEntry
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Save Review',
            'OK',
            'Error'
        ) | Out-Null
    }
})
$form.Controls.Add($saveButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = 'Cancel'
$cancelButton.Location = New-Object System.Drawing.Point(585, 620)
$cancelButton.Size = New-Object System.Drawing.Size(105, 38)
$cancelButton.Add_Click({ $form.Close() })
$form.Controls.Add($cancelButton)

$form.AcceptButton = $saveButton
$form.CancelButton = $cancelButton
Set-MealPlannerButtonStyle -Button $saveButton -Color $colors.Review
Set-MealPlannerNeutralButtonStyle -Button $cancelButton -Palette $colors
$keepText.BackColor = $colors.SoftPlanner
$changeText.BackColor = $colors.SoftOverride
Update-Outcome
Add-MealPlannerBranding `
    -Form $form `
    -Title 'Review Meal' `
    -Subtitle 'Family ratings and recipe approval' `
    -IconName 'review-meal'
[void]$form.ShowDialog()
