param(
    [string]$Properties = "",
    [string]$BaseDir = "",
    [switch]$DisableEventLog
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Properties) { $Properties = Join-Path $ScriptDir "jobExportNielsen.properties" }
if (-not $BaseDir) { $BaseDir = $ScriptDir }

$LogDir = Join-Path $BaseDir "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ("export_nielsen_{0}.log" -f (Get-Date -Format "yyyyMM"))
$Executable = Join-Path $ScriptDir "export_nielsen_sergiana.exe"

if (Test-Path -LiteralPath $Executable) {
    & $Executable --properties $Properties --base-dir $BaseDir 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    $ExitCode = $LASTEXITCODE
} else {
    $Python = "C:\Users\Daniel.GHELLER\AppData\Local\Programs\Python\Python312\python.exe"
    & $Python (Join-Path $ScriptDir "export_nielsen.py") --properties $Properties --base-dir $BaseDir 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    $ExitCode = $LASTEXITCODE
}

if ($ExitCode -ne 0) {
    $FailureMessage = "Export Nielsen esuat cu exit code $ExitCode. Log: $LogPath"
    $AlertPath = Join-Path $LogDir "export_nielsen_ALERTE.log"
    Add-Content -LiteralPath $AlertPath -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $FailureMessage)
    if (-not $DisableEventLog) {
        & eventcreate.exe /T ERROR /ID 100 /L APPLICATION /SO ExportNielsen /D $FailureMessage 2>$null
    }
    Write-Error $FailureMessage
}

exit $ExitCode
