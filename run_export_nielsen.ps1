$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\Daniel.GHELLER\AppData\Local\Programs\Python\Python312\python.exe"
& $Python "$ScriptDir\export_nielsen.py" `
  --properties "$ScriptDir\jobExportNielsen.properties" `
  --base-dir "$ScriptDir"
