Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$colors = @{
    Background = [System.Drawing.ColorTranslator]::FromHtml('#F3F6F4')
    Header = [System.Drawing.ColorTranslator]::FromHtml('#24312D')
    Primary = [System.Drawing.ColorTranslator]::FromHtml('#28765A')
    Accent = [System.Drawing.ColorTranslator]::FromHtml('#C5842C')
    Text = [System.Drawing.ColorTranslator]::FromHtml('#202624')
    Muted = [System.Drawing.ColorTranslator]::FromHtml('#66716D')
    Border = [System.Drawing.ColorTranslator]::FromHtml('#D5DDD9')
    Surface = [System.Drawing.Color]::White
}

function Get-NextMonday {
    $today = (Get-Date).Date
    $days = (([int][DayOfWeek]::Monday - [int]$today.DayOfWeek) + 7) % 7
    if ($days -eq 0) {
        $days = 7
    }
    return $today.AddDays($days)
}

function Get-RecipeSummary {
    $excluded = @('README.md', 'index.md', '_template.md')
    $files = @(
        Get-ChildItem -LiteralPath (Join-Path $projectRoot 'recipes') `
            -File -Filter '*.md' |
            Where-Object Name -NotIn $excluded
    )
    $candidateCount = 0
    foreach ($file in $files) {
        $text = [System.IO.File]::ReadAllText($file.FullName)
        if ($text -match '(?m)^status = "candidate"$') {
            $candidateCount++
        }
    }
    return "$($files.Count) recipes | $candidateCount candidates"
}

function Get-InventorySummary {
    $path = Join-Path $projectRoot 'inventory\stock.json'
    $document = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    $lots = @($document.items)
    $lowCount = @(
        $lots | Where-Object {
            $_.PSObject.Properties.Name -contains 'level' -and
            $_.level -eq 'low'
        }
    ).Count
    return "$($lots.Count) tracked lots | $lowCount low-stock items"
}

function Get-FeedbackSummary {
    $feedbackRoot = Join-Path $projectRoot 'feedback'
    $feedbackCount = @(
        Get-ChildItem -LiteralPath $feedbackRoot -File -ErrorAction SilentlyContinue
    ).Count
    $recipeCount = (
        (Get-RecipeSummary) -split ' '
    )[0]
    return "$recipeCount recipes available | $feedbackCount feedback records"
}

function Get-OverrideSummary {
    $menuCount = @(
        Get-ChildItem -LiteralPath (Join-Path $projectRoot 'menus') `
            -Recurse -File -Filter '*.md'
    ).Count
    return "$menuCount weekly menus available"
}

function Get-PlanSummary {
    $week = Get-NextMonday
    $menuPath = Join-Path $projectRoot (
        "menus\{0}\{1}.md" -f $week.Year, $week.ToString('yyyy-MM-dd')
    )
    $status = 'not generated'
    if (Test-Path -LiteralPath $menuPath) {
        $text = [System.IO.File]::ReadAllText($menuPath)
        $match = [regex]::Match($text, '(?m)^status = "([^"]+)"$')
        if ($match.Success) {
            $status = $match.Groups[1].Value
        } else {
            $status = 'menu exists'
        }
    }
    return "Week of $($week.ToString('MMM d, yyyy')) | $status"
}

function Get-ImportSummary {
    $recipeSummary = Get-RecipeSummary
    $ideaPath = Join-Path $projectRoot 'ideas\recipe-ideas.json'
    $ideaCount = 0
    if (Test-Path -LiteralPath $ideaPath) {
        $document = Get-Content -Raw -LiteralPath $ideaPath | ConvertFrom-Json
        if ($document.PSObject.Properties.Name -contains 'ideas') {
            $ideaCount = @($document.ideas).Count
        }
    }
    return "$recipeSummary | $ideaCount saved ideas"
}

function Start-SuiteModule {
    param([string]$ScriptPath)

    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        [System.Windows.Forms.MessageBox]::Show(
            "Module script was not found:`r`n$ScriptPath",
            'Unable to Open Module',
            'OK',
            'Error'
        ) | Out-Null
        return
    }

    $powerShellPath = (Get-Process -Id $PID).Path
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $powerShellPath
    $startInfo.Arguments = (
        '-NoProfile -ExecutionPolicy Bypass -STA -File "{0}"' -f
        $ScriptPath.Replace('"', '\"')
    )
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    [void][System.Diagnostics.Process]::Start($startInfo)
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Family Meal Planner'
$form.ClientSize = New-Object System.Drawing.Size(900, 650)
$form.MinimumSize = New-Object System.Drawing.Size(916, 689)
$form.StartPosition = 'CenterScreen'
$form.BackColor = $colors.Background
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.MaximizeBox = $false

$header = New-Object System.Windows.Forms.Panel
$header.Location = New-Object System.Drawing.Point(0, 0)
$header.Size = New-Object System.Drawing.Size(900, 112)
$header.Anchor = 'Top,Left,Right'
$header.BackColor = $colors.Header
$form.Controls.Add($header)

$suiteLabel = New-Object System.Windows.Forms.Label
$suiteLabel.Text = 'FAMILY MEAL PLANNER'
$suiteLabel.Location = New-Object System.Drawing.Point(28, 22)
$suiteLabel.Size = New-Object System.Drawing.Size(520, 38)
$suiteLabel.Font = New-Object System.Drawing.Font(
    'Segoe UI Semibold',
    22,
    [System.Drawing.FontStyle]::Bold
)
$suiteLabel.ForeColor = [System.Drawing.Color]::White
$header.Controls.Add($suiteLabel)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = 'Planning Suite'
$subtitle.Location = New-Object System.Drawing.Point(31, 65)
$subtitle.Size = New-Object System.Drawing.Size(300, 26)
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$subtitle.ForeColor = [System.Drawing.ColorTranslator]::FromHtml('#C9D7D1')
$header.Controls.Add($subtitle)

$refreshButton = New-Object System.Windows.Forms.Button
$refreshButton.Text = 'Refresh'
$refreshButton.Location = New-Object System.Drawing.Point(770, 36)
$refreshButton.Size = New-Object System.Drawing.Size(100, 38)
$refreshButton.Anchor = 'Top,Right'
$refreshButton.FlatStyle = 'Flat'
$refreshButton.FlatAppearance.BorderColor = $colors.Accent
$refreshButton.ForeColor = [System.Drawing.Color]::White
$refreshButton.BackColor = $colors.Header
$header.Controls.Add($refreshButton)

$modules = @(
    [pscustomobject]@{
        Name = 'Plan Week'
        Detail = 'Create and compare weekly proposals'
        Script = Join-Path $PSScriptRoot 'plan-week.ps1'
        Status = { Get-PlanSummary }
        Color = $colors.Primary
    },
    [pscustomobject]@{
        Name = 'Kitchen Inventory'
        Detail = 'Maintain ingredients and stock levels'
        Script = Join-Path $PSScriptRoot 'inventory-gui.ps1'
        Status = { Get-InventorySummary }
        Color = $colors.Accent
    },
    [pscustomobject]@{
        Name = 'Import Recipe'
        Detail = 'Add recipes and meal ideas'
        Script = Join-Path $PSScriptRoot 'import-recipe-gui.ps1'
        Status = { Get-ImportSummary }
        Color = [System.Drawing.ColorTranslator]::FromHtml('#48769A')
    },
    [pscustomobject]@{
        Name = 'Review Meal'
        Detail = 'Record ratings and family feedback'
        Script = Join-Path $PSScriptRoot 'recipe-feedback.ps1'
        Status = { Get-FeedbackSummary }
        Color = [System.Drawing.ColorTranslator]::FromHtml('#8A5D86')
    },
    [pscustomobject]@{
        Name = 'Override Meal'
        Detail = 'Adjust a planned day'
        Script = Join-Path $PSScriptRoot 'meal-override-gui.ps1'
        Status = { Get-OverrideSummary }
        Color = [System.Drawing.ColorTranslator]::FromHtml('#A04E45')
    }
)

$statusLabels = New-Object System.Collections.ArrayList
$rowTop = 132
foreach ($module in $modules) {
    $row = New-Object System.Windows.Forms.Panel
    $row.Location = New-Object System.Drawing.Point(24, $rowTop)
    $row.Size = New-Object System.Drawing.Size(852, 86)
    $row.Anchor = 'Top,Left,Right'
    $row.BackColor = $colors.Surface
    $row.BorderStyle = 'FixedSingle'
    $form.Controls.Add($row)

    $stripe = New-Object System.Windows.Forms.Panel
    $stripe.Location = New-Object System.Drawing.Point(0, 0)
    $stripe.Size = New-Object System.Drawing.Size(7, 84)
    $stripe.BackColor = $module.Color
    $row.Controls.Add($stripe)

    $nameLabel = New-Object System.Windows.Forms.Label
    $nameLabel.Text = $module.Name
    $nameLabel.Location = New-Object System.Drawing.Point(22, 12)
    $nameLabel.Size = New-Object System.Drawing.Size(250, 27)
    $nameLabel.Font = New-Object System.Drawing.Font(
        'Segoe UI Semibold',
        12,
        [System.Drawing.FontStyle]::Bold
    )
    $nameLabel.ForeColor = $colors.Text
    $row.Controls.Add($nameLabel)

    $detailLabel = New-Object System.Windows.Forms.Label
    $detailLabel.Text = $module.Detail
    $detailLabel.Location = New-Object System.Drawing.Point(22, 44)
    $detailLabel.Size = New-Object System.Drawing.Size(310, 24)
    $detailLabel.ForeColor = $colors.Muted
    $row.Controls.Add($detailLabel)

    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.Location = New-Object System.Drawing.Point(350, 29)
    $statusLabel.Size = New-Object System.Drawing.Size(350, 28)
    $statusLabel.ForeColor = $colors.Muted
    $statusLabel.TextAlign = 'MiddleLeft'
    $statusLabel.Tag = $module.Status
    $row.Controls.Add($statusLabel)
    [void]$statusLabels.Add($statusLabel)

    $openButton = New-Object System.Windows.Forms.Button
    $openButton.Text = 'Open'
    $openButton.Location = New-Object System.Drawing.Point(725, 23)
    $openButton.Size = New-Object System.Drawing.Size(100, 38)
    $openButton.Anchor = 'Top,Right'
    $openButton.FlatStyle = 'Flat'
    $openButton.FlatAppearance.BorderColor = $module.Color
    $openButton.ForeColor = [System.Drawing.Color]::White
    $openButton.BackColor = $module.Color
    $scriptPath = $module.Script
    $openButton.Add_Click({
        Start-SuiteModule -ScriptPath $scriptPath
    }.GetNewClosure())
    $row.Controls.Add($openButton)

    $rowTop += 96
}

$footer = New-Object System.Windows.Forms.Label
$footer.Text = 'Ready'
$footer.Location = New-Object System.Drawing.Point(27, 616)
$footer.Size = New-Object System.Drawing.Size(840, 24)
$footer.Anchor = 'Bottom,Left,Right'
$footer.ForeColor = $colors.Muted
$form.Controls.Add($footer)

function Refresh-SuiteStatus {
    foreach ($label in $statusLabels) {
        try {
            $label.Text = & $label.Tag
            $label.ForeColor = $colors.Muted
        } catch {
            $label.Text = 'Status unavailable'
            $label.ForeColor = [System.Drawing.Color]::Firebrick
        }
    }
    $footer.Text = "Updated $((Get-Date).ToString('h:mm tt'))"
}

$refreshButton.Add_Click({ Refresh-SuiteStatus })
$form.Add_Shown({ Refresh-SuiteStatus })
$form.Add_Activated({ Refresh-SuiteStatus })

[void]$form.ShowDialog()
