using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.EventLog;
using PulseLauncherService;

var builder = Host.CreateApplicationBuilder(args);

// Configure Event Log logging
builder.Services.AddLogging(logging =>
{
    logging.ClearProviders();
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
    var logger = host.Services.GetRequiredService<ILogger<Program>>();
    logger.LogCritical(ex, "Service failed to start");
    throw;
}

