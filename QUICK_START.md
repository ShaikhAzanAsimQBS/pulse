# Quick Start Guide - Pulse Launcher Service

## Prerequisites
- .NET 8.0 SDK (download from https://dotnet.microsoft.com/download)
- Windows 10/11
- Administrator privileges

## Step 1: Build the Components

Open PowerShell in the project directory and run:

```powershell
.\BuildLauncher.ps1
```

This builds both:
- `PulseLauncherService.exe` (Windows Service)
- `PulseUserLauncher.exe` (User Session Launcher)

## Step 2: Copy Files

Copy both executables to the same directory as `PulseForm.exe`:

```powershell
# Example: If PulseForm.exe is in C:\Pulse\
Copy-Item "PulseLauncherService\bin\Release\net8.0-windows\PulseLauncherService.exe" -Destination "C:\Pulse\"
Copy-Item "PulseUserLauncher\bin\Release\net8.0-windows\PulseUserLauncher.exe" -Destination "C:\Pulse\"
```

## Step 3: Install the Service

**Right-click PowerShell → Run as Administrator**, then:

```powershell
cd C:\Pulse
.\InstallService.ps1
```

This installs and starts the Windows Service.

## Step 4: Install the User Launcher

**Still as Administrator:**

```powershell
.\InstallUserLauncher.ps1
```

This sets up Task Scheduler to run the launcher at user logon.

## Step 5: Verify Installation

### Check Service Status
```powershell
Get-Service PulseLauncherService
```

Should show: `Status: Running`

### Check Task Scheduler
```powershell
Get-ScheduledTask -TaskName PulseUserLauncher
```

Should show the task exists.

### Check Logs

**Service logs** (Event Viewer):
```powershell
eventvwr.msc
```
Navigate to: `Windows Logs` → `Application` → Filter by Source: `PulseLauncherService`

**User Launcher logs**:
```
C:\Pulse\settings\user_launcher.log
```

## Testing

1. **Test Service Signal**: Wait 10 minutes, check user launcher log for signal received
2. **Test Launch**: Kill `PulseForm.exe`, wait for next signal (or manually trigger), verify it launches
3. **Test Sleep Resume**: Put system to sleep, wake it, verify `PulseForm.exe` launches

## Uninstall

```powershell
.\UninstallService.ps1
```

## Troubleshooting

### Service won't start
- Check Event Viewer for errors
- Verify executable path in service properties
- Ensure .NET 8.0 Runtime is installed

### User Launcher not running
- Check Task Scheduler → Task Status
- Check log file: `C:\Pulse\settings\user_launcher.log`
- Manually run `PulseUserLauncher.exe` to test

### PulseForm.exe not launching
- Verify `PulseForm.exe` exists in same directory
- Check user launcher log for errors
- Verify antivirus isn't blocking

## Architecture Summary

```
┌─────────────────────────────────────┐
│  Windows Service                    │
│  (PulseLauncherService.exe)         │
│  - Runs at system startup           │
│  - Signals every 10 minutes         │
│  - Logs to Event Viewer             │
└──────────────┬──────────────────────┘
               │ Named Pipe Signal
               ▼
┌─────────────────────────────────────┐
│  User Session Launcher              │
│  (PulseUserLauncher.exe)            │
│  - Runs at user logon               │
│  - Listens for signals               │
│  - Launches PulseForm.exe            │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ PulseForm.exe│
        └──────────────┘
```

## Important Notes

- Both executables must be in the **same directory** as `PulseForm.exe`
- Service runs as `LocalSystem` (no UI)
- User Launcher runs as logged-in user (can launch GUI)
- Service recovery: Auto-restart on failure
- Task Scheduler: Auto-restart launcher if it crashes

