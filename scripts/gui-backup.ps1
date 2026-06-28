Set-StrictMode -Version Latest

function Get-MealPlannerRelativePath {
    param(
        [string]$Root,
        [string]$Path
    )

    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith(
        $rootPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Backup path is outside the project root: $fullPath"
    }
    $rootUri = New-Object System.Uri($rootPath)
    $pathUri = New-Object System.Uri($fullPath)
    return [System.Uri]::UnescapeDataString(
        $rootUri.MakeRelativeUri($pathUri).ToString()
    ).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function New-MealPlannerGuiBackup {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [Parameter(Mandatory = $true)]
        [string]$Operation,
        [string[]]$Paths = @(
            'recipes',
            'inventory',
            'menus',
            'grocery-lists',
            'email-outputs',
            'overrides',
            'ideas',
            'feedback',
            'preferences'
        )
    )

    $resolvedRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
    $backupRoot = Join-Path $resolvedRoot '.backup'
    [System.IO.Directory]::CreateDirectory($backupRoot) | Out-Null
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = Join-Path $backupRoot $timestamp
    $suffix = 1
    while (Test-Path -LiteralPath $backupPath) {
        $backupPath = Join-Path $backupRoot (
            '{0}-{1:D2}' -f $timestamp, $suffix
        )
        $suffix++
    }
    [System.IO.Directory]::CreateDirectory($backupPath) | Out-Null

    $entries = New-Object System.Collections.ArrayList
    $fileCount = 0
    foreach ($path in $Paths) {
        $source = if ([System.IO.Path]::IsPathRooted($path)) {
            [System.IO.Path]::GetFullPath($path)
        } else {
            [System.IO.Path]::GetFullPath((Join-Path $resolvedRoot $path))
        }
        $relative = Get-MealPlannerRelativePath `
            -Root $resolvedRoot `
            -Path $source
        $exists = Test-Path -LiteralPath $source
        $isDirectory = $exists -and (
            Get-Item -LiteralPath $source
        ).PSIsContainer
        [void]$entries.Add([ordered]@{
            path = $relative.Replace('\', '/')
            existed = $exists
            type = if (-not $exists) {
                'missing'
            } elseif ($isDirectory) {
                'directory'
            } else {
                'file'
            }
        })
        if (-not $exists) {
            continue
        }
        if ($isDirectory) {
            foreach ($file in Get-ChildItem -LiteralPath $source -File -Recurse) {
                $fileRelative = Get-MealPlannerRelativePath `
                    -Root $resolvedRoot `
                    -Path $file.FullName
                $target = Join-Path $backupPath $fileRelative
                [System.IO.Directory]::CreateDirectory(
                    (Split-Path -Parent $target)
                ) | Out-Null
                [System.IO.File]::Copy($file.FullName, $target, $true)
                $fileCount++
            }
        } else {
            $target = Join-Path $backupPath $relative
            [System.IO.Directory]::CreateDirectory(
                (Split-Path -Parent $target)
            ) | Out-Null
            [System.IO.File]::Copy($source, $target, $true)
            $fileCount++
        }
    }

    $manifest = [ordered]@{
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString('o')
        operation = $Operation
        project_root = $resolvedRoot
        file_count = $fileCount
        paths = @($entries)
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $backupPath 'manifest.json'),
        ($manifest | ConvertTo-Json -Depth 5) + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
    return $backupPath
}
