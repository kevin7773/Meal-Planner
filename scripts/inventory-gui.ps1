Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$catalogPath = Join-Path $projectRoot 'inventory\catalog.json'
$stockPath = Join-Path $projectRoot 'inventory\stock.json'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$catalogDocument = Get-Content -Raw -LiteralPath $catalogPath | ConvertFrom-Json
$stockDocument = Get-Content -Raw -LiteralPath $stockPath | ConvertFrom-Json
$catalogById = @{}
foreach ($item in $catalogDocument.items) {
    $catalogById[$item.id] = $item
    $item | Add-Member -NotePropertyName Display -NotePropertyValue "$($item.name) [$($item.class)]"
}
$script:lots = New-Object System.Collections.ArrayList
foreach ($lot in @($stockDocument.items)) {
    [void]$script:lots.Add($lot)
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot 'gui-branding.ps1')
$colors = Get-MealPlannerPalette

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Kitchen Inventory'
$form.ClientSize = New-Object System.Drawing.Size(1080, 720)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
Set-MealPlannerFormSurface -Form $form -Palette $colors

$attentionButton = New-Object System.Windows.Forms.Button
$attentionButton.Text = 'Show Low Stock and Expiring'
$attentionButton.Location = New-Object System.Drawing.Point(20, 18)
$attentionButton.Size = New-Object System.Drawing.Size(235, 36)
$form.Controls.Add($attentionButton)

$attentionNote = New-Object System.Windows.Forms.Label
$attentionNote.Text = 'Expiring means within 7 days.'
$attentionNote.Location = New-Object System.Drawing.Point(270, 22)
$attentionNote.Size = New-Object System.Drawing.Size(300, 28)
$attentionNote.TextAlign = 'MiddleLeft'
$attentionNote.ForeColor = [System.Drawing.Color]::DimGray
$form.Controls.Add($attentionNote)

$grid = New-Object System.Windows.Forms.DataGridView
$grid.Location = New-Object System.Drawing.Point(20, 68)
$grid.Size = New-Object System.Drawing.Size(1040, 312)
$grid.ReadOnly = $true
$grid.AllowUserToAddRows = $false
$grid.AllowUserToDeleteRows = $false
$grid.MultiSelect = $false
$grid.SelectionMode = 'FullRowSelect'
$grid.AutoSizeColumnsMode = 'Fill'
foreach ($columnName in @(
    'Lot ID',
    'Item ID',
    'Ingredient',
    'Class',
    'On Hand',
    'Unit',
    'Level',
    'Acquired',
    'Expires',
    'Attention'
)) {
    [void]$grid.Columns.Add(($columnName -replace ' ', ''), $columnName)
}
$grid.Columns['LotID'].Visible = $false
$grid.Columns['ItemID'].Visible = $false
$grid.Columns['Attention'].FillWeight = 150
$form.Controls.Add($grid)

function Add-Label {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width = 130)
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($Width, 28)
    $label.TextAlign = 'MiddleLeft'
    $form.Controls.Add($label)
}

Add-Label 'Ingredient' 20 410
$ingredientCombo = New-Object System.Windows.Forms.ComboBox
$ingredientCombo.Location = New-Object System.Drawing.Point(150, 410)
$ingredientCombo.Size = New-Object System.Drawing.Size(360, 28)
$ingredientCombo.DropDownStyle = 'DropDownList'
$ingredientCombo.DisplayMember = 'Display'
foreach ($item in @($catalogDocument.items | Sort-Object name)) {
    [void]$ingredientCombo.Items.Add($item)
}
$ingredientCombo.SelectedIndex = 0
$form.Controls.Add($ingredientCombo)

Add-Label 'Quantity' 540 410 90
$quantity = New-Object System.Windows.Forms.NumericUpDown
$quantity.Location = New-Object System.Drawing.Point(630, 410)
$quantity.Size = New-Object System.Drawing.Size(110, 28)
$quantity.DecimalPlaces = 2
$quantity.Maximum = 9999
$quantity.Minimum = 0
$form.Controls.Add($quantity)

$unitLabel = New-Object System.Windows.Forms.Label
$unitLabel.Location = New-Object System.Drawing.Point(750, 410)
$unitLabel.Size = New-Object System.Drawing.Size(100, 28)
$unitLabel.TextAlign = 'MiddleLeft'
$form.Controls.Add($unitLabel)

Add-Label 'Level' 850 410 60
$levelCombo = New-Object System.Windows.Forms.ComboBox
$levelCombo.Location = New-Object System.Drawing.Point(910, 410)
$levelCombo.Size = New-Object System.Drawing.Size(150, 28)
$levelCombo.DropDownStyle = 'DropDownList'
@('full', 'half', 'low') | ForEach-Object { [void]$levelCombo.Items.Add($_) }
$levelCombo.SelectedIndex = 0
$form.Controls.Add($levelCombo)

Add-Label 'Acquired on' 20 458
$acquiredPicker = New-Object System.Windows.Forms.DateTimePicker
$acquiredPicker.Location = New-Object System.Drawing.Point(150, 458)
$acquiredPicker.Size = New-Object System.Drawing.Size(230, 28)
$acquiredPicker.ShowCheckBox = $true
$acquiredPicker.Checked = $false
$form.Controls.Add($acquiredPicker)

Add-Label 'Expires on' 410 458 100
$expiresPicker = New-Object System.Windows.Forms.DateTimePicker
$expiresPicker.Location = New-Object System.Drawing.Point(510, 458)
$expiresPicker.Size = New-Object System.Drawing.Size(230, 28)
$expiresPicker.ShowCheckBox = $true
$expiresPicker.Checked = $false
$form.Controls.Add($expiresPicker)

$behaviorLabel = New-Object System.Windows.Forms.Label
$behaviorLabel.Location = New-Object System.Drawing.Point(20, 510)
$behaviorLabel.Size = New-Object System.Drawing.Size(1040, 50)
$behaviorLabel.BorderStyle = 'FixedSingle'
$behaviorLabel.Padding = New-Object System.Windows.Forms.Padding(10)
$form.Controls.Add($behaviorLabel)

$newButton = New-Object System.Windows.Forms.Button
$newButton.Text = 'New Lot'
$newButton.Location = New-Object System.Drawing.Point(20, 585)
$newButton.Size = New-Object System.Drawing.Size(110, 38)
$form.Controls.Add($newButton)

$addButton = New-Object System.Windows.Forms.Button
$addButton.Text = 'Add to Inventory'
$addButton.Location = New-Object System.Drawing.Point(145, 585)
$addButton.Size = New-Object System.Drawing.Size(130, 38)
$form.Controls.Add($addButton)

$removeButton = New-Object System.Windows.Forms.Button
$removeButton.Text = 'Remove'
$removeButton.Location = New-Object System.Drawing.Point(290, 585)
$removeButton.Size = New-Object System.Drawing.Size(110, 38)
$removeButton.Enabled = $false
$form.Controls.Add($removeButton)

$saveButton = New-Object System.Windows.Forms.Button
$saveButton.Text = 'Save Inventory'
$saveButton.Location = New-Object System.Drawing.Point(790, 585)
$saveButton.Size = New-Object System.Drawing.Size(135, 38)
$form.Controls.Add($saveButton)

$closeButton = New-Object System.Windows.Forms.Button
$closeButton.Text = 'Close'
$closeButton.Location = New-Object System.Drawing.Point(940, 585)
$closeButton.Size = New-Object System.Drawing.Size(120, 38)
$closeButton.Add_Click({ $form.Close() })
$form.Controls.Add($closeButton)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(20, 650)
$statusLabel.Size = New-Object System.Drawing.Size(1040, 32)
$statusLabel.ForeColor = [System.Drawing.Color]::DarkGreen
$form.Controls.Add($statusLabel)

$script:editingLotId = $null
$script:attentionOnly = $false

function Get-QuantityTotals {
    $totals = @{}
    foreach ($lot in $script:lots) {
        if ($null -eq $lot.quantity) {
            continue
        }
        if (-not $totals.ContainsKey($lot.item_id)) {
            $totals[$lot.item_id] = 0.0
        }
        $totals[$lot.item_id] += [double]$lot.quantity
    }
    return $totals
}

function Get-AttentionReasons {
    param(
        $Lot,
        $Item,
        [hashtable]$QuantityTotals
    )

    $reasons = New-Object System.Collections.Generic.List[string]
    if ($Item.class -eq 'consumable' -and $Lot.level -eq 'low') {
        $reasons.Add('Low stock')
    }

    $minimum = if ($null -ne $Item.minimum) {
        [double]$Item.minimum
    } else {
        0.0
    }
    $total = if ($QuantityTotals.ContainsKey($Item.id)) {
        [double]$QuantityTotals[$Item.id]
    } else {
        0.0
    }
    if (
        $Item.class -ne 'consumable' -and
        $minimum -gt 0 -and
        $total -lt $minimum
    ) {
        $reasons.Add(
            "Low: $total $($Item.unit), minimum $minimum"
        )
    }

    if (
        $null -ne $Lot.expires_on -and
        -not [string]::IsNullOrWhiteSpace([string]$Lot.expires_on)
    ) {
        $expiration = ([datetime]$Lot.expires_on).Date
        $today = (Get-Date).Date
        if ($expiration -lt $today) {
            $reasons.Add(
                "Expired $($expiration.ToString('MMM d'))"
            )
        } elseif ($expiration -le $today.AddDays(7)) {
            $reasons.Add(
                "Expires $($expiration.ToString('MMM d'))"
            )
        }
    }
    return @($reasons)
}

function Refresh-Editor {
    $item = $ingredientCombo.SelectedItem
    if ($null -eq $item) {
        return
    }
    $unitLabel.Text = $item.unit
    $isConsumable = $item.class -eq 'consumable'
    $quantity.Enabled = -not $isConsumable
    $levelCombo.Enabled = $isConsumable
    $acquiredPicker.Enabled = $item.class -in @('frozen', 'fresh-produce', 'refrigerated')
    $expiresPicker.Enabled = $true
    if ($item.class -in @('frozen', 'fresh-produce') -and -not $acquiredPicker.Checked) {
        $acquiredPicker.Checked = $true
        $acquiredPicker.Value = Get-Date
    }
    if ($item.class -eq 'frozen') {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = $acquiredPicker.Value.AddMonths(6)
    } elseif (
        $item.class -eq 'fresh-produce' -and
        -not $expiresPicker.Checked
    ) {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = $acquiredPicker.Value.AddDays(5)
    } elseif (
        $item.class -eq 'refrigerated' -and
        -not $expiresPicker.Checked
    ) {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = (Get-Date).AddDays(7)
    } elseif (
        $null -eq $script:editingLotId -and
        $item.class -notin @('frozen', 'fresh-produce', 'refrigerated')
    ) {
        $expiresPicker.Checked = $false
    }
    $behaviorLabel.Text = "$($item.class): $($catalogDocument.classes.($item.class))"
}

function Refresh-Grid {
    $grid.Rows.Clear()
    $quantityTotals = Get-QuantityTotals
    $ordered = @($script:lots | Sort-Object item_id, acquired_on)
    $trackedItemIds = @{}
    $attentionCount = 0
    foreach ($lot in $ordered) {
        if (-not $catalogById.ContainsKey($lot.item_id)) {
            continue
        }
        $trackedItemIds[[string]$lot.item_id] = $true
        $item = $catalogById[$lot.item_id]
        $reasons = @(
            Get-AttentionReasons `
                -Lot $lot `
                -Item $item `
                -QuantityTotals $quantityTotals
        )
        if ($reasons.Count -gt 0) {
            $attentionCount++
        }
        if ($script:attentionOnly -and $reasons.Count -eq 0) {
            continue
        }
        $quantityText = if ($null -ne $lot.quantity) { [string]$lot.quantity } else { '' }
        $levelText = if ($null -ne $lot.level) { [string]$lot.level } else { '' }
        $rowIndex = $grid.Rows.Add(
            $lot.lot_id,
            $item.id,
            $item.name,
            $item.class,
            $quantityText,
            $item.unit,
            $levelText,
            [string]$lot.acquired_on,
            [string]$lot.expires_on,
            ($reasons -join '; ')
        )
        if ($reasons.Count -gt 0) {
            $grid.Rows[$rowIndex].DefaultCellStyle.BackColor = (
                [System.Drawing.Color]::LightYellow
            )
        }
    }
    $untrackedCount = 0
    foreach ($item in @($catalogDocument.items | Sort-Object name)) {
        if ($trackedItemIds.ContainsKey([string]$item.id)) {
            continue
        }
        $untrackedCount++
        $minimumProperty = $item.PSObject.Properties['minimum_quantity']
        $minimum = if (
            $null -ne $minimumProperty -and
            $null -ne $minimumProperty.Value
        ) {
            [double]$item.minimum_quantity
        } else {
            0.0
        }
        $needsAttention = $item.class -ne 'consumable' -and $minimum -gt 0
        if ($needsAttention) {
            $attentionCount++
        }
        if ($script:attentionOnly -and -not $needsAttention) {
            continue
        }
        $quantityText = if ($item.class -eq 'consumable') { '' } else { '0' }
        $levelText = if ($item.class -eq 'consumable') { 'not tracked' } else { '' }
        $attentionText = if ($needsAttention) {
            "Not stocked; minimum $minimum $($item.unit)"
        } else {
            'Not in inventory'
        }
        $rowIndex = $grid.Rows.Add(
            '',
            $item.id,
            $item.name,
            $item.class,
            $quantityText,
            $item.unit,
            $levelText,
            '',
            '',
            $attentionText
        )
        $grid.Rows[$rowIndex].DefaultCellStyle.ForeColor = (
            [System.Drawing.Color]::DimGray
        )
        if ($needsAttention) {
            $grid.Rows[$rowIndex].DefaultCellStyle.BackColor = (
                [System.Drawing.Color]::LightYellow
            )
        }
    }
    if ($script:attentionOnly) {
        $statusLabel.Text = (
            "$attentionCount low-stock, missing, or expiring item(s) shown. " +
            'Unsaved changes remain until Save Inventory is clicked.'
        )
    } else {
        $statusLabel.Text = (
            "$($catalogDocument.items.Count) catalog item(s); " +
            "$($trackedItemIds.Count) tracked, $untrackedCount not tracked. " +
            "$attentionCount need attention. " +
            'Unsaved changes remain until Save Inventory is clicked.'
        )
    }
}

function Reset-Editor {
    $script:editingLotId = $null
    $addButton.Text = 'Add to Inventory'
    $removeButton.Enabled = $false
    $quantity.Value = 0
    $levelCombo.SelectedIndex = 0
    $acquiredPicker.Checked = $false
    $expiresPicker.Checked = $false
    $grid.ClearSelection()
    Refresh-Editor
}

$ingredientCombo.Add_SelectedIndexChanged({ Refresh-Editor })
$acquiredPicker.Add_ValueChanged({
    $item = $ingredientCombo.SelectedItem
    if ($null -ne $item -and $acquiredPicker.Checked) {
        if ($item.class -eq 'frozen') {
            $expiresPicker.Checked = $true
            $expiresPicker.Value = $acquiredPicker.Value.AddMonths(6)
        } elseif ($item.class -eq 'fresh-produce') {
            $expiresPicker.Checked = $true
            $expiresPicker.Value = $acquiredPicker.Value.AddDays(5)
        }
    }
})
$newButton.Add_Click({ Reset-Editor })
$attentionButton.Add_Click({
    $script:attentionOnly = -not $script:attentionOnly
    $attentionButton.Text = if ($script:attentionOnly) {
        'Show All Inventory'
    } else {
        'Show Low Stock and Expiring'
    }
    Refresh-Grid
})

$grid.Add_SelectionChanged({
    if ($grid.SelectedRows.Count -ne 1) {
        return
    }
    $lotId = [string]$grid.SelectedRows[0].Cells['LotID'].Value
    $itemId = [string]$grid.SelectedRows[0].Cells['ItemID'].Value
    for ($index = 0; $index -lt $ingredientCombo.Items.Count; $index++) {
        if ($ingredientCombo.Items[$index].id -eq $itemId) {
            $ingredientCombo.SelectedIndex = $index
            break
        }
    }
    $lot = $script:lots | Where-Object { $_.lot_id -eq $lotId } | Select-Object -First 1
    if ($null -eq $lot) {
        $script:editingLotId = $null
        $addButton.Text = 'Add to Inventory'
        $removeButton.Enabled = $false
        $quantity.Value = 0
        $levelCombo.SelectedIndex = 0
        $acquiredPicker.Checked = $false
        $expiresPicker.Checked = $false
        Refresh-Editor
        return
    }
    $script:editingLotId = $lotId
    $addButton.Text = 'Update Lot'
    $removeButton.Enabled = $true
    if ($null -ne $lot.quantity) {
        $quantity.Value = [decimal]$lot.quantity
    }
    if ($null -ne $lot.level) {
        $levelCombo.SelectedItem = [string]$lot.level
    }
    if ($null -ne $lot.acquired_on -and [string]$lot.acquired_on -ne '') {
        $acquiredPicker.Checked = $true
        $acquiredPicker.Value = [datetime]$lot.acquired_on
    } else {
        $acquiredPicker.Checked = $false
    }
    if ($null -ne $lot.expires_on -and [string]$lot.expires_on -ne '') {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = [datetime]$lot.expires_on
    } elseif ($item.class -eq 'fresh-produce' -and $acquiredPicker.Checked) {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = $acquiredPicker.Value.AddDays(5)
    } else {
        $expiresPicker.Checked = $false
    }
})

$addButton.Add_Click({
    try {
        $item = $ingredientCombo.SelectedItem
        if ($null -eq $item) {
            throw 'Select an ingredient.'
        }
        if ($item.class -ne 'consumable' -and $quantity.Value -le 0) {
            throw 'Quantity must be greater than zero.'
        }
        if ($item.class -in @('frozen', 'fresh-produce') -and -not $acquiredPicker.Checked) {
            throw "$($item.class) inventory requires an acquired date."
        }
        if ($item.class -eq 'refrigerated' -and -not $expiresPicker.Checked) {
            throw 'Refrigerated inventory requires an expiration date.'
        }
        if ($item.class -eq 'frozen' -and -not $expiresPicker.Checked) {
            throw 'Frozen inventory requires an expiration date.'
        }
        $lotId = if ($null -ne $script:editingLotId) {
            $script:editingLotId
        } else {
            [guid]::NewGuid().ToString('N')
        }
        for ($index = $script:lots.Count - 1; $index -ge 0; $index--) {
            if (
                $script:lots[$index].lot_id -eq $lotId -or
                (
                    $item.class -eq 'consumable' -and
                    $script:lots[$index].item_id -eq $item.id
                )
            ) {
                $script:lots.RemoveAt($index)
            }
        }
        $lot = [pscustomobject][ordered]@{
            lot_id = $lotId
            item_id = [string]$item.id
            quantity = if ($item.class -eq 'consumable') { $null } else { [double]$quantity.Value }
            level = if ($item.class -eq 'consumable') { [string]$levelCombo.SelectedItem } else { $null }
            acquired_on = if ($acquiredPicker.Checked) { $acquiredPicker.Value.ToString('yyyy-MM-dd') } else { $null }
            expires_on = if ($expiresPicker.Checked) { $expiresPicker.Value.ToString('yyyy-MM-dd') } else { $null }
        }
        [void]$script:lots.Add($lot)
        Reset-Editor
        Refresh-Grid
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Inventory Entry Error',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$removeButton.Add_Click({
    if ($grid.SelectedRows.Count -ne 1) {
        return
    }
    $lotId = [string]$grid.SelectedRows[0].Cells['LotID'].Value
    if ([string]::IsNullOrWhiteSpace($lotId)) {
        return
    }
    for ($index = $script:lots.Count - 1; $index -ge 0; $index--) {
        if ($script:lots[$index].lot_id -eq $lotId) {
            $script:lots.RemoveAt($index)
        }
    }
    Reset-Editor
    Refresh-Grid
})

$saveButton.Add_Click({
    try {
        $document = [ordered]@{
            schema_version = 1
            updated_at = (Get-Date).ToUniversalTime().ToString('o')
            items = @($script:lots)
        }
        $json = $document | ConvertTo-Json -Depth 6
        [System.IO.File]::WriteAllText($stockPath, $json, $utf8NoBom)
        $statusLabel.Text = "Saved $($script:lots.Count) inventory lot(s) at $(Get-Date -Format 'h:mm tt')."
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            'Unable to Save Inventory',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$form.CancelButton = $closeButton
Set-MealPlannerButtonStyle -Button $attentionButton -Color $colors.Override
Set-MealPlannerButtonStyle -Button $newButton -Color $colors.Email
Set-MealPlannerButtonStyle -Button $addButton -Color $colors.Pantry
Set-MealPlannerButtonStyle -Button $removeButton -Color $colors.Override
Set-MealPlannerButtonStyle -Button $saveButton -Color $colors.Pantry
Set-MealPlannerNeutralButtonStyle -Button $closeButton -Palette $colors
$grid.EnableHeadersVisualStyles = $false
$grid.ColumnHeadersDefaultCellStyle.BackColor = $colors.Pantry
$grid.ColumnHeadersDefaultCellStyle.ForeColor = [System.Drawing.Color]::White
$grid.BackgroundColor = $colors.Surface
$grid.AlternatingRowsDefaultCellStyle.BackColor = $colors.SoftPantry
$behaviorLabel.BackColor = $colors.SoftPantry
$behaviorLabel.ForeColor = $colors.Text
$statusLabel.BackColor = $colors.SoftPantry
$statusLabel.ForeColor = $colors.PantryText
$statusLabel.Padding = New-Object System.Windows.Forms.Padding(10, 0, 0, 0)
Refresh-Editor
Refresh-Grid
Add-MealPlannerBranding `
    -Form $form `
    -Title 'Kitchen Inventory' `
    -Subtitle 'Stock, expiration, and pantry readiness' `
    -IconName 'kitchen-inventory'
[void]$form.ShowDialog()
