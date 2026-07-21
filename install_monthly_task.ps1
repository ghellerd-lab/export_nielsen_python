param(
    [string]$TaskName = "Export Nielsen - luna precedenta",
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time = "03:00",
    [string]$RunAs = "SYSTEM"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ScriptDir "run_export_nielsen.ps1"
$Properties = Join-Path $ScriptDir "jobExportNielsen.properties"

if (-not (Test-Path -LiteralPath $Runner)) { throw "Lipseste $Runner" }
if (-not (Test-Path -LiteralPath $Properties)) { throw "Lipseste $Properties" }

$LastMonthLine = Get-Content -LiteralPath $Properties |
    Where-Object { $_ -match '^\s*last_month\s*=\s*y\s*$' }
if (-not $LastMonthLine) {
    throw "Taskul lunar necesita last_month=y in jobExportNielsen.properties"
}

$TaskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Arguments = @(
    "/Create", "/F",
    "/TN", $TaskName,
    "/TR", $TaskCommand,
    "/SC", "MONTHLY",
    "/MO", "FIRST",
    "/D", "MON",
    "/ST", $Time,
    "/RU", $RunAs,
    "/RL", "HIGHEST"
)

& schtasks.exe @Arguments
if ($LASTEXITCODE -ne 0) { throw "Crearea taskului a esuat cu exit code $LASTEXITCODE" }

Write-Host "Task instalat: $TaskName - prima luni din luna la $Time, cont $RunAs"
