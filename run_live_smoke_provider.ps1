# Phase 9B - one-provider LIVE smoke test launcher (manual, opt-in).
# Never prints the API key. Never writes the key to disk.

if ($env:CED_ENABLE_LIVE_PROVIDERS -ne '1') {
    Write-Host '[live smoke] DISABLED (default safe mode). No network call made.'
    Write-Host '[live smoke] To enable: set $env:CED_ENABLE_LIVE_PROVIDERS=1 and $env:ANTHROPIC_API_KEY, then re-run.'
    exit 0
}
if ([string]::IsNullOrEmpty($env:ANTHROPIC_API_KEY)) {
    Write-Host '[live smoke] ERROR: ANTHROPIC_API_KEY is not set. Refusing to run. No network call made.'
    exit 2
}

Write-Host '[live smoke] Flag and key present. Running one-provider live smoke...'
$py = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
& $py scripts\live_smoke_provider.py
exit $LASTEXITCODE
