Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$iconRoot = Join-Path $projectRoot 'assets\icons'
$shell = New-Object -ComObject WScript.Shell
$launchers = @(
    @{
        Name = 'Family Meal Planner'
        Command = 'Meal Planner Suite.cmd'
        Icon = 'meal-planner-suite.ico'
        Description = 'Open the Family Meal Planner suite'
    },
    @{
        Name = 'Plan Week'
        Command = 'Plan Week.cmd'
        Icon = 'plan-week.ico'
        Description = 'Generate and compare weekly meal plans'
    },
    @{
        Name = 'Kitchen Inventory'
        Command = 'Kitchen Inventory.cmd'
        Icon = 'kitchen-inventory.ico'
        Description = 'Manage kitchen inventory'
    },
    @{
        Name = 'Import Recipe'
        Command = 'Import Recipe.cmd'
        Icon = 'import-recipe.ico'
        Description = 'Import and edit recipes'
    },
    @{
        Name = 'Review Meal'
        Command = 'Review Meal.cmd'
        Icon = 'review-meal.ico'
        Description = 'Review and rate family meals'
    },
    @{
        Name = 'Override Meal'
        Command = 'Override Meal.cmd'
        Icon = 'override-meal.ico'
        Description = 'Override a planned meal'
    }
)

foreach ($launcher in $launchers) {
    $shortcutPath = Join-Path $projectRoot "$($launcher.Name).lnk"
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $projectRoot $launcher.Command
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = (
        (Join-Path $iconRoot $launcher.Icon) + ',0'
    )
    $shortcut.Description = $launcher.Description
    $shortcut.WindowStyle = 1
    $shortcut.Save()
}

Write-Output "Created $($launchers.Count) meal-planner shortcuts."
