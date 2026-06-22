# Run the Socratic Dialogues demo (Phase 4) with the project's virtualenv.
#
# Usage:
#   .\run_dialogues_demo.ps1
#   .\run_dialogues_demo.ps1 "Is mathematics discovered or invented?"
#
# Pass an optional question as the first argument; otherwise a default is used.

param(
    [string]$Question = ""
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "venv python not found at $py — falling back to system 'python'." -ForegroundColor Yellow
    $py = "python"
}

Push-Location $root
try {
    if ([string]::IsNullOrWhiteSpace($Question)) {
        & $py -m backend.dialogues.demo
    } else {
        & $py -m backend.dialogues.demo $Question
    }
}
finally {
    Pop-Location
}
