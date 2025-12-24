# PowerShell script to install Pulse Launcher Service
# Run as Administrator

param(
    [string]$ServicePath = "",
    [string]$ServiceName = "PulseLauncherService",
    [string]$DisplayName = "Pulse Launcher Service",
    [string]$Description = "Ensures PulseForm.exe is running. Signals user session launcher every 10 minutes."
)

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Get service executable path
if ([string]::IsNullOrEmpty($ServicePath)) {
    # First, try current directory (where PulseForm.exe might be)
    $currentDirPath = Join-Path $PWD "PulseLauncherService.exe"
    if (Test-Path $currentDirPath) {
        $ServicePath = $currentDirPath
    } else {
        # Fall back to build output directory
        $ServicePath = Join-Path $PSScriptRoot "PulseLauncherService\bin\Release\net8.0-windows\PulseLauncherService.exe"
    }
}

if (-not (Test-Path $ServicePath)) {
    Write-Host "ERROR: Service executable not found at: $ServicePath" -ForegroundColor Red
    Write-Host "Please build the service first using: dotnet build -c Release" -ForegroundColor Yellow
    Write-Host "Or copy PulseLauncherService.exe to the current directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing Pulse Launcher Service..." -ForegroundColor Green
Write-Host "Service Path: $ServicePath" -ForegroundColor Cyan

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service already exists. Stopping and removing..." -ForegroundColor Yellow
    if ($existingService.Status -eq 'Running') {
        Stop-Service -Name $ServiceName -Force
    }
    sc.exe delete $ServiceName
    Start-Sleep -Seconds 2
}

# Install the service
Write-Host "Creating service..." -ForegroundColor Cyan
$service = New-Service -Name $ServiceName `
    -BinaryPathName "`"$ServicePath`"" `
    -DisplayName $DisplayName `
    -Description $Description `
    -StartupType Automatic

if ($service) {
    Write-Host "Service created successfully" -ForegroundColor Green
    
    # Configure service recovery
    Write-Host "Configuring service recovery..." -ForegroundColor Cyan
    sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/60000
    
    # Start the service
    Write-Host "Starting service..." -ForegroundColor Cyan
    Start-Service -Name $ServiceName
    
    Write-Host "`nService installed and started successfully!" -ForegroundColor Green
    Write-Host "Service Name: $ServiceName" -ForegroundColor Cyan
    Write-Host "Display Name: $DisplayName" -ForegroundColor Cyan
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "1. Install the User Session Launcher via Task Scheduler (see InstallUserLauncher.ps1)" -ForegroundColor White
    Write-Host "2. Check Event Viewer -> Windows Logs -> Application for service logs" -ForegroundColor White
} else {
    Write-Host "ERROR: Failed to create service" -ForegroundColor Red
    exit 1
}

