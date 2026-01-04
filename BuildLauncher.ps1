# Build script for Pulse Launcher components
# Builds both the Windows Service and User Session Launcher

param(
    [string]$Configuration = "Release"
)

Write-Host "Building Pulse Launcher Components..." -ForegroundColor Green
Write-Host "Configuration: $Configuration" -ForegroundColor Cyan
Write-Host ""

# Check if .NET SDK is installed
try {
    $dotnetVersion = dotnet --version
    Write-Host "Using .NET SDK: $dotnetVersion" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: .NET SDK not found. Please install .NET 8.0 SDK or later." -ForegroundColor Red
    exit 1
}

# Build Service (as self-contained)
Write-Host "`n[1/2] Building PulseLauncherService (self-contained)..." -ForegroundColor Yellow
Push-Location "PulseLauncherService"
try {
    dotnet publish -c $Configuration -r win-x64 --self-contained true -p:PublishSingleFile=true
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Service build failed" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Write-Host "Service built successfully" -ForegroundColor Green
} finally {
    Pop-Location
}

# Build User Launcher (as self-contained)
Write-Host "`n[2/2] Building PulseUserLauncher (self-contained)..." -ForegroundColor Yellow
Push-Location "PulseUserLauncher"
try {
    dotnet publish -c $Configuration -r win-x64 --self-contained true -p:PublishSingleFile=true
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: User Launcher build failed" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Write-Host "User Launcher built successfully" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Write-Host "  Service:   PulseLauncherService\bin\$Configuration\net8.0-windows\win-x64\publish\PulseLauncherService.exe" -ForegroundColor White
Write-Host "  Launcher:  PulseUserLauncher\bin\$Configuration\net8.0-windows\win-x64\publish\PulseUserLauncher.exe" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy both .exe files to the same directory as PulseForm.exe" -ForegroundColor White
Write-Host "  2. Run InstallService.ps1 (as Administrator)" -ForegroundColor White
Write-Host "  3. Run InstallUserLauncher.ps1 (as Administrator)" -ForegroundColor White

