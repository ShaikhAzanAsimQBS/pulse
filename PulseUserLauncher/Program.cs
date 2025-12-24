using System.Diagnostics;
using System.IO.Pipes;
using System.Security.Principal;

namespace PulseUserLauncher;

class Program
{
    private static readonly string PipeName = "PulseLauncherServicePipe";
    private static readonly string PulseFormExe = "PulseForm.exe";
    private static readonly string LogFile = @"C:\Pulse\settings\user_launcher.log";
    private static NamedPipeServerStream? _pipeServer;
    private static bool _running = true;

    static void Main(string[] args)
    {
        // Ensure log directory exists
        try
        {
            var logDir = Path.GetDirectoryName(LogFile);
            if (!string.IsNullOrEmpty(logDir) && !Directory.Exists(logDir))
            {
                Directory.CreateDirectory(logDir);
            }
        }
        catch { }

        LogMessage("User Session Launcher started");

        // Setup console close handler
        Console.CancelKeyPress += (sender, e) =>
        {
            e.Cancel = true;
            _running = false;
            LogMessage("Received shutdown signal");
        };

        // Start named pipe server
        Task.Run(ListenForSignals);

        // Check and launch PulseForm.exe immediately on startup
        Task.Run(async () =>
        {
            await Task.Delay(2000); // Wait 2 seconds for system to stabilize
            CheckAndLaunchPulseForm();
        });

        // Keep running until shutdown
        while (_running)
        {
            Thread.Sleep(1000);
        }

        _pipeServer?.Dispose();
        LogMessage("User Session Launcher stopped");
    }

    static void ListenForSignals()
    {
        while (_running)
        {
            try
            {
                _pipeServer = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.In,
                    1,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous);

                LogMessage("Waiting for service signal...");
                _pipeServer.WaitForConnection();

                LogMessage("Received signal from service");
                
                // Read signal (even if we don't use it, we need to read to clear the pipe)
                byte[] buffer = new byte[1];
                if (_pipeServer.IsConnected)
                {
                    _pipeServer.Read(buffer, 0, 1);
                }

                _pipeServer.Disconnect();
                _pipeServer.Dispose();

                // Check and launch PulseForm.exe
                CheckAndLaunchPulseForm();
            }
            catch (Exception ex)
            {
                LogMessage($"Error in pipe listener: {ex.Message}");
                _pipeServer?.Dispose();
                Thread.Sleep(5000); // Wait before retrying
            }
        }
    }

    static void CheckAndLaunchPulseForm()
    {
        try
        {
            // Check if PulseForm.exe is already running
            if (IsPulseFormRunning())
            {
                LogMessage("PulseForm.exe is already running");
                return;
            }

            // Get path to PulseForm.exe (same directory as this exe)
            string? exeDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
            if (string.IsNullOrEmpty(exeDir))
            {
                exeDir = AppDomain.CurrentDomain.BaseDirectory;
            }
            
            // Also try current working directory as fallback
            if (string.IsNullOrEmpty(exeDir) || !Directory.Exists(exeDir))
            {
                exeDir = Directory.GetCurrentDirectory();
            }

            string pulseFormPath = Path.Combine(exeDir, PulseFormExe);

            if (!File.Exists(pulseFormPath))
            {
                LogMessage($"ERROR: PulseForm.exe not found at: {pulseFormPath}");
                return;
            }

            // Launch PulseForm.exe
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = pulseFormPath,
                WorkingDirectory = exeDir,
                UseShellExecute = true,
                CreateNoWindow = false // PulseForm needs a window
            };

            Process? process = Process.Start(startInfo);
            if (process != null && !process.HasExited)
            {
                LogMessage($"Successfully launched PulseForm.exe (PID: {process.Id})");
            }
            else
            {
                LogMessage("ERROR: Failed to launch PulseForm.exe");
            }
        }
        catch (Exception ex)
        {
            LogMessage($"ERROR launching PulseForm.exe: {ex.Message}");
        }
    }

    static bool IsPulseFormRunning()
    {
        try
        {
            Process[] processes = Process.GetProcessesByName("PulseForm");
            return processes.Length > 0;
        }
        catch
        {
            return false;
        }
    }

    static void LogMessage(string message)
    {
        try
        {
            string logEntry = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {message}";
            File.AppendAllText(LogFile, logEntry + Environment.NewLine);
        }
        catch { }
    }
}

