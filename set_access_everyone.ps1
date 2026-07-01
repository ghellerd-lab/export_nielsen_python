$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

icacls $ScriptDir /grant '*S-1-1-0:(OI)(CI)M' /T /C
