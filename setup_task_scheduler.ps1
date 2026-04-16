# ─────────────────────────────────────────────────────────────
#  FX Intelligence Dashboard — Windows Task Scheduler Setup
#  Run this script ONCE in PowerShell as Administrator
#  It creates a scheduled task that runs run_refresh.bat
#  once each weekday morning at 07:05
# ─────────────────────────────────────────────────────────────

$TaskName    = "FX-Dashboard-Refresh"
$ProjectDir  = "C:\fx-dashboard-automation"
$BatchFile   = "$ProjectDir\run_refresh.bat"
$LogFile     = "$ProjectDir\refresh.log"

# ── Trigger: once daily, Mon–Fri, at 07:05 ───────────────────
$trigger = New-ScheduledTaskTrigger `
    -At "07:05" `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

# ── Action: run the batch file and log output ─────────────────
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatchFile`" >> `"$LogFile`" 2>&1" `
    -WorkingDirectory $ProjectDir

# ── Settings ─────────────────────────────────────────────────
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

# ── Principal: run as current user ───────────────────────────
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# ── Register the task ─────────────────────────────────────────
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Description "Auto-refreshes FX Intelligence Core Pairs Dashboard each weekday morning" `
    -Force

Write-Host ""
Write-Host "Task '$TaskName' registered successfully." -ForegroundColor Green
Write-Host "It will run each weekday at 07:05, logging to:"
Write-Host "  $LogFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run it immediately: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove it:          Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
