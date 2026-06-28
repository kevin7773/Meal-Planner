Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$plannerScript = Join-Path $PSScriptRoot 'planner_cli.py'

function Resolve-Python {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    throw 'Python was not found. Install Python 3.11 or run this project inside Codex.'
}

$python = Resolve-Python

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Weekly Meal Planner - Dry Run'
$form.ClientSize = New-Object System.Drawing.Size(900, 720)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$weekLabel = New-Object System.Windows.Forms.Label
$weekLabel.Text = 'Week of (Monday)'
$weekLabel.Location = New-Object System.Drawing.Point(20, 22)
$weekLabel.Size = New-Object System.Drawing.Size(145, 28)
$form.Controls.Add($weekLabel)

$weekPicker = New-Object System.Windows.Forms.DateTimePicker
$weekPicker.Location = New-Object System.Drawing.Point(170, 22)
$weekPicker.Size = New-Object System.Drawing.Size(230, 28)
$daysUntilMonday = (([int][DayOfWeek]::Monday - [int](Get-Date).DayOfWeek) + 7) % 7
if ($daysUntilMonday -eq 0) {
    $daysUntilMonday = 7
}
$weekPicker.Value = (Get-Date).Date.AddDays($daysUntilMonday)
$form.Controls.Add($weekPicker)

$generateButton = New-Object System.Windows.Forms.Button
$generateButton.Text = 'Generate 3 Dry Runs'
$generateButton.Location = New-Object System.Drawing.Point(420, 18)
$generateButton.Size = New-Object System.Drawing.Size(175, 38)
$form.Controls.Add($generateButton)

$noWriteLabel = New-Object System.Windows.Forms.Label
$noWriteLabel.Text = 'Dry Run writes no project files.'
$noWriteLabel.Location = New-Object System.Drawing.Point(615, 23)
$noWriteLabel.Size = New-Object System.Drawing.Size(250, 28)
$noWriteLabel.ForeColor = [System.Drawing.Color]::DarkGreen
$form.Controls.Add($noWriteLabel)

$existingPlanPanel = New-Object System.Windows.Forms.Panel
$existingPlanPanel.Location = New-Object System.Drawing.Point(20, 68)
$existingPlanPanel.Size = New-Object System.Drawing.Size(855, 44)
$existingPlanPanel.BorderStyle = 'FixedSingle'
$form.Controls.Add($existingPlanPanel)

$existingPlanLabel = New-Object System.Windows.Forms.Label
$existingPlanLabel.Location = New-Object System.Drawing.Point(12, 7)
$existingPlanLabel.Size = New-Object System.Drawing.Size(655, 28)
$existingPlanLabel.TextAlign = 'MiddleLeft'
$existingPlanPanel.Controls.Add($existingPlanLabel)

$viewExistingButton = New-Object System.Windows.Forms.Button
$viewExistingButton.Text = 'View Existing Plan'
$viewExistingButton.Location = New-Object System.Drawing.Point(685, 5)
$viewExistingButton.Size = New-Object System.Drawing.Size(155, 32)
$viewExistingButton.Enabled = $false
$existingPlanPanel.Controls.Add($viewExistingButton)

$dinersLabel = New-Object System.Windows.Forms.Label
$dinersLabel.Text = 'Diners'
$dinersLabel.Location = New-Object System.Drawing.Point(20, 126)
$dinersLabel.Size = New-Object System.Drawing.Size(60, 28)
$dinersLabel.TextAlign = 'MiddleLeft'
$form.Controls.Add($dinersLabel)

$script:dinerInputs = New-Object System.Collections.ArrayList
$dinerDays = @(
    @{ Name = 'Mon'; X = 85 },
    @{ Name = 'Tue'; X = 195 },
    @{ Name = 'Wed'; X = 305 },
    @{ Name = 'Thu'; X = 415 },
    @{ Name = 'Fri'; X = 525 },
    @{ Name = 'Sat'; X = 635 },
    @{ Name = 'Sun'; X = 745 }
)
foreach ($day in $dinerDays) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $day.Name
    $label.Location = New-Object System.Drawing.Point($day.X, 119)
    $label.Size = New-Object System.Drawing.Size(45, 20)
    $label.TextAlign = 'MiddleCenter'
    $form.Controls.Add($label)

    $input = New-Object System.Windows.Forms.NumericUpDown
    $input.Location = New-Object System.Drawing.Point($day.X, 140)
    $input.Size = New-Object System.Drawing.Size(70, 28)
    $input.Minimum = 1
    $input.Maximum = 20
    $input.Value = 4
    $input.TextAlign = 'Center'
    $form.Controls.Add($input)
    [void]$script:dinerInputs.Add($input)
}

$optionList = New-Object System.Windows.Forms.ListBox
$optionList.Location = New-Object System.Drawing.Point(20, 184)
$optionList.Size = New-Object System.Drawing.Size(280, 414)
$form.Controls.Add($optionList)

$reportText = New-Object System.Windows.Forms.TextBox
$reportText.Location = New-Object System.Drawing.Point(320, 184)
$reportText.Size = New-Object System.Drawing.Size(555, 414)
$reportText.Multiline = $true
$reportText.ReadOnly = $true
$reportText.ScrollBars = 'Vertical'
$reportText.Font = New-Object System.Drawing.Font('Consolas', 10)
$form.Controls.Add($reportText)

$actorLabel = New-Object System.Windows.Forms.Label
$actorLabel.Text = 'Selected by'
$actorLabel.Location = New-Object System.Drawing.Point(320, 623)
$actorLabel.Size = New-Object System.Drawing.Size(90, 28)
$form.Controls.Add($actorLabel)

$actorText = New-Object System.Windows.Forms.TextBox
$actorText.Location = New-Object System.Drawing.Point(415, 620)
$actorText.Size = New-Object System.Drawing.Size(180, 28)
$actorText.Text = $env:USERNAME
$form.Controls.Add($actorText)

$commitButton = New-Object System.Windows.Forms.Button
$commitButton.Text = 'Commit Selected'
$commitButton.Location = New-Object System.Drawing.Point(610, 615)
$commitButton.Size = New-Object System.Drawing.Size(145, 40)
$commitButton.Enabled = $false
$form.Controls.Add($commitButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = 'Close'
$closeButton.Location = New-Object System.Drawing.Point(770, 615)
$closeButton.Size = New-Object System.Drawing.Size(105, 40)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$script:proposals = @()
$script:existingMenuPath = $null

function Get-SelectedMenuPath {
    $week = $weekPicker.Value.Date
    return Join-Path $projectRoot (
        "menus\{0}\{1}.md" -f $week.Year, $week.ToString('yyyy-MM-dd')
    )
}

function Get-PlannedDiners {
    return @(
        $script:dinerInputs |
        ForEach-Object { [int]$_.Value }
    )
}

function Set-PlannedDiners {
    param([int[]]$Values)

    if ($Values.Count -ne 7) {
        return
    }
    for ($index = 0; $index -lt 7; $index++) {
        if ($Values[$index] -ge 1 -and $Values[$index] -le 20) {
            $script:dinerInputs[$index].Value = $Values[$index]
        }
    }
}

function Update-ExistingPlanState {
    param([switch]$LoadDiners)

    $path = Get-SelectedMenuPath
    if (Test-Path -LiteralPath $path) {
        $script:existingMenuPath = $path
        $text = [System.IO.File]::ReadAllText($path)
        $statusMatch = [regex]::Match(
            $text,
            '(?m)^status = "([^"]+)"$'
        )
        $status = if ($statusMatch.Success) {
            $statusMatch.Groups[1].Value
        } else {
            'status unavailable'
        }
        $existingPlanLabel.Text = (
            "Existing plan found for this week | Status: $status"
        )
        $existingPlanLabel.ForeColor = [System.Drawing.Color]::DarkRed
        $existingPlanPanel.BackColor = [System.Drawing.Color]::Moccasin
        $viewExistingButton.Enabled = $true
        if ($LoadDiners) {
            $dinersMatch = [regex]::Match(
                $text,
                '(?m)^planned_diners = \[([0-9,\s]+)\]$'
            )
            if ($dinersMatch.Success) {
                Set-PlannedDiners -Values @(
                    $dinersMatch.Groups[1].Value.Split(',') |
                    ForEach-Object { [int]$_.Trim() }
                )
            }
        }
    } else {
        $script:existingMenuPath = $null
        $existingPlanLabel.Text = 'No existing plan found for this week.'
        $existingPlanLabel.ForeColor = [System.Drawing.Color]::DarkGreen
        $existingPlanPanel.BackColor = [System.Drawing.Color]::Honeydew
        $viewExistingButton.Enabled = $false
        if ($LoadDiners) {
            Set-PlannedDiners -Values @(4, 4, 4, 4, 4, 4, 4)
        }
    }
}

function Format-Proposal {
    param($Proposal, [int]$Number)
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("OPTION $Number")
    $lines.Add("Week of: $($Proposal.week_of)")
    $lines.Add(
        "Diners (Mon-Sun): $(@($Proposal.planned_diners) -join ', ')"
    )
    $lines.Add(('Estimated cost: ${0:N2}' -f [double]$Proposal.estimated_cost_usd))
    $lines.Add(('After inventory: ${0:N2}' -f [double]$Proposal.estimated_shopping_cost_usd))
    $lines.Add("Inventory coverage: $($Proposal.inventory_coverage_score)/100")
    $lines.Add(('Average fiber: {0:N1} g/serving' -f [double]$Proposal.average_fiber_grams))
    $lines.Add(('Kid-friendly score: {0:N1}/5' -f [double]$Proposal.average_kid_friendly_score))
    $lines.Add("Recipe rotation score: $($Proposal.rotation_score)/100")
    $lines.Add("Explainability score: $($Proposal.explainability_score)/100")
    $lines.Add("Weather: $($Proposal.weather_category) ($($Proposal.heat_friendly_meals) heat-friendly meals)")
    $lines.Add('')
    foreach ($meal in $Proposal.meals) {
        $lines.Add(
            "$($meal.day) ($($meal.planned_diners) diners): " +
            "$($meal.recipe_id) rev $($meal.revision) - $($meal.name)"
        )
        $lines.Add("  $($meal.cooking_method), $($meal.fiber_grams)g fiber, `$$($meal.estimated_cost_usd)")
        $lines.Add("  Kid-friendly: $($meal.kid_friendly_reason)")
        $lines.Add('  Why selected:')
        foreach ($reason in @($meal.selection_explanation.reasons)) {
            $lines.Add("    - $reason")
        }
        if (@($meal.side_suggestions).Count -gt 0) {
            $sideNames = @($meal.side_suggestions | ForEach-Object {
                "$($_.name) ($($_.fiber_grams)g fiber)"
            })
            $lines.Add("  Suggested sides: $($sideNames -join '; ')")
        }
        if ($null -ne $meal.kids_quick_meal) {
            $lines.Add(
                "  Kids' quick meal: $($meal.kids_quick_meal.name) " +
                "($($meal.kids_quick_meal.id), `$$($meal.kids_quick_meal.estimated_cost_usd))"
            )
        }
    }
    if ($null -ne $Proposal.planning_trace) {
        $trace = $Proposal.planning_trace
        $lines.Add('')
        $lines.Add('PLANNING TRACE')
        $lines.Add("Candidate recipes available: $($trace.candidate_recipes_available)")
        $lines.Add("Candidate evaluations: $($trace.candidate_evaluations)")
        $lines.Add("Search candidate attempts: $($trace.search_candidate_attempts)")
        $lines.Add(
            "Explainability score: $($trace.explainability.score)/100 " +
            "($($trace.explainability.explained)/$($trace.explainability.decisions) decisions)"
        )
        $lines.Add("Search order: $(@($trace.search_order) -join ' -> ')")
        foreach ($dayTrace in @($trace.days)) {
            $lines.Add('')
            $lines.Add([string]$dayTrace.day)
            $lines.Add('-' * ([string]$dayTrace.day).Length)
            $lines.Add("Started with $($dayTrace.started_count) recipes")
            foreach ($stage in @($dayTrace.stages)) {
                $actionProperty = $stage.PSObject.Properties['action']
                $suffix = if (
                    $null -ne $actionProperty -and
                    [string]$actionProperty.Value -eq 'sorted'
                ) {
                    ' (sorted)'
                } else {
                    ''
                }
                $lines.Add(
                    "  $($stage.name): $($stage.before) -> " +
                    "$($stage.after)$suffix"
                )
            }
            $lines.Add(
                "  Selected: $($dayTrace.selected_recipe_id) - " +
                "$($dayTrace.selected_name)"
            )
            $lines.Add('  Candidate decisions:')
            foreach ($candidate in @($dayTrace.candidates)) {
                $rankProperty = $candidate.PSObject.Properties['rank']
                $rank = if ($null -ne $rankProperty) {
                    $scoreProperty = $candidate.PSObject.Properties['ranking_score']
                    $inventoryProperty = $candidate.PSObject.Properties['inventory_score']
                    $score = if ($null -ne $scoreProperty) {
                        [string]$scoreProperty.Value
                    } else {
                        'n/a'
                    }
                    $inventory = if ($null -ne $inventoryProperty) {
                        [string]$inventoryProperty.Value
                    } else {
                        'n/a'
                    }
                    "rank $($rankProperty.Value), score $score/100, inventory " +
                    "$inventory/100, "
                } else {
                    ''
                }
                $lines.Add(
                    "    - $($candidate.recipe_id) ($($candidate.name)): " +
                    "$rank$($candidate.decision) - $($candidate.reason)"
                )
            }
        }
    }
    if (@($Proposal.errors).Count -gt 0) {
        $lines.Add('')
        $lines.Add('BLOCKING ERRORS')
        foreach ($item in $Proposal.errors) {
            $lines.Add("- $item")
        }
    }
    if (@($Proposal.warnings).Count -gt 0) {
        $lines.Add('')
        $lines.Add('WARNINGS')
        foreach ($item in $Proposal.warnings) {
            $lines.Add("- $item")
        }
    }
    if (@($Proposal.inventory_warnings).Count -gt 0) {
        $lines.Add('')
        $lines.Add('INVENTORY WARNINGS')
        foreach ($item in $Proposal.inventory_warnings) {
            $lines.Add("- $item")
        }
    }
    if (@($Proposal.inventory_buy).Count -gt 0) {
        $lines.Add('')
        $lines.Add('ESTIMATED SHOPPING NEEDS')
        foreach ($item in $Proposal.inventory_buy) {
            $lines.Add("- $($item.name): $($item.quantity) $($item.unit)")
        }
    }
    $lines.Add('')
    $lines.Add('No planning artifacts were written. Engine telemetry was recorded.')
    return $lines -join [Environment]::NewLine
}

$generateButton.Add_Click({
    try {
        if ($weekPicker.Value.DayOfWeek -ne [DayOfWeek]::Monday) {
            throw 'Choose a Monday as the week start.'
        }
        Update-ExistingPlanState
        if ($null -ne $script:existingMenuPath) {
            $answer = [System.Windows.Forms.MessageBox]::Show(
                (
                    "A meal plan already exists for " +
                    "$($weekPicker.Value.ToString('MMMM d, yyyy')).`r`n`r`n" +
                    "Generating dry runs will not change the existing plan. " +
                    "Continue?"
                ),
                'Existing Meal Plan',
                'YesNo',
                'Warning'
            )
            if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
                return
            }
        }
        $week = $weekPicker.Value.ToString('yyyy-MM-dd')
        $diners = (Get-PlannedDiners) -join ','
        $raw = & $python $plannerScript generate `
            --week $week `
            --count 3 `
            --diners $diners `
            --json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ($raw -join [Environment]::NewLine)
        }
        $parsedProposals = ($raw -join [Environment]::NewLine) | ConvertFrom-Json
        $script:proposals = @($parsedProposals)
        $optionList.Items.Clear()
        for ($index = 0; $index -lt $script:proposals.Count; $index++) {
            $proposal = $script:proposals[$index]
            $summary = 'Option {0}: ${1:N0} shop, inv {2}, fiber {3:N1}g, rotation {4}' -f `
                ($index + 1), [double]$proposal.estimated_shopping_cost_usd, `
                $proposal.inventory_coverage_score, `
                [double]$proposal.average_fiber_grams, `
                $proposal.rotation_score
            [void]$optionList.Items.Add($summary)
        }
        if ($optionList.Items.Count -gt 0) {
            $optionList.SelectedIndex = 0
        }
        $commitButton.Enabled = $true
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Dry Run Failed',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$viewExistingButton.Add_Click({
    if ($null -eq $script:existingMenuPath) {
        return
    }
    try {
        $menuText = [System.IO.File]::ReadAllText(
            $script:existingMenuPath
        )
        $menuText = $menuText -replace '\r?\n', [Environment]::NewLine
        $optionList.ClearSelected()
        $commitButton.Enabled = $false
        $reportText.Text = (
            "EXISTING WEEKLY PLAN`r`n" +
            "$($script:existingMenuPath)`r`n`r`n" +
            $menuText
        )
        $reportText.SelectionStart = 0
        $reportText.ScrollToCaret()
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to View Existing Plan',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$optionList.Add_SelectedIndexChanged({
    if ($optionList.SelectedIndex -ge 0) {
        $reportText.Text = Format-Proposal `
            -Proposal $script:proposals[$optionList.SelectedIndex] `
            -Number ($optionList.SelectedIndex + 1)
        $commitButton.Enabled = $true
    }
})

$commitButton.Add_Click({
    try {
        if ($optionList.SelectedIndex -lt 0) {
            throw 'Select a dry-run option.'
        }
        if ([string]::IsNullOrWhiteSpace($actorText.Text)) {
            throw 'Enter the person selecting this plan.'
        }
        $proposal = $script:proposals[$optionList.SelectedIndex]
        if (@($proposal.errors).Count -gt 0) {
            throw 'This option has blocking errors and cannot be committed.'
        }
        $warningText = if (@($proposal.warnings).Count -gt 0) {
            ($proposal.warnings -join [Environment]::NewLine) +
                "`n`nCommit this option with those warnings?"
        } else {
            'Commit this option as the draft weekly menu?'
        }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            $warningText,
            'Commit Dry Run',
            'YesNo',
            'Question'
        )
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            return
        }
        $week = [string]$proposal.week_of
        $assignments = @($proposal.assignments) -join ','
        $arguments = @(
            $plannerScript,
            'apply',
            '--week', $week,
            '--recipes', $assignments,
            '--actor', $actorText.Text,
            '--diners', (@($proposal.planned_diners) -join ',')
        )
        if (@($proposal.warnings).Count -gt 0) {
            $arguments += '--accept-warnings'
        }
        $result = & $python @arguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw ($result -join [Environment]::NewLine)
        }
        [System.Windows.Forms.MessageBox]::Show(
            "Draft weekly menu created:`n$($result -join '')",
            'Dry Run Committed',
            'OK',
            'Information'
        ) | Out-Null
        $form.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Commit',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$weekPicker.Add_ValueChanged({
    Update-ExistingPlanState -LoadDiners
})

$form.CancelButton = $closeButton
$form.Add_Shown({
    Update-ExistingPlanState -LoadDiners
})
. (Join-Path $PSScriptRoot 'gui-branding.ps1')
Add-MealPlannerBranding `
    -Form $form `
    -Title 'Plan Week' `
    -Subtitle 'Dry-run planning and proposal comparison' `
    -IconName 'plan-week'
[void]$form.ShowDialog()
