param(
    [Parameter(Mandatory = $true)]
    [string]$PlannerScript,
    [Parameter(Mandatory = $true)]
    [string]$ProposalJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $PlannerScript,
    [ref]$tokens,
    [ref]$parseErrors
)
if (@($parseErrors).Count -gt 0) {
    throw ($parseErrors -join [Environment]::NewLine)
}
$functionAst = $ast.Find(
    {
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Format-Proposal'
    },
    $true
)
if ($null -eq $functionAst) {
    throw 'Format-Proposal was not found.'
}
Invoke-Expression $functionAst.Extent.Text

$proposal = Get-Content -LiteralPath $ProposalJson -Raw | ConvertFrom-Json
$report = Format-Proposal -Proposal $proposal -Number 1
if ($report -notmatch 'PLANNING TRACE') {
    throw 'Planning trace was not rendered.'
}
if ($report -notmatch 'Rejected -') {
    throw 'Candidate rejection reasons were not rendered.'
}
if ($report -notmatch '\(sorted\)') {
    throw 'Sorted planning stages were not rendered.'
}
