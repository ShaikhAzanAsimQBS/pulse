# PowerShell script to uninstall Pulse Launcher Service
# Run as Administrator

param(
    [string]$ServiceName = "PulseLauncherService",
    [string]$TaskName = "PulseUserLauncher"
)

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

Write-Host "Uninstalling Pulse Launcher components..." -ForegroundColor Yellow

# Stop and remove service
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "Stopping service..." -ForegroundColor Cyan
    if ($service.Status -eq 'Running') {
        Stop-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 2
    }
    
    Write-Host "Removing service..." -ForegroundColor Cyan
    sc.exe delete $ServiceName
    Write-Host "Service removed" -ForegroundColor Green
} else {
    Write-Host "Service not found" -ForegroundColor Gray
}

# Remove scheduled task
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "Removing scheduled task..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Scheduled task removed" -ForegroundColor Green
} else {
    Write-Host "Scheduled task not found" -ForegroundColor Gray
}

Write-Host "`nUninstallation complete!" -ForegroundColor Green

