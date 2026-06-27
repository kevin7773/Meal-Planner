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

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Kitchen Inventory'
$form.ClientSize = New-Object System.Drawing.Size(1080, 720)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

$grid = New-Object System.Windows.Forms.DataGridView
$grid.Location = New-Object System.Drawing.Point(20, 20)
$grid.Size = New-Object System.Drawing.Size(1040, 360)
$grid.ReadOnly = $true
$grid.AllowUserToAddRows = $false
$grid.AllowUserToDeleteRows = $false
$grid.MultiSelect = $false
$grid.SelectionMode = 'FullRowSelect'
$grid.AutoSizeColumnsMode = 'Fill'
foreach ($columnName in @('Lot ID', 'Ingredient', 'Class', 'On Hand', 'Unit', 'Level', 'Acquired', 'Expires')) {
    [void]$grid.Columns.Add(($columnName -replace ' ', ''), $columnName)
}
$grid.Columns['LotID'].Visible = $false
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
$addButton.Text = 'Add / Update'
$addButton.Location = New-Object System.Drawing.Point(145, 585)
$addButton.Size = New-Object System.Drawing.Size(130, 38)
$form.Controls.Add($addButton)

$removeButton = New-Object System.Windows.Forms.Button
$removeButton.Text = 'Remove'
$removeButton.Location = New-Object System.Drawing.Point(290, 585)
$removeButton.Size = New-Object System.Drawing.Size(110, 38)
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
    $expiresPicker.Enabled = $item.class -eq 'refrigerated'
    if ($item.class -in @('frozen', 'fresh-produce') -and -not $acquiredPicker.Checked) {
        $acquiredPicker.Checked = $true
        $acquiredPicker.Value = Get-Date
    }
    if ($item.class -eq 'refrigerated' -and -not $expiresPicker.Checked) {
        $expiresPicker.Checked = $true
        $expiresPicker.Value = (Get-Date).AddDays(7)
    }
    $behaviorLabel.Text = "$($item.class): $($catalogDocument.classes.($item.class))"
}

function Refresh-Grid {
    $grid.Rows.Clear()
    $ordered = @($script:lots | Sort-Object item_id, acquired_on)
    foreach ($lot in $ordered) {
        if (-not $catalogById.ContainsKey($lot.item_id)) {
            continue
        }
        $item = $catalogById[$lot.item_id]
        $quantityText = if ($null -ne $lot.quantity) { [string]$lot.quantity } else { '' }
        $levelText = if ($null -ne $lot.level) { [string]$lot.level } else { '' }
        [void]$grid.Rows.Add(
            $lot.lot_id,
            $item.name,
            $item.class,
            $quantityText,
            $item.unit,
            $levelText,
            [string]$lot.acquired_on,
            [string]$lot.expires_on
        )
    }
    $statusLabel.Text = "$($script:lots.Count) inventory lot(s). Unsaved changes remain until Save Inventory is clicked."
}

function Reset-Editor {
    $script:editingLotId = $null
    $quantity.Value = 0
    $levelCombo.SelectedIndex = 0
    $acquiredPicker.Checked = $false
    $expiresPicker.Checked = $false
    $grid.ClearSelection()
    Refresh-Editor
}

$ingredientCombo.Add_SelectedIndexChanged({ Refresh-Editor })
$newButton.Add_Click({ Reset-Editor })

$grid.Add_SelectionChanged({
    if ($grid.SelectedRows.Count -ne 1) {
        return
    }
    $lotId = [string]$grid.SelectedRows[0].Cells['LotID'].Value
    $lot = $script:lots | Where-Object { $_.lot_id -eq $lotId } | Select-Object -First 1
    if ($null -eq $lot) {
        return
    }
    $script:editingLotId = $lotId
    for ($index = 0; $index -lt $ingredientCombo.Items.Count; $index++) {
        if ($ingredientCombo.Items[$index].id -eq $lot.item_id) {
            $ingredientCombo.SelectedIndex = $index
            break
        }
    }
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
Refresh-Editor
Refresh-Grid
[void]$form.ShowDialog()
