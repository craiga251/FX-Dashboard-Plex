@echo off
SETLOCAL

REM ─────────────────────────────────────────────
REM  FX Intelligence Dashboard - Refresh Runner
REM  Run this manually or via Task Scheduler
REM ─────────────────────────────────────────────

REM Set your project folder path here
SET PROJECT_DIR=C:\fx-dashboard-automation

REM Set your Perplexity API key here (or set it as a system env variable)
SET GEMINI_API_KEY=your_perplexity_api_key_here

REM ─────────────────────────────────────────────
cd /d "%PROJECT_DIR%"

echo [%DATE% %TIME%] Starting FX Dashboard refresh...

REM Step 1 — Pull fresh rates and regenerate analysis JSON
echo [%DATE% %TIME%] Running refresh_core_pairs.py...
python refresh_core_pairs.py
IF ERRORLEVEL 1 (
    echo [%DATE% %TIME%] ERROR: refresh_core_pairs.py failed. Aborting.
    exit /b 1
)

REM Step 2 — Inject new analysis into dashboard HTML
echo [%DATE% %TIME%] Running update_dashboard_html.py...
python update_dashboard_html.py
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
