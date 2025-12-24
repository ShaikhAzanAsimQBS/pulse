using System.Diagnostics;
using System.IO.Pipes;
using System.Security.Principal;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace PulseLauncherService;

public class Worker : BackgroundService
{
    private readonly ILogger<Worker> _logger;
    private readonly string _pipeName = "PulseLauncherServicePipe";
    private Timer? _timer;
    private DateTime _lastLaunchTime = DateTime.MinValue;

    public Worker(ILogger<Worker> logger)
    {
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Pulse Launcher Service started at: {time}", DateTimeOffset.Now);
        
        // Start timer to signal launcher every 10 minutes
        _timer = new Timer(async _ => await SignalUserLauncher(stoppingToken), null, 
            TimeSpan.Zero, TimeSpan.FromMinutes(10));

        // Keep service running
        while (!stoppingToken.IsCancellationRequested)
        {
            await Task.Delay(1000, stoppingToken);
        }
    }

    private async Task SignalUserLauncher(CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogDebug("Signaling user session launcher at {time}", DateTimeOffset.Now);
            
            // Try to connect to named pipe in user session
            using var pipeClient = new NamedPipeClientStream(
                ".", 
                _pipeName, 
                PipeDirection.Out, 
                PipeOptions.None, 
                TokenImpersonationLevel.Impersonate);

            try
            {
                // Try to connect with 2 second timeout
                await pipeClient.ConnectAsync(2000, cancellationToken);
                
                // Send signal
                byte[] signal = { 1 }; // Simple signal byte
                await pipeClient.WriteAsync(signal, cancellationToken);
                await pipeClient.FlushAsync(cancellationToken);
                
                _logger.LogInformation("Successfully signaled user session launcher");
                _lastLaunchTime = DateTime.Now;
            }
            catch (TimeoutException)
            {
                // This is normal if user hasn't logged in yet or launcher isn't running
                _logger.LogDebug("User session launcher not available (timeout connecting to pipe)");
            }
            catch (Exception ex)
            {
                // Log at debug level since this is expected when launcher isn't running
                _logger.LogDebug(ex, "Could not signal user session launcher (may not be running)");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error signaling user session launcher");
        }
    }

    public override void Stop()
    {
        _timer?.Dispose();
        _logger.LogInformation("Pulse Launcher Service stopped at: {time}", DateTimeOffset.Now);
        base.Stop();
    }

    public override void Dispose()
    {
        _timer?.Dispose();
        base.Dispose();
    }
}

