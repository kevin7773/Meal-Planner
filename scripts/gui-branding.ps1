function Get-MealPlannerBitmap {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $source = [System.Drawing.Image]::FromFile($Path)
    try {
        return New-Object System.Drawing.Bitmap($source)
    } finally {
        $source.Dispose()
    }
}

function Get-MealPlannerPalette {
    return @{
        Background = [System.Drawing.ColorTranslator]::FromHtml('#F3F6F4')
        Surface = [System.Drawing.Color]::White
        Header = [System.Drawing.ColorTranslator]::FromHtml('#24312D')
        Planner = [System.Drawing.ColorTranslator]::FromHtml('#28765A')
        Pantry = [System.Drawing.ColorTranslator]::FromHtml('#C5842C')
        PantryText = [System.Drawing.ColorTranslator]::FromHtml('#8A5A1B')
        Email = [System.Drawing.ColorTranslator]::FromHtml('#48769A')
        Review = [System.Drawing.ColorTranslator]::FromHtml('#8A5D86')
        Override = [System.Drawing.ColorTranslator]::FromHtml('#A04E45')
        Text = [System.Drawing.ColorTranslator]::FromHtml('#202624')
        Muted = [System.Drawing.ColorTranslator]::FromHtml('#66716D')
        Border = [System.Drawing.ColorTranslator]::FromHtml('#D5DDD9')
        SoftPlanner = [System.Drawing.ColorTranslator]::FromHtml('#E8F3ED')
        SoftPantry = [System.Drawing.ColorTranslator]::FromHtml('#FFF2DD')
        SoftEmail = [System.Drawing.ColorTranslator]::FromHtml('#E8F0F7')
        SoftReview = [System.Drawing.ColorTranslator]::FromHtml('#F1EAF1')
        SoftOverride = [System.Drawing.ColorTranslator]::FromHtml('#F7E8E6')
        SoftMuted = [System.Drawing.ColorTranslator]::FromHtml('#ECEFED')
    }
}

function Set-MealPlannerButtonStyle {
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

function Set-MealPlannerNeutralButtonStyle {
    param(
        [System.Windows.Forms.Button]$Button,
        [hashtable]$Palette
    )

    $Button.FlatStyle = 'Flat'
    $Button.FlatAppearance.BorderColor = $Palette.Border
    $Button.BackColor = $Palette.Surface
    $Button.ForeColor = $Palette.Text
    $Button.UseVisualStyleBackColor = $false
}

function Set-MealPlannerFormSurface {
    param(
        [System.Windows.Forms.Form]$Form,
        [hashtable]$Palette
    )

    $Form.BackColor = $Palette.Background
    $Form.ForeColor = $Palette.Text
}

function Set-MealPlannerFormIcon {
    param(
        [System.Windows.Forms.Form]$Form,
        [string]$IconPath
    )

    if (-not (Test-Path -LiteralPath $IconPath)) {
        return
    }
    $icon = New-Object System.Drawing.Icon($IconPath)
    $Form.Icon = $icon
    $Form.Add_FormClosed({
        $icon.Dispose()
    }.GetNewClosure())
}

function Add-MealPlannerBranding {
    param(
        [System.Windows.Forms.Form]$Form,
        [string]$Title,
        [string]$Subtitle,
        [string]$IconName,
        [switch]$PreserveClientHeight
    )

    $headerHeight = 60
    $existingControls = @($Form.Controls)
    foreach ($control in $existingControls) {
        $control.Top += $headerHeight
    }
    if (-not $PreserveClientHeight) {
        $Form.ClientSize = New-Object System.Drawing.Size(
            $Form.ClientSize.Width,
            ($Form.ClientSize.Height + $headerHeight)
        )
    }
    $Form.Text = "Family Meal Planner - $Title"

    $assetRoot = Join-Path (
        Split-Path -Parent $PSScriptRoot
    ) 'assets\icons'
    $pngPath = Join-Path $assetRoot "$IconName.png"
    $icoPath = Join-Path $assetRoot "$IconName.ico"
    Set-MealPlannerFormIcon -Form $Form -IconPath $icoPath

    $header = New-Object System.Windows.Forms.Panel
    $header.Location = New-Object System.Drawing.Point(0, 0)
    $header.Size = New-Object System.Drawing.Size(
        $Form.ClientSize.Width,
        $headerHeight
    )
    $header.Anchor = 'Top,Left,Right'
    $header.BackColor = (
        [System.Drawing.ColorTranslator]::FromHtml('#24312D')
    )

    $bitmap = Get-MealPlannerBitmap -Path $pngPath
    if ($null -ne $bitmap) {
        $picture = New-Object System.Windows.Forms.PictureBox
        $picture.Location = New-Object System.Drawing.Point(14, 8)
        $picture.Size = New-Object System.Drawing.Size(44, 44)
        $picture.SizeMode = 'Zoom'
        $picture.Image = $bitmap
        $header.Controls.Add($picture)
        $Form.Add_FormClosed({
            $bitmap.Dispose()
        }.GetNewClosure())
    }

    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = $Title
    $titleLabel.Location = New-Object System.Drawing.Point(72, 7)
    $titleLabel.Size = New-Object System.Drawing.Size(
        ($Form.ClientSize.Width - 90),
        27
    )
    $titleLabel.Anchor = 'Top,Left,Right'
    $titleLabel.Font = New-Object System.Drawing.Font(
        'Segoe UI Semibold',
        12,
        [System.Drawing.FontStyle]::Bold
    )
    $titleLabel.ForeColor = [System.Drawing.Color]::White
    $header.Controls.Add($titleLabel)

    $subtitleLabel = New-Object System.Windows.Forms.Label
    $subtitleLabel.Text = $Subtitle
    $subtitleLabel.Location = New-Object System.Drawing.Point(73, 33)
    $subtitleLabel.Size = New-Object System.Drawing.Size(
        ($Form.ClientSize.Width - 90),
        20
    )
    $subtitleLabel.Anchor = 'Top,Left,Right'
    $subtitleLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
    $subtitleLabel.ForeColor = (
        [System.Drawing.ColorTranslator]::FromHtml('#C9D7D1')
    )
    $header.Controls.Add($subtitleLabel)

    $Form.Controls.Add($header)
    $header.BringToFront()
}
