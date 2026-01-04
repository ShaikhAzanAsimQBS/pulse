using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.EventLog;
using PulseLauncherService;

var builder = Host.CreateApplicationBuilder(args);

// Use Windows Service hosting
builder.Services.AddWindowsService(options =>
{
    options.ServiceName = "PulseLauncherService";
});

// Configure Event Log logging
builder.Services.AddLogging(logging =>
{
    logging.ClearProviders();
    
    // Create Event Log source if it doesn't exist (service runs as LocalSystem, has permission)
    try
    {
        if (!System.Diagnostics.EventLog.SourceExists("PulseLauncherService"))
        {
            System.Diagnostics.EventLog.CreateEventSource("PulseLauncherService", "Application");
        }
    }
    catch
    {
        // If creation fails, EventLog provider will handle it
    }
    
    logging.AddEventLog(settings =>
    {
        settings.SourceName = "PulseLauncherService";
        settings.LogName = "Application";
    });
    
    logging.SetMinimumLevel(LogLevel.Information);
});

// Add the worker service
builder.Services.AddHostedService<Worker>();

// Build and run
var host = builder.Build();

try
{
    host.Run();
}
catch (Exception ex)
{
    // Try to log, but if logging fails, at least we tried
    try
    {
        var logger = host.Services.GetRequiredService<ILogger<Program>>();
        logger.LogCritical(ex, "Service failed to start");
    }
    catch
    {
        // If logging fails, write to a file as last resort
        try
        {
            var logPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "PulseLauncherService", "startup_error.log");
            Directory.CreateDirectory(Path.GetDirectoryName(logPath)!);
            File.WriteAllText(logPath, $"{DateTime.Now}: Service failed to start: {ex}");
        }
        catch { }
    }
    throw;
}

