# FX Intelligence Dashboard — Automation Bundle

Automatically refreshes the Core Pairs Dashboard analysis every 4 hours
on weekdays using the Perplexity Sonar API and live FX rates.

---

## Files in this bundle

| File | Purpose |
|---|---|
| `refresh_core_pairs.py` | Fetches live FX rates, calls Perplexity API, writes `core_pairs_latest.json` |
| `update_dashboard_html.py` | Reads JSON and injects Core Pairs cards into `dashboard_template.html` |
| `dashboard_template.html` | HTML dashboard layout with placeholders |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for environment variables |
| `run_refresh.bat` | Windows batch runner — runs both Python scripts in sequence |
| `setup_task_scheduler.ps1` | PowerShell script to register a Windows Task Scheduler job |
| `.github/workflows/fx_dashboard_refresh.yml` | GitHub Actions workflow for cloud-based scheduled refreshes |

---

## Quick start (Windows)

### 1. Create your project folder

mkdir C:\fx-dashboard-automation

Copy all files from this bundle into that folder.

### 2. Install Python dependencies

pip install -r requirements.txt


### 3. Set your Perplexity API key

Option A — Edit `run_refresh.bat` and replace:

SET PPLX_API_KEY=your_perplexity_api_key_here


Option B — Set it as a Windows system environment variable:

setx PPLX_API_KEY "your_key_here"


Get your API key from: https://www.perplexity.ai/settings/api

### 4. Run a manual refresh to test

cd C:\fx-dashboard-automation
run_refresh.bat


This will:
- Pull live FX rates from Frankfurter API
- Call Perplexity Sonar to regenerate Core Pairs analysis
- Write `core_pairs_latest.json`
- Build `dashboard_generated.html`

Open `dashboard_generated.html` in your browser to see the result.

### 5. Set up automatic scheduling (Windows Task Scheduler)

Open PowerShell as Administrator and run:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_task_scheduler.ps1
```

This registers a task called `FX-Dashboard-Refresh` that runs every
4 hours Mon–Fri from 07:05, logging output to `refresh.log`.

---

## Cloud scheduling (GitHub Actions)

1. Push this project to a GitHub repository.
2. Go to Settings → Secrets → Actions and add:
   - `PPLX_API_KEY` = your Perplexity API key
3. The workflow at `.github/workflows/fx_dashboard_refresh.yml` will
   run automatically at 07:05, 11:05, 15:05, and 19:05 UTC on weekdays.
4. Each run commits updated `core_pairs_latest.json` and
   `dashboard_generated.html` back to the repository.

---

## Refresh schedule

| What | How often | Method |
|---|---|---|
| Live FX prices | Every 5 min | Already built into dashboard page |
| Core Pairs analysis | Every 4 hours | This automation bundle |
| Forced refresh | On demand | Run `run_refresh.bat` manually |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing PPLX_API_KEY` error | Set the env variable or edit `run_refresh.bat` |
| `JSONDecodeError` | API returned unexpected format — retry; check model name in `.env` |
| `refresh_core_pairs.py` not found | Make sure you're running from the project folder |
| Task Scheduler not running | Check `refresh.log` for errors; verify Python is in system PATH |
