# Migration Guide: Python Launcher → C# Service

## Problem with Python Launcher

The original `auto_launcher.py` converted to `.exe` via PyInstaller had these issues:
- ❌ Windows Defender/Antivirus kills it (false positives)
- ❌ Unreliable as a Windows service
- ❌ Dependency management issues
- ❌ Process termination detection but no recovery

## Solution: C# .NET Architecture

### Component 1: Windows Service (`PulseLauncherService`)
- ✅ Native .NET Worker Service (Windows trusts it)
- ✅ Runs at system startup (before user login)
- ✅ Signals user launcher every 10 minutes via named pipe
- ✅ Logs to Windows Event Viewer
- ✅ Auto-restart on failure (Windows Service Recovery)

### Component 2: User Session Launcher (`PulseUserLauncher`)
- ✅ Native .NET console app (hidden)
- ✅ Runs in user session (via Task Scheduler)
- ✅ Listens for service signals
- ✅ Launches `PulseForm.exe` if not running
- ✅ Auto-restart on crash (Task Scheduler)

## Key Differences

| Feature | Python Launcher | C# Service |
|---------|----------------|------------|
| **AV Detection** | ❌ High (PyInstaller) | ✅ Low (Native .NET) |
| **Service Stability** | ❌ Unreliable | ✅ Native support |
| **Recovery** | ⚠️ Manual detection | ✅ Automatic (Windows) |
| **Logging** | File-based | Event Viewer + File |
| **Dependencies** | Many (Python runtime) | Self-contained |
| **Sleep Handling** | ❌ Timer pauses | ✅ Task Scheduler event |

## Migration Steps

### 1. Build the New Components

```powershell
.\BuildLauncher.ps1
```

### 2. Stop Old Python Launcher

```powershell
# If running as service
Stop-Service -Name "AutoLauncher" -ErrorAction SilentlyContinue

# If running as scheduled task
Unregister-ScheduledTask -TaskName "AutoLauncher" -Confirm:$false -ErrorAction SilentlyContinue

# Kill any running instances
Get-Process -Name "auto_launcher" -ErrorAction SilentlyContinue | Stop-Process -Force
```

### 3. Copy New Executables

Copy to same directory as `PulseForm.exe`:
- `PulseLauncherService.exe`
- `PulseUserLauncher.exe`

### 4. Install New Service

```powershell
# Run as Administrator
.\InstallService.ps1
.\InstallUserLauncher.ps1
```

### 5. Verify

```powershell
# Check service
Get-Service PulseLauncherService

# Check task
Get-ScheduledTask -TaskName PulseUserLauncher

# Check logs
Get-Content "C:\Pulse\settings\user_launcher.log" -Tail 20
```

## Architecture Comparison

### Old (Python)
```
auto_launcher.exe (PyInstaller)
  ├─ Runs in user session
  ├─ Checks every 10 minutes
  ├─ Launches PulseForm.exe
  └─ ❌ Gets killed by Windows
```

### New (C#)
```
PulseLauncherService.exe (Windows Service)
  ├─ Runs at system startup
  ├─ Signals every 10 minutes
  └─ ✅ Windows trusts it

PulseUserLauncher.exe (Task Scheduler)
  ├─ Runs at user logon
  ├─ Listens for signals
  ├─ Launches PulseForm.exe
  └─ ✅ Auto-restarts on crash
```

## Benefits

1. **No More AV Kills**: Native .NET executables are trusted
2. **True Service**: Uses Windows Service framework
3. **Automatic Recovery**: Windows handles restarts
4. **Better Logging**: Event Viewer integration
5. **Sleep Handling**: Task Scheduler event triggers
6. **Separation of Concerns**: Service vs User Session

## Rollback Plan

If you need to revert:

```powershell
# Uninstall new service
.\UninstallService.ps1

# Reinstall old Python launcher
# (your original installation method)
```

## Testing Checklist

- [ ] Service starts on boot
- [ ] Service signals launcher every 10 minutes
- [ ] Launcher receives signals (check log)
- [ ] PulseForm.exe launches when not running
- [ ] PulseForm.exe doesn't launch if already running
- [ ] Service auto-restarts after crash
- [ ] Launcher auto-restarts after crash
- [ ] Sleep/resume triggers launcher
- [ ] Event Viewer shows service logs
- [ ] No AV warnings

## Troubleshooting

### Service Not Starting
- Check Event Viewer → Application logs
- Verify .NET 8.0 Runtime installed
- Check service executable path

### Launcher Not Running
- Check Task Scheduler → Task Status
- Verify task is enabled
- Check log file for errors

### Signals Not Working
- Verify both service and launcher are running
- Check named pipe permissions
- Review Event Viewer logs

## Support

For issues:
1. Check Event Viewer (service logs)
2. Check `C:\Pulse\settings\user_launcher.log` (launcher logs)
3. Verify both executables are in same directory as `PulseForm.exe`
4. Ensure .NET 8.0 Runtime is installed

