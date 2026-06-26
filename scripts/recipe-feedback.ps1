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

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Family Recipe Review'
$form.ClientSize = New-Object System.Drawing.Size(720, 700)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

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
$recipeCombo.Size = New-Object System.Drawing.Size(510, 28)
$recipeCombo.DropDownStyle = 'DropDownList'
$recipeCombo.DisplayMember = 'Display'
foreach ($recipe in $recipes) {
    [void]$recipeCombo.Items.Add($recipe)
}
if ($recipeCombo.Items.Count -gt 0) {
    $recipeCombo.SelectedIndex = 0
}
$form.Controls.Add($recipeCombo)

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
            "Review saved.`nStatus: $($result.Status)`nRating: $($result.RatingAverage) / 5 from $($result.RatingCount) review(s).",
            'Recipe Review Saved',
            'OK',
            'Information'
        ) | Out-Null
        $form.Close()
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
Update-Outcome
[void]$form.ShowDialog()
