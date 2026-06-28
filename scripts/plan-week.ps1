Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$plannerScript = Join-Path $PSScriptRoot 'planner_cli.py'
$workflowScript = Join-Path $PSScriptRoot 'week_workflow.py'
$emailSettingsPath = Join-Path $projectRoot 'preferences\email-settings.json'

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

function Resolve-OnePasswordCli {
    $command = Get-Command op.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $wingetPattern = Join-Path $env:LOCALAPPDATA (
        'Microsoft\WinGet\Packages\AgileBits.1Password.CLI_*\op.exe'
    )
    $wingetCli = Get-Item $wingetPattern -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $wingetCli) {
        return $wingetCli.FullName
    }
    return $null
}

function Get-EmailSettings {
    if (-not (Test-Path -LiteralPath $emailSettingsPath)) {
        return [pscustomobject]@{
            schema_version = 1
            sender_email = ''
            password_source = 'manual'
            onepassword_reference = ''
        }
    }
    $settings = (
        [System.IO.File]::ReadAllText($emailSettingsPath) |
            ConvertFrom-Json
    )
    if ([int]$settings.schema_version -ne 1) {
        throw 'Email settings use an unsupported schema version.'
    }
    return $settings
}

function Save-EmailSettings {
    param(
        [string]$Sender,
        [string]$PasswordSource,
        [string]$OnePasswordReference
    )

    $settings = [ordered]@{
        schema_version = 1
        sender_email = $Sender
        password_source = $PasswordSource
        onepassword_reference = $OnePasswordReference
    }
    $parent = Split-Path -Parent $emailSettingsPath
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    [System.IO.File]::WriteAllText(
        $emailSettingsPath,
        ($settings | ConvertTo-Json -Depth 3) + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Read-OnePasswordSecret {
    param([string]$Reference)

    if (-not $Reference.StartsWith('op://')) {
        throw 'The 1Password secret reference must start with op://.'
    }
    $op = Resolve-OnePasswordCli
    if ($null -eq $op) {
        throw '1Password CLI is not installed. Install it with: winget install 1password-cli'
    }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $raw = & $op read $Reference --no-newline 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) {
        throw (
            '1Password could not read the configured secret. Unlock the ' +
            '1Password desktop app, enable CLI integration under Settings > ' +
            'Developer, and verify the secret reference.'
        )
    }
    return (($raw -join '') -replace '\s', '')
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$colors = @{
    Background = [System.Drawing.ColorTranslator]::FromHtml('#F3F6F4')
    Surface = [System.Drawing.Color]::White
    Text = [System.Drawing.ColorTranslator]::FromHtml('#202624')
    Muted = [System.Drawing.ColorTranslator]::FromHtml('#66716D')
    Border = [System.Drawing.ColorTranslator]::FromHtml('#D5DDD9')
    Planner = [System.Drawing.ColorTranslator]::FromHtml('#28765A')
    Pantry = [System.Drawing.ColorTranslator]::FromHtml('#C5842C')
    Email = [System.Drawing.ColorTranslator]::FromHtml('#48769A')
    Review = [System.Drawing.ColorTranslator]::FromHtml('#8A5D86')
    Override = [System.Drawing.ColorTranslator]::FromHtml('#A04E45')
    SoftPlanner = [System.Drawing.ColorTranslator]::FromHtml('#E8F3ED')
    SoftPantry = [System.Drawing.ColorTranslator]::FromHtml('#FFF2DD')
    SoftEmail = [System.Drawing.ColorTranslator]::FromHtml('#E8F0F7')
    SoftReview = [System.Drawing.ColorTranslator]::FromHtml('#F1EAF1')
    SoftMuted = [System.Drawing.ColorTranslator]::FromHtml('#ECEFED')
}

function Set-SectionButtonStyle {
    param(
        [System.Windows.Forms.Button]$Button,
        [System.Drawing.Color]$Color
    )

    $Button.FlatStyle = 'Flat'
    $Button.FlatAppearance.BorderSize = 0
    $Button.BackColor = $Color
    $Button.ForeColor = [System.Drawing.Color]::White
    $Button.UseVisualStyleBackColor = $false
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Weekly Meal Planner - Dry Run'
$form.ClientSize = New-Object System.Drawing.Size(1060, 680)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.BackColor = $colors.Background
$form.ForeColor = $colors.Text

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
$existingPlanPanel.Size = New-Object System.Drawing.Size(1020, 44)
$existingPlanPanel.BorderStyle = 'FixedSingle'
$form.Controls.Add($existingPlanPanel)

$existingPlanLabel = New-Object System.Windows.Forms.Label
$existingPlanLabel.Location = New-Object System.Drawing.Point(12, 7)
$existingPlanLabel.Size = New-Object System.Drawing.Size(385, 28)
$existingPlanLabel.TextAlign = 'MiddleLeft'
$existingPlanPanel.Controls.Add($existingPlanLabel)

$viewExistingButton = New-Object System.Windows.Forms.Button
$viewExistingButton.Text = 'Raw Markdown'
$viewExistingButton.Location = New-Object System.Drawing.Point(865, 5)
$viewExistingButton.Size = New-Object System.Drawing.Size(140, 32)
$viewExistingButton.Enabled = $false
$existingPlanPanel.Controls.Add($viewExistingButton)

$viewSummaryButton = New-Object System.Windows.Forms.Button
$viewSummaryButton.Text = 'Menu Summary'
$viewSummaryButton.Location = New-Object System.Drawing.Point(400, 5)
$viewSummaryButton.Size = New-Object System.Drawing.Size(145, 32)
$viewSummaryButton.Enabled = $false
$existingPlanPanel.Controls.Add($viewSummaryButton)

$viewGroceryButton = New-Object System.Windows.Forms.Button
$viewGroceryButton.Text = 'Grocery List'
$viewGroceryButton.Location = New-Object System.Drawing.Point(555, 5)
$viewGroceryButton.Size = New-Object System.Drawing.Size(140, 32)
$viewGroceryButton.Enabled = $false
$existingPlanPanel.Controls.Add($viewGroceryButton)

$viewEmailsButton = New-Object System.Windows.Forms.Button
$viewEmailsButton.Text = 'Email Drafts'
$viewEmailsButton.Location = New-Object System.Drawing.Point(705, 5)
$viewEmailsButton.Size = New-Object System.Drawing.Size(150, 32)
$viewEmailsButton.Enabled = $false
$existingPlanPanel.Controls.Add($viewEmailsButton)

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
$optionList.Size = New-Object System.Drawing.Size(300, 330)
$form.Controls.Add($optionList)

$reportText = New-Object System.Windows.Forms.TextBox
$reportText.Location = New-Object System.Drawing.Point(340, 184)
$reportText.Size = New-Object System.Drawing.Size(700, 330)
$reportText.Multiline = $true
$reportText.ReadOnly = $true
$reportText.ScrollBars = 'Vertical'
$reportText.Font = New-Object System.Drawing.Font('Consolas', 10)
$form.Controls.Add($reportText)

$actorLabel = New-Object System.Windows.Forms.Label
$actorLabel.Text = 'Selected by'
$actorLabel.Location = New-Object System.Drawing.Point(340, 533)
$actorLabel.Size = New-Object System.Drawing.Size(90, 28)
$form.Controls.Add($actorLabel)

$actorText = New-Object System.Windows.Forms.TextBox
$actorText.Location = New-Object System.Drawing.Point(435, 530)
$actorText.Size = New-Object System.Drawing.Size(180, 28)
$actorText.Text = $env:USERNAME
$form.Controls.Add($actorText)

$commitButton = New-Object System.Windows.Forms.Button
$commitButton.Text = 'Commit Selected'
$commitButton.Location = New-Object System.Drawing.Point(690, 525)
$commitButton.Size = New-Object System.Drawing.Size(145, 40)
$commitButton.Enabled = $false
$form.Controls.Add($commitButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = 'Close'
$closeButton.Location = New-Object System.Drawing.Point(935, 525)
$closeButton.Size = New-Object System.Drawing.Size(105, 40)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$workflowStatusLabel = New-Object System.Windows.Forms.Label
$workflowStatusLabel.Location = New-Object System.Drawing.Point(20, 575)
$workflowStatusLabel.Size = New-Object System.Drawing.Size(1020, 28)
$workflowStatusLabel.TextAlign = 'MiddleLeft'
$workflowStatusLabel.ForeColor = [System.Drawing.Color]::DimGray
$form.Controls.Add($workflowStatusLabel)

$generatePackageButton = New-Object System.Windows.Forms.Button
$generatePackageButton.Text = 'Generate Review Package'
$generatePackageButton.Location = New-Object System.Drawing.Point(20, 615)
$generatePackageButton.Size = New-Object System.Drawing.Size(210, 40)
$generatePackageButton.Enabled = $false
$form.Controls.Add($generatePackageButton)

$approvePackageButton = New-Object System.Windows.Forms.Button
$approvePackageButton.Text = 'Approve Package'
$approvePackageButton.Location = New-Object System.Drawing.Point(245, 615)
$approvePackageButton.Size = New-Object System.Drawing.Size(175, 40)
$approvePackageButton.Enabled = $false
$form.Controls.Add($approvePackageButton)

$sendEmailsButton = New-Object System.Windows.Forms.Button
$sendEmailsButton.Text = 'Send Approved Emails'
$sendEmailsButton.Location = New-Object System.Drawing.Point(435, 615)
$sendEmailsButton.Size = New-Object System.Drawing.Size(205, 40)
$sendEmailsButton.Enabled = $false
$form.Controls.Add($sendEmailsButton)

$testEmailButton = New-Object System.Windows.Forms.Button
$testEmailButton.Text = 'Test Email Setup'
$testEmailButton.Location = New-Object System.Drawing.Point(655, 615)
$testEmailButton.Size = New-Object System.Drawing.Size(185, 40)
$testEmailButton.Enabled = $true
$form.Controls.Add($testEmailButton)

Set-SectionButtonStyle -Button $generateButton -Color $colors.Planner
Set-SectionButtonStyle -Button $viewSummaryButton -Color $colors.Planner
Set-SectionButtonStyle -Button $viewGroceryButton -Color $colors.Pantry
Set-SectionButtonStyle -Button $viewEmailsButton -Color $colors.Email
Set-SectionButtonStyle -Button $viewExistingButton -Color $colors.Override
Set-SectionButtonStyle -Button $commitButton -Color $colors.Planner
Set-SectionButtonStyle -Button $generatePackageButton -Color $colors.Planner
Set-SectionButtonStyle -Button $approvePackageButton -Color $colors.Review
Set-SectionButtonStyle -Button $sendEmailsButton -Color $colors.Email
Set-SectionButtonStyle -Button $testEmailButton -Color $colors.Email

$closeButton.FlatStyle = 'Flat'
$closeButton.FlatAppearance.BorderColor = $colors.Border
$closeButton.BackColor = $colors.Surface
$closeButton.ForeColor = $colors.Text

$optionList.BackColor = $colors.SoftPlanner
$optionList.ForeColor = $colors.Text
$reportText.BackColor = $colors.Surface
$reportText.ForeColor = $colors.Text
$workflowStatusLabel.BackColor = $colors.SoftMuted
$workflowStatusLabel.ForeColor = $colors.Muted
$workflowStatusLabel.Padding = New-Object System.Windows.Forms.Padding(10, 0, 0, 0)

$script:proposals = @()
$script:existingMenuPath = $null
$script:existingStatus = $null
$script:hasMealOverrides = $false
$script:emailSettings = Get-EmailSettings
$script:lastEmailSender = [Environment]::GetEnvironmentVariable(
    'MEAL_PLANNER_EMAIL_FROM',
    'Process'
)
if ([string]::IsNullOrWhiteSpace($script:lastEmailSender)) {
    $script:lastEmailSender = [string]$script:emailSettings.sender_email
}

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

function Invoke-WeekWorkflow {
    param(
        [string]$Command,
        [string]$Actor = '',
        [string]$Sender = ''
    )

    $workflowArguments = @(
        $workflowScript,
        $Command,
        '--week', $weekPicker.Value.ToString('yyyy-MM-dd'),
        '--json'
    )
    if (-not [string]::IsNullOrWhiteSpace($Actor)) {
        $workflowArguments += @('--actor', $Actor)
    }
    if (-not [string]::IsNullOrWhiteSpace($Sender)) {
        $workflowArguments += @('--sender', $Sender)
    }
    $raw = & $python @workflowArguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($raw -join [Environment]::NewLine)
    }
    return ($raw -join [Environment]::NewLine) | ConvertFrom-Json
}

function Show-WorkflowContent {
    param(
        [string]$Property,
        [string]$Title
    )

    $package = Invoke-WeekWorkflow -Command 'inspect'
    $optionList.ClearSelected()
    $commitButton.Enabled = $false
    $content = [string]$package.$Property
    $reportText.Text = (
        "$Title`r`nWeek of $($package.week_of) | " +
        "Status: $($package.status)`r`n`r`n" +
        ($content -replace '\r?\n', [Environment]::NewLine)
    )
    $reportText.SelectionStart = 0
    $reportText.ScrollToCaret()
}

function Show-EmailCredentialDialog {
    param([switch]$TestOnly)

    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = if ($TestOnly) {
        'Test Meal Planner Email Setup'
    } else {
        'Send Approved Meal Plan Emails'
    }
    $dialog.ClientSize = New-Object System.Drawing.Size(570, 335)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    $dialog.Font = New-Object System.Drawing.Font('Segoe UI', 10)

    $note = New-Object System.Windows.Forms.Label
    $note.Text = if ($TestOnly) {
        (
            'Authenticate with Gmail without sending a message. Use a saved ' +
            '1Password reference or enter the app password manually.'
        )
    } else {
        (
            'Use a saved 1Password secret reference or enter the Google app ' +
            'password manually. Plaintext passwords are never saved.'
        )
    }
    $note.Location = New-Object System.Drawing.Point(20, 18)
    $note.Size = New-Object System.Drawing.Size(530, 45)
    $dialog.Controls.Add($note)

    $sourceLabel = New-Object System.Windows.Forms.Label
    $sourceLabel.Text = 'Password source'
    $sourceLabel.Location = New-Object System.Drawing.Point(20, 72)
    $sourceLabel.Size = New-Object System.Drawing.Size(130, 28)
    $dialog.Controls.Add($sourceLabel)

    $sourceCombo = New-Object System.Windows.Forms.ComboBox
    $sourceCombo.Location = New-Object System.Drawing.Point(155, 70)
    $sourceCombo.Size = New-Object System.Drawing.Size(390, 28)
    $sourceCombo.DropDownStyle = 'DropDownList'
    [void]$sourceCombo.Items.Add('1Password')
    [void]$sourceCombo.Items.Add('Enter manually')
    $sourceCombo.SelectedItem = if (
        $script:emailSettings.password_source -eq '1password' -or
        -not [string]::IsNullOrWhiteSpace(
            [string]$script:emailSettings.onepassword_reference
        ) -or
        $null -ne (Resolve-OnePasswordCli)
    ) {
        '1Password'
    } else {
        'Enter manually'
    }
    $dialog.Controls.Add($sourceCombo)

    $senderLabel = New-Object System.Windows.Forms.Label
    $senderLabel.Text = 'Sender email'
    $senderLabel.Location = New-Object System.Drawing.Point(20, 112)
    $senderLabel.Size = New-Object System.Drawing.Size(130, 28)
    $dialog.Controls.Add($senderLabel)

    $senderText = New-Object System.Windows.Forms.TextBox
    $senderText.Location = New-Object System.Drawing.Point(155, 110)
    $senderText.Size = New-Object System.Drawing.Size(390, 28)
    $senderText.Text = [string]$script:lastEmailSender
    $dialog.Controls.Add($senderText)

    $referenceLabel = New-Object System.Windows.Forms.Label
    $referenceLabel.Text = 'Secret reference'
    $referenceLabel.Location = New-Object System.Drawing.Point(20, 152)
    $referenceLabel.Size = New-Object System.Drawing.Size(130, 28)
    $dialog.Controls.Add($referenceLabel)

    $referenceText = New-Object System.Windows.Forms.TextBox
    $referenceText.Location = New-Object System.Drawing.Point(155, 150)
    $referenceText.Size = New-Object System.Drawing.Size(390, 28)
    $referenceText.Text = [string]$script:emailSettings.onepassword_reference
    $dialog.Controls.Add($referenceText)

    $passwordLabel = New-Object System.Windows.Forms.Label
    $passwordLabel.Text = 'App password'
    $passwordLabel.Location = New-Object System.Drawing.Point(20, 192)
    $passwordLabel.Size = New-Object System.Drawing.Size(130, 28)
    $dialog.Controls.Add($passwordLabel)

    $passwordText = New-Object System.Windows.Forms.TextBox
    $passwordText.Location = New-Object System.Drawing.Point(155, 190)
    $passwordText.Size = New-Object System.Drawing.Size(390, 28)
    $passwordText.UseSystemPasswordChar = $true
    $dialog.Controls.Add($passwordText)

    $sourceHelp = New-Object System.Windows.Forms.Label
    $sourceHelp.Location = New-Object System.Drawing.Point(155, 225)
    $sourceHelp.Size = New-Object System.Drawing.Size(390, 35)
    $sourceHelp.ForeColor = [System.Drawing.Color]::DimGray
    $dialog.Controls.Add($sourceHelp)

    $updateSourceControls = {
        $usingOnePassword = $sourceCombo.SelectedItem -eq '1Password'
        $referenceText.Enabled = $usingOnePassword
        $passwordText.Enabled = -not $usingOnePassword
        $sourceHelp.Text = if ($usingOnePassword) {
            'Example: op://Private/Meal Planner Gmail/password'
        } else {
            'Use the 16-character Google app password. Spaces are ignored.'
        }
    }
    $sourceCombo.Add_SelectedIndexChanged($updateSourceControls)
    & $updateSourceControls

    $sendButton = New-Object System.Windows.Forms.Button
    $sendButton.Text = if ($TestOnly) { 'Test' } else { 'Send' }
    $sendButton.Location = New-Object System.Drawing.Point(355, 280)
    $sendButton.Size = New-Object System.Drawing.Size(90, 34)
    $sendButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dialog.Controls.Add($sendButton)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = 'Cancel'
    $cancelButton.Location = New-Object System.Drawing.Point(455, 280)
    $cancelButton.Size = New-Object System.Drawing.Size(90, 34)
    $cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dialog.Controls.Add($cancelButton)

    $dialog.AcceptButton = $sendButton
    $dialog.CancelButton = $cancelButton
    if ($dialog.ShowDialog($form) -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }
    if ([string]::IsNullOrWhiteSpace($senderText.Text)) {
        throw 'Sender email is required.'
    }
    $passwordSource = if ($sourceCombo.SelectedItem -eq '1Password') {
        '1password'
    } else {
        'manual'
    }
    if ($passwordSource -eq '1password') {
        if ([string]::IsNullOrWhiteSpace($referenceText.Text)) {
            throw 'Enter a 1Password secret reference.'
        }
        $appPassword = Read-OnePasswordSecret -Reference $referenceText.Text.Trim()
    } else {
        if ([string]::IsNullOrWhiteSpace($passwordText.Text)) {
            throw 'Enter the Google app password.'
        }
        $appPassword = $passwordText.Text -replace '\s', ''
    }
    if ($appPassword.Length -ne 16) {
        throw (
            'Google app passwords contain 16 characters. Generate one in ' +
            'Google Account Security after enabling 2-Step Verification.'
        )
    }
    $script:lastEmailSender = $senderText.Text.Trim()
    Save-EmailSettings `
        -Sender $script:lastEmailSender `
        -PasswordSource $passwordSource `
        -OnePasswordReference $(if ($passwordSource -eq '1password') {
            $referenceText.Text.Trim()
        } else {
            ''
        })
    $script:emailSettings = Get-EmailSettings
    return [pscustomobject]@{
        Sender = $senderText.Text.Trim()
        Password = $appPassword
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
        $script:existingStatus = $status
        $existingPlanLabel.Text = (
            "Existing plan found for this week | Status: $status"
        )
        switch ($status) {
            'draft' {
                $existingPlanLabel.ForeColor = $colors.Pantry
                $existingPlanPanel.BackColor = $colors.SoftPantry
                $workflowStatusLabel.BackColor = $colors.SoftPantry
            }
            { $_ -in @('generated', 'validated') } {
                $existingPlanLabel.ForeColor = $colors.Email
                $existingPlanPanel.BackColor = $colors.SoftEmail
                $workflowStatusLabel.BackColor = $colors.SoftEmail
            }
            'reviewed' {
                $existingPlanLabel.ForeColor = $colors.Review
                $existingPlanPanel.BackColor = $colors.SoftReview
                $workflowStatusLabel.BackColor = $colors.SoftReview
            }
            { $_ -in @('approved', 'completed') } {
                $existingPlanLabel.ForeColor = $colors.Planner
                $existingPlanPanel.BackColor = $colors.SoftPlanner
                $workflowStatusLabel.BackColor = $colors.SoftPlanner
            }
            default {
                $existingPlanLabel.ForeColor = $colors.Muted
                $existingPlanPanel.BackColor = $colors.SoftMuted
                $workflowStatusLabel.BackColor = $colors.SoftMuted
            }
        }
        $viewExistingButton.Enabled = $true
        $viewSummaryButton.Enabled = $true
        $groceryPath = Join-Path $projectRoot (
            "grocery-lists\{0}\{1}-grocery-list.md" -f
                $weekPicker.Value.Year,
                $weekPicker.Value.ToString('yyyy-MM-dd')
        )
        $emailRoot = Join-Path $projectRoot (
            "email-outputs\{0}\{1}" -f
                $weekPicker.Value.Year,
                $weekPicker.Value.ToString('yyyy-MM-dd')
        )
        $emailDraftsComplete = @(
            'email-1-mon-tue.md',
            'email-2-wed-thu-fri.md',
            'email-3-sat-sun.md'
        ) | ForEach-Object {
            Test-Path -LiteralPath (Join-Path $emailRoot $_)
        }
        $viewGroceryButton.Enabled = Test-Path -LiteralPath $groceryPath
        $viewEmailsButton.Enabled = (
            @($emailDraftsComplete | Where-Object { -not $_ }).Count -eq 0
        )
        $overridePath = Join-Path $projectRoot (
            "overrides\{0}\{1}-overrides.json" -f
                $weekPicker.Value.Year,
                $weekPicker.Value.ToString('yyyy-MM-dd')
        )
        $script:hasMealOverrides = Test-Path -LiteralPath $overridePath
        $generatePackageButton.Text = if (
            $status -eq 'draft' -and $script:hasMealOverrides
        ) {
            'Revalidate Override'
        } else {
            'Generate Review Package'
        }
        $generatePackageButton.Enabled = $status -in @('draft', 'generated')
        $approvePackageButton.Enabled = (
            $status -in @('validated', 'reviewed') -and
            $viewGroceryButton.Enabled -and
            $viewEmailsButton.Enabled
        )
        $sendEmailsButton.Enabled = $status -eq 'approved'
        $workflowStatusLabel.Text = switch ($status) {
            'draft' {
                if ($script:hasMealOverrides) {
                    'Review the overridden menu, then click Revalidate Override before approval.'
                } else {
                    'Review the menu summary, then generate the grocery and email review package.'
                }
            }
            'generated' {
                'Package generation is incomplete; run Generate Review Package to validate it.'
            }
            'validated' {
                'Review Menu Summary, Grocery List, and Email Drafts, then approve the package.'
            }
            'reviewed' {
                'Human review is recorded. Approve the package to authorize delivery.'
            }
            'approved' {
                'Package is approved. Send Approved Emails is now available.'
            }
            'completed' {
                'All approved emails were sent successfully.'
            }
            'archived' {
                'This weekly package is archived and read-only.'
            }
            default {
                "Existing package status: $status"
            }
        }
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
        $script:existingStatus = $null
        $script:hasMealOverrides = $false
        $generatePackageButton.Text = 'Generate Review Package'
        $existingPlanLabel.Text = 'No existing plan found for this week.'
        $existingPlanLabel.ForeColor = $colors.Planner
        $existingPlanPanel.BackColor = $colors.SoftPlanner
        $viewExistingButton.Enabled = $false
        $viewSummaryButton.Enabled = $false
        $viewGroceryButton.Enabled = $false
        $viewEmailsButton.Enabled = $false
        $generatePackageButton.Enabled = $false
        $approvePackageButton.Enabled = $false
        $sendEmailsButton.Enabled = $false
        $workflowStatusLabel.Text = (
            'Generate dry runs and commit one option to begin the review workflow.'
        )
        $workflowStatusLabel.BackColor = $colors.SoftMuted
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
        $staticCandidatesProperty = $trace.PSObject.Properties[
            'static_candidates_considered'
        ]
        $staticCandidates = if ($null -ne $staticCandidatesProperty) {
            $staticCandidatesProperty.Value
        } else {
            $trace.candidate_evaluations
        }
        $lines.Add("Static candidates considered: $staticCandidates")
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
            "EXISTING WEEKLY PLAN - RAW MARKDOWN`r`n" +
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

$viewSummaryButton.Add_Click({
    try {
        Show-WorkflowContent `
            -Property 'menu_summary' `
            -Title 'HUMAN-READABLE MENU SUMMARY'
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to View Menu Summary',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$viewGroceryButton.Add_Click({
    try {
        Show-WorkflowContent `
            -Property 'grocery_text' `
            -Title 'GROCERY LIST'
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to View Grocery List',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$viewEmailsButton.Add_Click({
    try {
        Show-WorkflowContent `
            -Property 'email_text' `
            -Title 'EMAIL DRAFTS'
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to View Email Drafts',
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
            (
                "Draft weekly menu created:`n$($result -join '')`n`n" +
                'Review the menu summary, then generate the review package.'
            ),
            'Dry Run Committed',
            'OK',
            'Information'
        ) | Out-Null
        $script:proposals = @()
        $optionList.Items.Clear()
        $commitButton.Enabled = $false
        Update-ExistingPlanState -LoadDiners
        Show-WorkflowContent `
            -Property 'menu_summary' `
            -Title 'HUMAN-READABLE DRAFT MENU'
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Commit',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$generatePackageButton.Add_Click({
    try {
        $isOverrideRevalidation = (
            $script:existingStatus -eq 'draft' -and
            $script:hasMealOverrides
        )
        $confirmation = if ($isOverrideRevalidation) {
            (
                'Rebuild the grocery list and email drafts for the overridden ' +
                'menu, then run automated validation?'
            )
        } else {
            (
                'Generate the grocery list and three email drafts, then run ' +
                'automated validation?'
            )
        }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            $confirmation,
            $(if ($isOverrideRevalidation) {
                'Revalidate Override'
            } else {
                'Generate Review Package'
            }),
            'YesNo',
            'Question'
        )
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            return
        }
        $form.UseWaitCursor = $true
        $package = Invoke-WeekWorkflow -Command 'generate'
        Update-ExistingPlanState
        $reportText.Text = (
            "REVIEW PACKAGE READY`r`n" +
            "Week of $($package.week_of) | Status: $($package.status)`r`n`r`n" +
            ($package.menu_summary -replace '\r?\n', [Environment]::NewLine)
        )
        $reportText.SelectionStart = 0
        $reportText.ScrollToCaret()
        [System.Windows.Forms.MessageBox]::Show(
            $(if ($isOverrideRevalidation) {
                (
                    'The overridden menu, grocery list, and email drafts are ' +
                    'validated. Review each view before approving the package.'
                )
            } else {
                (
                'The menu, grocery list, and email drafts are validated. ' +
                'Review each view before approving the package.'
                )
            }),
            'Review Package Ready',
            'OK',
            'Information'
        ) | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Generate Review Package',
            'OK',
            'Error'
        ) | Out-Null
    } finally {
        $form.UseWaitCursor = $false
    }
})

$approvePackageButton.Add_Click({
    try {
        if ([string]::IsNullOrWhiteSpace($actorText.Text)) {
            throw 'Enter the person reviewing and approving this package.'
        }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            (
                'I have reviewed the menu summary, grocery list, and all ' +
                'three email drafts. Approve this package for delivery?'
            ),
            'Approve Weekly Package',
            'YesNo',
            'Warning'
        )
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            return
        }
        $package = Invoke-WeekWorkflow `
            -Command 'approve' `
            -Actor $actorText.Text
        Update-ExistingPlanState
        $reportText.Text = (
            "PACKAGE APPROVED FOR DELIVERY`r`n" +
            "Week of $($package.week_of) | Status: $($package.status)`r`n`r`n" +
            ($package.menu_summary -replace '\r?\n', [Environment]::NewLine)
        )
        [System.Windows.Forms.MessageBox]::Show(
            'Approval recorded. Send Approved Emails is now available.',
            'Package Approved',
            'OK',
            'Information'
        ) | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Approve Package',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$sendEmailsButton.Add_Click({
    try {
        if ([string]::IsNullOrWhiteSpace($actorText.Text)) {
            throw 'Enter the person authorizing email delivery.'
        }
        $answer = [System.Windows.Forms.MessageBox]::Show(
            (
                'This will immediately send all three approved weekly menu ' +
                'emails. Continue?'
            ),
            'Send Approved Emails',
            'YesNo',
            'Warning'
        )
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            return
        }
        $credentials = Show-EmailCredentialDialog
        if ($null -eq $credentials) {
            return
        }
        $previousPassword = [Environment]::GetEnvironmentVariable(
            'MEAL_PLANNER_EMAIL_PASSWORD',
            'Process'
        )
        try {
            [Environment]::SetEnvironmentVariable(
                'MEAL_PLANNER_EMAIL_PASSWORD',
                $credentials.Password,
                'Process'
            )
            $form.UseWaitCursor = $true
            $package = Invoke-WeekWorkflow `
                -Command 'send' `
                -Actor $actorText.Text `
                -Sender $credentials.Sender
        } finally {
            [Environment]::SetEnvironmentVariable(
                'MEAL_PLANNER_EMAIL_PASSWORD',
                $previousPassword,
                'Process'
            )
            $credentials.Password = ''
            $form.UseWaitCursor = $false
        }
        Update-ExistingPlanState
        $reportText.Text = (
            "EMAIL DELIVERY COMPLETE`r`n" +
            "Week of $($package.week_of) | Status: $($package.status)`r`n`r`n" +
            "Message IDs:`r`n" +
            (@($package.message_ids) -join [Environment]::NewLine)
        )
        [System.Windows.Forms.MessageBox]::Show(
            'All three approved emails were sent successfully.',
            'Email Delivery Complete',
            'OK',
            'Information'
        ) | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            (
                "$($_.Exception.Message)`r`n`r`n" +
                'Any successfully sent message was recorded; retrying will ' +
                'send only drafts that remain unsent.'
            ),
            'Email Delivery Failed',
            'OK',
            'Error'
        ) | Out-Null
        Update-ExistingPlanState
    }
})

$testEmailButton.Add_Click({
    try {
        $credentials = Show-EmailCredentialDialog -TestOnly
        if ($null -eq $credentials) {
            return
        }
        $previousPassword = [Environment]::GetEnvironmentVariable(
            'MEAL_PLANNER_EMAIL_PASSWORD',
            'Process'
        )
        try {
            [Environment]::SetEnvironmentVariable(
                'MEAL_PLANNER_EMAIL_PASSWORD',
                $credentials.Password,
                'Process'
            )
            $form.UseWaitCursor = $true
            $result = Invoke-WeekWorkflow `
                -Command 'test-email' `
                -Sender $credentials.Sender
        } finally {
            [Environment]::SetEnvironmentVariable(
                'MEAL_PLANNER_EMAIL_PASSWORD',
                $previousPassword,
                'Process'
            )
            $credentials.Password = ''
            $form.UseWaitCursor = $false
        }
        [System.Windows.Forms.MessageBox]::Show(
            (
                "Email authentication succeeded for $($result.sender).`r`n" +
                'No message was sent.'
            ),
            'Email Setup Verified',
            'OK',
            'Information'
        ) | Out-Null
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Email Setup Test Failed',
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
