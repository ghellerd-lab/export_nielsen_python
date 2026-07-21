param(
    [string]$JobAccount = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Restrang accesul la: $JobAccount, Administrators si SYSTEM"

& icacls $ScriptDir /grant:r "${JobAccount}:(OI)(CI)M" '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' /T /C
if ($LASTEXITCODE -ne 0) { throw "Nu am putut acorda drepturile necesare." }

& icacls $ScriptDir /inheritance:r /T /C
if ($LASTEXITCODE -ne 0) { throw "Nu am putut dezactiva mostenirea ACL." }

& icacls $ScriptDir /remove:g '*S-1-1-0' /T /C
if ($LASTEXITCODE -ne 0) { throw "Nu am putut elimina grupul Everyone din ACL." }

Write-Host "Drepturile au fost actualizate cu succes."
