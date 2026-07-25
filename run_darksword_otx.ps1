# DARKSWORD — OTX Automated Run
# Invoked by Windows Task Scheduler to run the AlienVault OTX pipeline.
# Logs all output (stdout + stderr) to a dated file in the darksword folder.

$ScriptDir = "C:\Work\GRC\darksword"
$Python    = "C:\Work\GRC\.venv\Scripts\python.exe"
$LogDir    = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile   = Join-Path $LogDir "darksword_otx_$(Get-Date -Format 'yyyy-MM-dd').log"

function Write-Log ($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    $line | Out-File -FilePath $LogFile -Append -Encoding utf8NoBOM
    Write-Host $line
}

# Pre-flight checks — run before Write-Log can be used
if (-not (Test-Path $ScriptDir)) {
    $msg = "[$(Get-Date -Format 'HH:mm:ss')] FATAL: Script directory not found: $ScriptDir"
    Write-Host $msg
    $msg | Out-File -FilePath "$env:TEMP\darksword_preflight_error.log" -Append -Encoding utf8NoBOM
    exit 1
}
if (-not (Test-Path $Python)) {
    Write-Log "FATAL: Python executable not found: $Python"
    exit 1
}

Write-Log "=== DARKSWORD OTX auto-run starting ==="
Set-Location $ScriptDir

# Align PowerShell's pipe-read encoding with Python's UTF-8 output.
# $OutputEncoding controls how PS decodes external process stdout/stderr;
# without it PS uses the system codepage and garbles emoji before Out-File
# ever sees the bytes.
$env:PYTHONUNBUFFERED           = "1"
$env:PYTHONIOENCODING          = "utf-8"
$OutputEncoding                = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding      = [System.Text.Encoding]::UTF8

& $Python "notion_logger_v7.py" --auto-otx *>&1 | ForEach-Object {
    $_ | Out-File -FilePath $LogFile -Append -Encoding utf8NoBOM
    Write-Host $_
}

$ExitCode = $LASTEXITCODE
Write-Log "=== OTX auto-run finished — exit code: $ExitCode ==="

if ($ExitCode -ne 0) { exit $ExitCode }
