# Pulse Launcher Service Architecture

This replaces the Python-based `auto_launcher.py` with a robust C# .NET solution that Windows won't kill.

## Architecture Overview

### Component 1: Windows Service (`PulseLauncherService`)
- **Type**: C# .NET 8.0 Worker Service
- **Runs**: System startup (before user login)
- **UI**: None (headless service)
- **Responsibilities**:
  - Starts automatically on boot
  - Signals user-session launcher every 10 minutes
  - Logs to Windows Event Viewer
  - Uses Windows Service Recovery (auto-restart on failure)

### Component 2: User Session Launcher (`PulseUserLauncher`)
- **Type**: C# .NET 8.0 Console Application (hidden)
- **Runs**: User session (after login)
- **UI**: None (hidden console)
- **How it starts**: Task Scheduler (at user logon + on sleep resume)
- **Responsibilities**:
  - Listens for signals from the service via named pipe
  - Checks if `PulseForm.exe` is running
  - Launches `PulseForm.exe` if not running
  - Auto-restarts if it crashes (via Task Scheduler)

## How It Works

### The 10-Minute Cycle

1. **Service** runs a timer every 10 minutes
2. **Service** sends a signal to **User Launcher** via named pipe
3. **User Launcher** receives signal
4. **User Launcher** checks: Is `PulseForm.exe` running?
5. If **NO** → Launches `PulseForm.exe`
6. If **YES** → Does nothing

### Sleep/Hibernate Handling

- Task Scheduler trigger: **On system resume from sleep**
- Event: `System` log, Source: `Power-Troubleshooter`, Event ID: `1`
- When system wakes, launcher runs immediately
- Checks and launches `PulseForm.exe` if needed

### Crash Recovery

**Service Recovery** (configured automatically):
- First failure → Restart service (after 1 minute)
- Second failure → Restart service (after 1 minute)
- Subsequent failures → Restart service (after 1 minute)
- Reset fail count after 1 day

**User Launcher Recovery** (via Task Scheduler):
- Configured to restart up to 3 times if it crashes
- Restart interval: 1 minute

## Building

### Prerequisites
- .NET 8.0 SDK (or later)
- Visual Studio 2022 or VS Code with C# extension

### Build Commands

```powershell
# Build both projects in Release mode
dotnet build -c Release

# Or build individually
cd PulseLauncherService
dotnet build -c Release

cd ..\PulseUserLauncher
dotnet build -c Release
```

### Output Locations
- Service: `PulseLauncherService\bin\Release\net8.0-windows\PulseLauncherService.exe`
- Launcher: `PulseUserLauncher\bin\Release\net8.0-windows\PulseUserLauncher.exe`

## Installation

### Step 1: Install the Windows Service

**Run as Administrator:**
```powershell
.\InstallService.ps1
```

This will:
- Install the service
- Configure service recovery
- Start the service
- Set it to start automatically on boot

### Step 2: Install the User Session Launcher

**Run as Administrator:**
```powershell
.\InstallUserLauncher.ps1
```

This will:
- Create a Task Scheduler task
- Configure it to run at user logon
- Add sleep/resume trigger
- Set auto-restart on crash

### Manual Installation (Alternative)

#### Service Installation
```powershell
# As Administrator
sc.exe create PulseLauncherService binPath= "C:\Path\To\PulseLauncherService.exe" start= auto
sc.exe description PulseLauncherService "Ensures PulseForm.exe is running. Signals user session launcher every 10 minutes."
sc.exe failure PulseLauncherService reset= 86400 actions= restart/60000/restart/60000/restart/60000
sc.exe start PulseLauncherService
```

#### Task Scheduler Setup
1. Open Task Scheduler
2. Create Basic Task
3. Name: `PulseUserLauncher`
4. Trigger: "When I log on"
5. Action: Start a program → `PulseUserLauncher.exe`
6. Settings:
   - ✅ Allow task to be run on demand
   - ✅ Run task as soon as possible after a scheduled start is missed
   - ✅ If the task fails, restart every: 1 minute (up to 3 times)

#### Sleep/Resume Trigger (Manual)
1. In Task Scheduler, edit the task
2. Triggers tab → New
3. Begin the task: "On an event"
4. Settings:
   - Log: `System`
   - Source: `Microsoft-Windows-Power-Troubleshooter`
   - Event ID: `1`

## Uninstallation

**Run as Administrator:**
```powershell
.\UninstallService.ps1
```

Or manually:
```powershell
# Stop and remove service
sc.exe stop PulseLauncherService
sc.exe delete PulseLauncherService

# Remove scheduled task
Unregister-ScheduledTask -TaskName PulseUserLauncher -Confirm:$false
```

## Logging

### Service Logs
- **Location**: Windows Event Viewer
- **Path**: `Windows Logs` → `Application`
- **Source**: `PulseLauncherService`
- **View**: `eventvwr.msc`

### User Launcher Logs
- **Location**: `C:\Pulse\settings\user_launcher.log`
- **Format**: `[YYYY-MM-DD HH:MM:SS] message`

## Troubleshooting

### Service Not Starting
1. Check Event Viewer for errors
2. Verify service executable path is correct
3. Ensure service account has permissions
4. Check if port/pipe is already in use

### User Launcher Not Running
1. Check Task Scheduler → Task Status
2. Check log file: `C:\Pulse\settings\user_launcher.log`
3. Verify `PulseForm.exe` exists in same directory
4. Manually run `PulseUserLauncher.exe` to test

### PulseForm.exe Not Launching
1. Check user launcher log file
2. Verify `PulseForm.exe` path is correct
3. Check Windows Defender/Antivirus isn't blocking
4. Verify user has permissions to launch executables

### Named Pipe Connection Issues
- Service and launcher use named pipe: `PulseLauncherServicePipe`
- If launcher isn't running, service will log warnings (this is normal)
- Launcher must be running in user session for signals to work

## Why This Solution?

### ✅ Advantages Over Python
- **No AV false positives**: Native .NET executables are trusted
- **Stable services**: .NET Worker Services are designed for Windows
- **Better integration**: Native Windows Service support
- **No dependency hell**: Self-contained executables
- **Event Viewer logging**: Built-in Windows logging
- **Service Recovery**: Native Windows feature

### ❌ Why Not Python?
- PyInstaller executables trigger antivirus
- Python services are unreliable on Windows
- Dependency management issues
- Windows kills Python processes more aggressively

## File Structure

```
pulse/
├── PulseLauncherService/
│   ├── PulseLauncherService.csproj
│   ├── Program.cs
│   └── Worker.cs
├── PulseUserLauncher/
│   ├── PulseUserLauncher.csproj
│   ├── Program.cs
│   └── app.manifest
├── InstallService.ps1
├── InstallUserLauncher.ps1
├── UninstallService.ps1
└── README_LAUNCHER_SERVICE.md
```

## Notes

- Both executables must be in the same directory as `PulseForm.exe`
- Service runs as `LocalSystem` (no user interaction)
- User launcher runs as logged-in user (can launch GUI apps)
- Named pipe communication is local-only (secure)
- Service recovery resets fail count after 24 hours

