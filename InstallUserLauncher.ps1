# PowerShell script to install User Session Launcher via Task Scheduler
# Run as Administrator (for Task Scheduler access)

param(
    [string]$LauncherPath = "",
    [string]$TaskName = "PulseUserLauncher"
)

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Get launcher executable path
if ([string]::IsNullOrEmpty($LauncherPath)) {
    # First, try current directory (where PulseForm.exe might be)
    $currentDirPath = Join-Path $PWD "PulseUserLauncher.exe"
    if (Test-Path $currentDirPath) {
        $LauncherPath = $currentDirPath
    } else {
        # Fall back to build output directory
        $LauncherPath = Join-Path $PSScriptRoot "PulseUserLauncher\bin\Release\net8.0-windows\PulseUserLauncher.exe"
    }
}

if (-not (Test-Path $LauncherPath)) {
    Write-Host "ERROR: Launcher executable not found at: $LauncherPath" -ForegroundColor Red
    Write-Host "Please build the launcher first using: dotnet build -c Release" -ForegroundColor Yellow
    Write-Host "Or copy PulseUserLauncher.exe to the current directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing User Session Launcher via Task Scheduler..." -ForegroundColor Green
Write-Host "Launcher Path: $LauncherPath" -ForegroundColor Cyan

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action
$action = New-ScheduledTaskAction -Execute $LauncherPath

# Create trigger: At user logon
$trigger1 = New-ScheduledTaskTrigger -AtLogOn

# Create trigger: On system resume from sleep (Power-Troubleshooter Event ID 1)
# This requires using XML since PowerShell doesn't have direct support for event triggers
$trigger2Xml = @"
<QueryList>
  <Query Id="0" Path="System">
    <Select Path="System">
      *[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]
    </Select>
  </Query>
</QueryList>
"@

# Create principal (run as current user)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# Register the task
Write-Host "Creating scheduled task..." -ForegroundColor Cyan
$task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger1 `
    -Principal $principal `
    -Settings $settings `
    -Description "Launches PulseForm.exe in user session. Listens for signals from Pulse Launcher Service."

if ($task) {
    Write-Host "Task created successfully" -ForegroundColor Green
    
    # Add event-based trigger for sleep resume (requires XML modification)
    Write-Host "Adding sleep/resume trigger..." -ForegroundColor Cyan
    try {
        # Export task to XML
        $taskXml = [xml](Export-ScheduledTask -TaskName $TaskName)
        
        # Add event trigger
        $ns = New-Object System.Xml.XmlNamespaceManager($taskXml.NameTable)
        $ns.AddNamespace("ns", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        
        $triggersNode = $taskXml.SelectSingleNode("//ns:Triggers", $ns)
        
        $eventTrigger = $taskXml.CreateElement("EventTrigger", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $eventTrigger.SetAttribute("xmlns", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        
        $enabled = $taskXml.CreateElement("Enabled", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $enabled.InnerText = "true"
        $eventTrigger.AppendChild($enabled) | Out-Null
        
        $subscription = $taskXml.CreateElement("Subscription", "http://schemas.microsoft.com/windows/2004/02/mit/task")
        $subscription.InnerText = $trigger2Xml
        $eventTrigger.AppendChild($subscription) | Out-Null
        
        $triggersNode.AppendChild($eventTrigger) | Out-Null
        
        # Re-import task
        Register-ScheduledTask -TaskName $TaskName -Xml $taskXml.OuterXml -Force | Out-Null
        Write-Host "Sleep/resume trigger added successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "Warning: Could not add sleep/resume trigger: $_" -ForegroundColor Yellow
        Write-Host "You can manually add it via Task Scheduler GUI" -ForegroundColor Yellow
    }
    
    Write-Host "`nUser Session Launcher installed successfully!" -ForegroundColor Green
    Write-Host "Task Name: $TaskName" -ForegroundColor Cyan
    Write-Host "`nThe launcher will:" -ForegroundColor Yellow
    Write-Host "- Start automatically when user logs on" -ForegroundColor White
    Write-Host "- Restart automatically if it crashes" -ForegroundColor White
    Write-Host "- Launch PulseForm.exe when signaled by the service" -ForegroundColor White
    Write-Host "`nCheck log file: C:\Pulse\settings\user_launcher.log" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    exit 1
}

