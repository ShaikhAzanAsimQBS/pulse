# Deployment Package - What to Send

For a laptop **without Python or .NET installed**, you need to send these files:

## Required Files

### 1. Main Application
- `PulseForm.exe` - Your main application

### 2. Launcher Service Components
- `PulseLauncherService.exe` - Windows Service (self-contained, includes .NET runtime)
- `PulseUserLauncher.exe` - User Session Launcher (self-contained, includes .NET runtime)

### 3. Installation Scripts
- `InstallService.ps1` - Install the Windows Service
- `InstallUserLauncher.ps1` - Install the User Session Launcher
- `UninstallService.ps1` - Uninstall everything (optional, for cleanup)
- `RegisterEventLogSource.ps1` - Register Event Log source (optional, script handles this)

### 4. Documentation (Optional but Recommended)
- `README_LAUNCHER_SERVICE.md` - Full documentation
- `QUICK_START.md` - Quick start guide
- `MIGRATION_GUIDE.md` - Migration guide


```

## Installation on Target Laptop

1. Copy all files to a folder on the laptop (e.g., `C:\Pulse\` or `C:\Programs\Pulse\`)

2. **Run as Administrator:**
   ```powershell
   cd "C:\Path\To\Files"
   .\InstallService.ps1
   .\InstallUserLauncher.ps1
   ```

3. Verify installation:
   ```powershell
   Get-Service PulseLauncherService
   Get-ScheduledTask -TaskName PulseUserLauncher
   ```

## What You DON'T Need

- ❌ Python (not needed - PulseForm.exe is already compiled)
- ❌ .NET SDK (not needed - executables are self-contained)
- ❌ .NET Runtime (not needed - executables are self-contained)
- ❌ Any dependencies (everything is bundled)

## Notes

- All executables are **self-contained** (include .NET runtime)
- All executables are **single-file** (no DLL dependencies to manage)
- Works on Windows 10/11 **without any prerequisites**
- File sizes will be larger (~70-80MB each) but completely portable

