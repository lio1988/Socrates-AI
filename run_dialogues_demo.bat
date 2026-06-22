@echo off
REM ===================================================================
REM  Socratic Dialogues demo (Phase 4) - double-click to run.
REM
REM  Double-click in Explorer for the default question, or from a
REM  terminal pass your own:
REM      run_dialogues_demo.bat "Is mathematics discovered or invented?"
REM ===================================================================
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"

REM Run from this script's own folder so the package import works.
cd /d "%~dp0"

REM Prefer the project virtualenv; fall back to system python.
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" (
    "%PY%" -m backend.dialogues.demo
) else (
    "%PY%" -m backend.dialogues.demo "%~1"
)

echo.
echo ----------------------------------------------------------------
echo  Demo finished. Press any key to close this window.
pause >nul
endlocal
