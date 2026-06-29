Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$script:moduleSessions = New-Object System.Collections.ArrayList
$script:weatherSession = $null
$script:weatherDate = $null
$script:kitchenFactQueue = New-Object System.Collections.ArrayList
$dailyWeatherScript = Join-Path $PSScriptRoot 'daily_weather.py'

function Resolve-Python {
    $bundled = Join-Path $env:USERPROFILE (
        '.cache\codex-runtimes\codex-primary-runtime' +
        '\dependencies\python\python.exe'
    )
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    return $null
}

$python = Resolve-Python

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot 'gui-branding.ps1')

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

function Get-KitchenFact {
    try {
        if ($script:kitchenFactQueue.Count -eq 0) {
            $path = Join-Path $projectRoot (
                'planner-data\kitchen-facts.json'
            )
            $document = (
                Get-Content -Raw -LiteralPath $path |
                ConvertFrom-Json
            )
            $facts = @($document.facts)
            if (
                $document.schema_version -ne 1 -or
                $facts.Count -lt 15 -or
                $facts.Count -gt 20
            ) {
                throw 'Kitchen fact data is invalid.'
            }
            for ($index = $facts.Count - 1; $index -gt 0; $index--) {
                $swapIndex = Get-Random -Minimum 0 -Maximum ($index + 1)
                $temporary = $facts[$index]
                $facts[$index] = $facts[$swapIndex]
                $facts[$swapIndex] = $temporary
            }
            foreach ($fact in $facts) {
                [void]$script:kitchenFactQueue.Add([string]$fact)
            }
        }
        $fact = [string]$script:kitchenFactQueue[0]
        $script:kitchenFactQueue.RemoveAt(0)
        return $fact
    } catch {
        return 'Good meals start with a little curiosity.'
    }
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
    $lowLabel = if ($lowCount -eq 1) { 'item' } else { 'items' }
    return "$($lots.Count) tracked lots | $lowCount low-stock $lowLabel"
}

function Get-OverrideSummary {
    $menuCount = @(
        Get-ChildItem -LiteralPath (Join-Path $projectRoot 'menus') `
            -Recurse -File -Filter '*.md'
    ).Count
    $menuLabel = if ($menuCount -eq 1) { 'menu' } else { 'menus' }
    return "$menuCount weekly $menuLabel available"
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

function Get-CookbookSummary {
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

    $runspace = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
    $runspace.ApartmentState = 'STA'
    $runspace.ThreadOptions = 'ReuseThread'
    $runspace.Open()

    $powerShell = [System.Management.Automation.PowerShell]::Create()
    $powerShell.Runspace = $runspace
    [void]$powerShell.AddCommand($ScriptPath)
    $invocation = $powerShell.BeginInvoke()
    [void]$script:moduleSessions.Add(
        [pscustomobject]@{
            PowerShell = $powerShell
            Runspace = $runspace
            Invocation = $invocation
        }
    )
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Family Meal Planner'
$form.ClientSize = New-Object System.Drawing.Size(900, 650)
$form.MinimumSize = New-Object System.Drawing.Size(916, 689)
$form.StartPosition = 'CenterScreen'
$form.BackColor = $colors.Background
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.MaximizeBox = $false
$iconRoot = Join-Path $projectRoot 'assets\icons'
Set-MealPlannerFormIcon `
    -Form $form `
    -IconPath (Join-Path $iconRoot 'meal-planner-suite.ico')

$header = New-Object System.Windows.Forms.Panel
$header.Location = New-Object System.Drawing.Point(0, 0)
$header.Size = New-Object System.Drawing.Size(900, 112)
$header.Anchor = 'Top,Left,Right'
$header.BackColor = $colors.Header
$form.Controls.Add($header)

$suiteLabel = New-Object System.Windows.Forms.Label
$suiteLabel.Text = 'FAMILY MEAL PLANNER'
$suiteLabel.Location = New-Object System.Drawing.Point(82, 22)
$suiteLabel.Size = New-Object System.Drawing.Size(390, 38)
$suiteLabel.Font = New-Object System.Drawing.Font(
    'Segoe UI Semibold',
    22,
    [System.Drawing.FontStyle]::Bold
)
$suiteLabel.ForeColor = [System.Drawing.Color]::White
$header.Controls.Add($suiteLabel)

$suiteArtwork = New-Object System.Windows.Forms.PictureBox
$suiteArtwork.Location = New-Object System.Drawing.Point(24, 17)
$suiteArtwork.Size = New-Object System.Drawing.Size(48, 48)
$suiteArtwork.SizeMode = 'Zoom'
$suiteArtwork.Image = Get-MealPlannerBitmap -Path (
    Join-Path $iconRoot 'meal-planner-suite.png'
)
$header.Controls.Add($suiteArtwork)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = 'Planning Suite'
$subtitle.Location = New-Object System.Drawing.Point(84, 65)
$subtitle.Size = New-Object System.Drawing.Size(300, 26)
$subtitle.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$subtitle.ForeColor = [System.Drawing.ColorTranslator]::FromHtml('#C9D7D1')
$header.Controls.Add($subtitle)

$weatherLabel = New-Object System.Windows.Forms.Label
$weatherLabel.Text = "Today's weather: Loading..."
$weatherLabel.Location = New-Object System.Drawing.Point(490, 15)
$weatherLabel.Size = New-Object System.Drawing.Size(260, 46)
$weatherLabel.TextAlign = 'MiddleRight'
$weatherLabel.ForeColor = [System.Drawing.Color]::White
$weatherLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$header.Controls.Add($weatherLabel)

$factLabel = New-Object System.Windows.Forms.Label
$factLabel.Text = 'Kitchen fact: Loading...'
$factLabel.Location = New-Object System.Drawing.Point(350, 68)
$factLabel.Size = New-Object System.Drawing.Size(520, 28)
$factLabel.TextAlign = 'MiddleRight'
$factLabel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml('#D9C59C')
$factLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$header.Controls.Add($factLabel)

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
        Icon = 'plan-week'
    },
    [pscustomobject]@{
        Name = 'Kitchen Inventory'
        Detail = 'Maintain ingredients and stock levels'
        Script = Join-Path $PSScriptRoot 'inventory-gui.ps1'
        Status = { Get-InventorySummary }
        Color = $colors.Accent
        Icon = 'kitchen-inventory'
    },
    [pscustomobject]@{
        Name = 'Recipe Cookbook'
        Detail = 'Browse, import, edit, and approve recipes'
        Script = Join-Path $PSScriptRoot 'import-recipe-gui.ps1'
        Status = { Get-CookbookSummary }
        Color = [System.Drawing.ColorTranslator]::FromHtml('#48769A')
        Icon = 'recipe-cookbook'
    },
    [pscustomobject]@{
        Name = 'Override Meal'
        Detail = 'Adjust a planned day'
        Script = Join-Path $PSScriptRoot 'meal-override-gui.ps1'
        Status = { Get-OverrideSummary }
        Color = [System.Drawing.ColorTranslator]::FromHtml('#A04E45')
        Icon = 'override-meal'
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

    $moduleArtwork = New-Object System.Windows.Forms.PictureBox
    $moduleArtwork.Location = New-Object System.Drawing.Point(20, 20)
    $moduleArtwork.Size = New-Object System.Drawing.Size(44, 44)
    $moduleArtwork.SizeMode = 'Zoom'
    $moduleArtwork.Image = Get-MealPlannerBitmap -Path (
        Join-Path $iconRoot "$($module.Icon).png"
    )
    $row.Controls.Add($moduleArtwork)

    $nameLabel = New-Object System.Windows.Forms.Label
    $nameLabel.Text = $module.Name
    $nameLabel.Location = New-Object System.Drawing.Point(78, 12)
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
    $detailLabel.Location = New-Object System.Drawing.Point(78, 44)
    $detailLabel.Size = New-Object System.Drawing.Size(255, 24)
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

$weatherTimer = New-Object System.Windows.Forms.Timer
$weatherTimer.Interval = 250
$weatherTimer.Add_Tick({
    if (
        $null -eq $script:weatherSession -or
        -not $script:weatherSession.Invocation.IsCompleted
    ) {
        return
    }
    try {
        $output = @(
            $script:weatherSession.PowerShell.EndInvoke(
                $script:weatherSession.Invocation
            )
        )
        $raw = (
            $output | ForEach-Object { $_.ToString() }
        ) -join [Environment]::NewLine
        if ($script:weatherSession.PowerShell.HadErrors) {
            throw $raw
        }
        $forecast = $raw | ConvertFrom-Json
        $weatherLabel.Text = (
            "Today in $($forecast.location): " +
            "$($forecast.high_f)/$($forecast.low_f) F`r`n" +
            "$($forecast.description) | " +
            "$($forecast.precipitation_probability)% precip"
        )
        $weatherLabel.ForeColor = [System.Drawing.Color]::White
        $script:weatherDate = (Get-Date).Date
    } catch {
        $weatherLabel.Text = "Today's weather unavailable`r`nZIP 21617"
        $weatherLabel.ForeColor = (
            [System.Drawing.ColorTranslator]::FromHtml('#E7C7A0')
        )
    } finally {
        $script:weatherSession.PowerShell.Dispose()
        $script:weatherSession.Runspace.Dispose()
        $script:weatherSession = $null
        $weatherTimer.Stop()
    }
})

function Start-WeatherRefresh {
    param([switch]$Force)

    if ($null -ne $script:weatherSession) {
        return
    }
    if (
        -not $Force -and
        $script:weatherDate -eq (Get-Date).Date
    ) {
        return
    }
    if ($null -eq $python) {
        $weatherLabel.Text = "Today's weather unavailable`r`nPython not found"
        return
    }

    $weatherLabel.Text = "Today's weather: Loading..."
    $runspace = (
        [System.Management.Automation.Runspaces.RunspaceFactory]
    )::CreateRunspace()
    $runspace.Open()
    $powerShell = [System.Management.Automation.PowerShell]::Create()
    $powerShell.Runspace = $runspace
    [void]$powerShell.AddCommand($python)
    [void]$powerShell.AddArgument($dailyWeatherScript)
    [void]$powerShell.AddArgument('--json')
    $invocation = $powerShell.BeginInvoke()
    $script:weatherSession = [pscustomobject]@{
        PowerShell = $powerShell
        Runspace = $runspace
        Invocation = $invocation
    }
    $weatherTimer.Start()
}

function Refresh-SuiteStatus {
    foreach ($session in @($script:moduleSessions)) {
        if ($session.Invocation.IsCompleted) {
            try {
                [void]$session.PowerShell.EndInvoke($session.Invocation)
            } catch {
                $footer.Text = "Module error: $($_.Exception.Message)"
            } finally {
                $session.PowerShell.Dispose()
                $session.Runspace.Dispose()
                [void]$script:moduleSessions.Remove($session)
            }
        }
    }
    foreach ($label in $statusLabels) {
        try {
            $label.Text = & $label.Tag
            $label.ForeColor = $colors.Muted
        } catch {
            $label.Text = 'Status unavailable'
            $label.ForeColor = [System.Drawing.Color]::Firebrick
        }
    }
    $factLabel.Text = "Kitchen fact: $(Get-KitchenFact)"
    $footer.Text = "Updated $((Get-Date).ToString('h:mm tt'))"
}

$refreshButton.Add_Click({
    Refresh-SuiteStatus
    Start-WeatherRefresh -Force
})
$form.Add_Shown({
    Refresh-SuiteStatus
    Start-WeatherRefresh
})
$form.Add_Activated({ Refresh-SuiteStatus })
$form.Add_FormClosed({
    $weatherTimer.Stop()
    if ($null -ne $script:weatherSession) {
        if ($script:weatherSession.Invocation.IsCompleted) {
            $script:weatherSession.PowerShell.Dispose()
            $script:weatherSession.Runspace.Dispose()
        } else {
            [void]$script:weatherSession.PowerShell.BeginStop(
                $null,
                $null
            )
        }
    }
    foreach ($session in @($script:moduleSessions)) {
        if ($session.Invocation.IsCompleted) {
            $session.PowerShell.Dispose()
            $session.Runspace.Dispose()
        } else {
            [void]$session.PowerShell.BeginStop($null, $null)
        }
    }
    foreach ($row in @($form.Controls | Where-Object {
        $_ -is [System.Windows.Forms.Panel]
    })) {
        foreach ($picture in @($row.Controls | Where-Object {
            $_ -is [System.Windows.Forms.PictureBox]
        })) {
            if ($null -ne $picture.Image) {
                $picture.Image.Dispose()
            }
        }
    }
})

[void]$form.ShowDialog()
