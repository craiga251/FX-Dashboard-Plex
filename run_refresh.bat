@echo off
SETLOCAL

REM ─────────────────────────────────────────────
REM  FX Intelligence Dashboard - Refresh Runner
REM  Run this manually or via Task Scheduler
REM ─────────────────────────────────────────────

REM Use the folder this batch file lives in
SET "PROJECT_DIR=%~dp0"
SET "PYTHON_EXE=%PROJECT_DIR%..\.venv\Scripts\python.exe"

REM Keep refresh behavior controlled from this launcher
IF "%ANALYSIS_TIMEFRAME%"=="" SET "ANALYSIS_TIMEFRAME=1H / 4H focus, daily context"
IF "%CORE_PAIRS_TARGET%"=="" SET "CORE_PAIRS_TARGET=7"
IF "%GEMINI_MAX_OUTPUT_TOKENS%"=="" SET "GEMINI_MAX_OUTPUT_TOKENS=8192"
IF "%GEMINI_MAX_RETRIES%"=="" SET "GEMINI_MAX_RETRIES=3"

IF NOT EXIST "%PYTHON_EXE%" SET "PYTHON_EXE=python"

REM Prefer a system/user environment variable. Fall back to PPLX_API_KEY for older setups.
IF "%GEMINI_API_KEY%"=="" IF NOT "%PPLX_API_KEY%"=="" SET "GEMINI_API_KEY=%PPLX_API_KEY%"

IF "%GEMINI_API_KEY%"=="" (
    echo [%DATE% %TIME%] ERROR: GEMINI_API_KEY is not set.
    echo Set it in your environment before running this script.
    exit /b 1
)

REM ─────────────────────────────────────────────
cd /d "%PROJECT_DIR%"

echo [%DATE% %TIME%] Starting FX Dashboard refresh...
echo [%DATE% %TIME%] Macro themes: rebuilding top 5 cards from Gemini prompt...
echo [%DATE% %TIME%] Core pairs target: %CORE_PAIRS_TARGET%
echo [%DATE% %TIME%] Model max output tokens: %GEMINI_MAX_OUTPUT_TOKENS%
echo [%DATE% %TIME%] Model retries: %GEMINI_MAX_RETRIES%

REM Ensure dependencies are installed into the same interpreter used below
echo [%DATE% %TIME%] Installing/updating Python dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt >nul
IF ERRORLEVEL 1 (
    echo [%DATE% %TIME%] ERROR: Failed to install requirements. Aborting.
    exit /b 1
)

REM Step 1 — Pull fresh rates and regenerate analysis JSON
echo [%DATE% %TIME%] Running refresh_core_pairs.py...
"%PYTHON_EXE%" refresh_core_pairs.py
IF ERRORLEVEL 1 (
    echo [%DATE% %TIME%] ERROR: refresh_core_pairs.py failed. Aborting.
    exit /b 1
)

REM Step 2 — Inject new analysis into dashboard HTML
echo [%DATE% %TIME%] Running update_dashboard_html.py...
"%PYTHON_EXE%" update_dashboard_html.py
IF ERRORLEVEL 1 (
    echo [%DATE% %TIME%] ERROR: update_dashboard_html.py failed. Aborting.
    exit /b 1
)

echo [%DATE% %TIME%] Dashboard refresh complete.
echo [%DATE% %TIME%] Output: %PROJECT_DIR%\dashboard_generated.html

REM Optional — open the dashboard in your default browser after refresh
REM Uncomment the line below if you want this behaviour
REM start "" "%PROJECT_DIR%\dashboard_generated.html"

ENDLOCAL
