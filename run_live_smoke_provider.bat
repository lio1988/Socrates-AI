@echo off
chcp 65001 >nul
setlocal

REM Phase 9B - one-provider LIVE smoke test launcher (manual, opt-in).
REM Never echoes the API key. Never writes the key to disk.

if not "%CED_ENABLE_LIVE_PROVIDERS%"=="1" goto :disabled
if "%ANTHROPIC_API_KEY%"=="" goto :nokey

echo [live smoke] Flag and key present. Running one-provider live smoke...
if exist ".venv\Scripts\python.exe" goto :venv
python scripts\live_smoke_provider.py
goto :done

:venv
".venv\Scripts\python.exe" scripts\live_smoke_provider.py
goto :done

:disabled
echo [live smoke] DISABLED (default safe mode). No network call made.
echo [live smoke] To enable: set CED_ENABLE_LIVE_PROVIDERS=1 and ANTHROPIC_API_KEY, then re-run.
goto :done

:nokey
echo [live smoke] ERROR: ANTHROPIC_API_KEY is not set. Refusing to run. No network call made.
goto :done

:done
endlocal
