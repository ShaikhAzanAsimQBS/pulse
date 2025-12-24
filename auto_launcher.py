#pyinstaller --clean --name=auto_launcher --onefile --noconsole --noupx --hidden-import=psutil --hidden-import=ctypes --hidden-import=ctypes.wintypes --exclude-module=matplotlib --exclude-module=numpy --exclude-module=scipy --exclude-module=pandas --exclude-module=IPython --exclude-module=jupyter --runtime-tmpdir=. --log-level=WARN auto_launcher.py
import os
import time
import subprocess
import sys
import ctypes
from ctypes import wintypes
import psutil  # pip install psutil
import traceback
import logging
import atexit
import shutil
import glob
import tempfile
import signal
import threading

# Setup logging with error handling
LOG_FILE = r"C:\Pulse\settings\auto_launcher.log"
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    # Try to open log file to check permissions
    with open(LOG_FILE, 'a') as f:
        pass
except (OSError, PermissionError) as e:
    # If can't write to log file, use fallback location
    LOG_FILE = os.path.join(os.path.expanduser("~"), "auto_launcher.log")
    try:
        with open(LOG_FILE, 'a') as f:
            pass
    except Exception:
        # Last resort: use temp directory
        import tempfile
        LOG_FILE = os.path.join(tempfile.gettempdir(), "auto_launcher.log")

# Custom file handler that flushes immediately
class ImmediateFlushFileHandler(logging.FileHandler):
    """File handler that flushes after each log entry."""
    def emit(self, record):
        super().emit(record)
        self.flush()  # Force write to disk immediately

# Custom console handler that flushes immediately
class ImmediateFlushStreamHandler(logging.StreamHandler):
    """Stream handler that flushes after each log entry."""
    def emit(self, record):
        super().emit(record)
        self.flush()  # Force write to console immediately

try:
    file_handler = ImmediateFlushFileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    console_handler = ImmediateFlushStreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )
except Exception as e:
    # Fallback to basic console logging if file logging fails
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    print(f"Warning: Could not set up file logging: {e}")

MUTEX_NAME = "Global\\PulseFormAutoLauncherMutex"
mutex_handle = None

# Termination tracking
_graceful_shutdown = False
_termination_reason = None
_start_time = None

# Heartbeat file for crash detection
HEARTBEAT_FILE = r"C:\Pulse\settings\auto_launcher_heartbeat.txt"
HEARTBEAT_INTERVAL = 10  # Update heartbeat every 10 seconds

# Win32 API setup
CreateMutex = ctypes.windll.kernel32.CreateMutexW
CreateMutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
CreateMutex.restype = wintypes.HANDLE
CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL
GetLastError = ctypes.windll.kernel32.GetLastError
ERROR_ALREADY_EXISTS = 183

def cleanup_mutex():
    """Release mutex handle on exit."""
    global mutex_handle
    if mutex_handle:
        try:
            CloseHandle(mutex_handle)
            logging.debug("Mutex handle released")
        except Exception as e:
            logging.warning(f"Error releasing mutex: {e}")

atexit.register(cleanup_mutex)

def write_heartbeat():
    """Write heartbeat file to detect if process was killed."""
    try:
        heartbeat_dir = os.path.dirname(HEARTBEAT_FILE)
        os.makedirs(heartbeat_dir, exist_ok=True)
        with open(HEARTBEAT_FILE, 'w') as f:
            f.write(f"{time.time()}\n{os.getpid()}\n")
            f.flush()  # Force write to disk
            os.fsync(f.fileno())  # Ensure OS writes to disk
    except Exception as e:
        logging.debug(f"Could not write heartbeat: {e}")

def check_previous_run_abnormal():
    """Check if previous run ended abnormally by checking heartbeat file."""
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            return False, None
        
        # Read heartbeat file
        with open(HEARTBEAT_FILE, 'r') as f:
            lines = f.readlines()
            if len(lines) < 1:
                return False, None
            
            last_heartbeat_time = float(lines[0].strip())
            current_time = time.time()
            time_since_heartbeat = current_time - last_heartbeat_time
            
            # If heartbeat is older than 30 seconds, previous run likely died
            if time_since_heartbeat > 30:
                # Get PID if available
                old_pid = lines[1].strip() if len(lines) > 1 else "unknown"
                
                # Check if that process still exists
                process_still_running = False
                try:
                    if old_pid != "unknown":
                        old_process = psutil.Process(int(old_pid))
                        if old_process.is_running():
                            process_still_running = True
                except (psutil.NoSuchProcess, ValueError):
                    pass  # Process doesn't exist, which confirms it died
                
                if not process_still_running:
                    return True, {
                        'last_heartbeat': last_heartbeat_time,
                        'time_since_heartbeat': time_since_heartbeat,
                        'old_pid': old_pid
                    }
    except Exception as e:
        logging.debug(f"Error checking previous run: {e}")
    
    return False, None

def heartbeat_loop():
    """Continuously update heartbeat file."""
    global _graceful_shutdown
    while not _graceful_shutdown:
        try:
            write_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)
        except Exception as e:
            logging.debug(f"Error in heartbeat loop: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

def is_folder_locked(folder_path):
    """Check if a folder is locked by another process by attempting to delete a test file."""
    try:
        # Try to create and delete a test file in the folder
        # This is more reliable than renaming the folder
        test_file = os.path.join(folder_path, ".lock_test_file")
        try:
            # Try to create a test file
            with open(test_file, 'w') as f:
                f.write("test")
            # Try to delete it immediately
            os.remove(test_file)
            return False  # Folder is not locked - we can write and delete
        except (PermissionError, OSError, IOError):
            # Can't write/delete - folder is likely locked
            return True
    except Exception:
        # If we can't even check, try a different approach
        # Check if folder is actually accessible
        try:
            os.listdir(folder_path)
            # If we can list it, try to see if we can delete a file
            return False  # Assume not locked if we can access it
        except (PermissionError, OSError):
            return True  # Can't access - likely locked

def get_folder_owner_process(folder_path):
    """Try to find which process might be using this folder."""
    try:
        # Check if any Python/PyInstaller processes are using files in this folder
        folder_name = os.path.basename(folder_path)
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info.get('name', '').lower()
                # Check if it's a Python or PyInstaller process
                if 'python' in proc_name or 'pulseform' in proc_name or 'auto_launcher' in proc_name:
                    # Try to check if process has files open in this folder
                    try:
                        open_files = proc.open_files()
                        for file_info in open_files:
                            if folder_name in file_info.path:
                                return proc.info['pid'], proc.info['name']
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None, None

def cleanup_temp_folders(force_cleanup=False, aggressive=False):
    """Clean up PyInstaller temp folders (_MEI*) from previous runs.
    
    Args:
        force_cleanup: If True, attempts to clean all _MEI* folders regardless of age.
        aggressive: If True, tries harder to clean folders (multiple attempts, longer waits).
    """
    try:
        # Check multiple locations for _MEI* folders
        search_dirs = []
        
        # 1. Standard temp directory
        temp_dir = tempfile.gettempdir()
        search_dirs.append(("Temp directory", temp_dir))
        
        # 2. Directory where auto_launcher.exe is located (important when --runtime-tmpdir=. is used)
        try:
            if getattr(sys, 'frozen', False):
                # Running as compiled .exe
                exe_dir = os.path.dirname(sys.executable)
            else:
                # Running as .py script
                exe_dir = os.path.dirname(os.path.abspath(__file__))
            search_dirs.append(("Executable directory", exe_dir))
        except Exception as e:
            logging.debug(f"Could not get executable directory: {e}")
        
        # 3. Current working directory (fallback)
        try:
            cwd = os.getcwd()
            if cwd not in [d[1] for d in search_dirs]:
                search_dirs.append(("Current directory", cwd))
        except Exception:
            pass
        
        logging.info(f"Starting cleanup of _MEI* folders in {len(search_dirs)} location(s)...")
        # Force flush to ensure message appears
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        # Find all _MEI* folders in all search directories
        mei_folders = []
        for dir_name, dir_path in search_dirs:
            try:
                folders_in_dir = glob.glob(os.path.join(dir_path, "_MEI*"))
                if folders_in_dir:
                    logging.info(f"Found {len(folders_in_dir)} _MEI* folder(s) in {dir_name}: {dir_path}")
                    for folder in folders_in_dir:
                        if os.path.isdir(folder):  # Only include directories
                            mei_folders.append(folder)
            except Exception as e:
                logging.debug(f"Error searching {dir_name} ({dir_path}): {e}")
        
        logging.info(f"Total found: {len(mei_folders)} _MEI* folder(s) to check")
        # Force flush
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        if not mei_folders:
            logging.info("No _MEI* folders found to clean")
            # Force flush
            for handler in logging.root.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
            return
        
        cleaned_count = 0
        locked_count = 0
        failed_count = 0
        skipped_count = 0
        
        logging.info(f"Checking {len(mei_folders)} _MEI* folder(s) for cleanup (aggressive={aggressive})...")
        # Force flush to ensure message appears in console (especially important for .exe)
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        # Log all folders found for debugging
        if len(mei_folders) > 0:
            logging.debug(f"Found _MEI* folders: {[os.path.basename(f) for f in mei_folders]}")
        
        for folder in mei_folders:
            try:
                folder_time = os.path.getmtime(folder)
                age_seconds = time.time() - folder_time
                folder_name = os.path.basename(folder)
                
                # In aggressive mode (startup), check ALL folders regardless of age
                # In normal mode, only clean folders older than 30 seconds
                if aggressive:
                    should_clean = True  # Check all folders in aggressive mode (startup)
                else:
                    age_threshold = 5
                    should_clean = force_cleanup or age_seconds > age_threshold
                
                if not should_clean:
                    skipped_count += 1
                    logging.debug(f"Skipping {folder_name} - too new ({age_seconds:.1f}s old)")
                    continue
                
                # Try to delete the folder directly
                # Don't pre-check if locked - just try to delete and handle errors
                try:
                    # First attempt - immediate removal
                    try:
                        shutil.rmtree(folder, ignore_errors=False)
                    except (PermissionError, OSError) as e:
                        # Folder might be locked, but let's try a few more times
                        if aggressive:
                            # In aggressive mode, try multiple times with delays
                            deleted = False
                            for attempt in range(3):  # Try 3 times
                                time.sleep(0.5 * (attempt + 1))  # Increasing delay: 0.5s, 1s, 1.5s
                                try:
                                    shutil.rmtree(folder, ignore_errors=False)
                                    deleted = True
                                    break
                                except (PermissionError, OSError):
                                    continue
                            
                            if not deleted:
                                # Still locked after multiple attempts
                                # Try to find which process is using it
                                owner_pid, owner_name = get_folder_owner_process(folder)
                                if owner_pid:
                                    logging.warning(f"{folder_name} is locked by process {owner_name} (PID: {owner_pid}) - cannot delete")
                                else:
                                    logging.warning(f"{folder_name} appears to be locked (Permission denied) - cannot delete after {3} attempts")
                                locked_count += 1
                                continue
                        else:
                            # Not aggressive mode - just mark as locked
                            owner_pid, owner_name = get_folder_owner_process(folder)
                            if owner_pid:
                                logging.info(f"{folder_name} is locked by process {owner_name} (PID: {owner_pid}) - will retry on next startup")
                            else:
                                logging.info(f"{folder_name} appears to be locked (Permission denied) - will retry on next startup")
                            locked_count += 1
                            continue
                    
                    # Verify it was deleted
                    if os.path.exists(folder):
                        # Still exists after deletion attempt - this shouldn't happen with ignore_errors=False
                        # But let's try one more time with ignore_errors
                        if aggressive:
                            time.sleep(0.5)
                            shutil.rmtree(folder, ignore_errors=True)
                        
                        # Check again
                        if os.path.exists(folder):
                            failed_count += 1
                            logging.warning(f"Could not delete {folder_name} after attempts (age: {age_seconds:.1f}s)")
                        else:
                            cleaned_count += 1
                            logging.info(f"Cleaned up temp folder: {folder_name} (age: {age_seconds:.1f}s)")
                    else:
                        cleaned_count += 1
                        logging.info(f"Cleaned up temp folder: {folder_name} (age: {age_seconds:.1f}s)")
                        
                except Exception as e:
                    # Unexpected error
                    failed_count += 1
                    logging.warning(f"Error removing {folder_name}: {e}")
                    
            except Exception as e:
                logging.debug(f"Error checking temp folder {folder}: {e}")
        
        # Summary logging
        if cleaned_count > 0:
            logging.info(f"Successfully cleaned up {cleaned_count} temp folder(s)")
        if skipped_count > 0:
            logging.debug(f"Skipped {skipped_count} folder(s) (too new)")
        if locked_count > 0:
            logging.info(f"{locked_count} temp folder(s) are locked by running processes (will retry on next startup)")
        if failed_count > 0:
            logging.warning(f"{failed_count} temp folder(s) could not be deleted (may need manual cleanup)")
        
        if cleaned_count == 0 and locked_count == 0 and failed_count == 0 and skipped_count == 0:
            logging.debug("No _MEI* folders needed cleanup")
        
        # Force flush all handlers after cleanup summary (especially important for .exe)
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
    except Exception as e:
        logging.error(f"Error in cleanup_temp_folders: {e}\n{traceback.format_exc()}")

def detect_termination_reason():
    """Detect why the process is terminating."""
    global _termination_reason, _graceful_shutdown
    
    if _graceful_shutdown:
        return "Graceful shutdown (user or programmatic exit)"
    
    # Check if process is being terminated externally
    try:
        current_process = psutil.Process()
        parent = current_process.parent()
        if parent:
            parent_name = parent.name().lower()
            # Common antivirus/security processes
            av_processes = [
                'msmpeng.exe',  # Windows Defender
                'smartscreen.exe',  # Windows SmartScreen
                'securityhealthsystray.exe',  # Windows Security
                'mcshield.exe',  # McAfee
                'avgsvca.exe',  # AVG
                'avastsvc.exe',  # Avast
                'ekrn.exe',  # ESET
                'bdagent.exe',  # BitDefender
                'kaspersky',  # Kaspersky
                'norton',  # Norton
                'symantec',  # Symantec
            ]
            
            for av in av_processes:
                if av in parent_name:
                    _termination_reason = f"Terminated by antivirus/security: {parent_name}"
                    return _termination_reason
    except Exception:
        pass
    
    # Check for abnormal termination signals
    try:
        # If we get here without graceful shutdown, it's likely external termination
        _termination_reason = "Terminated by external process (OS, antivirus, or task manager)"
        return _termination_reason
    except Exception:
        return "Unknown termination reason"

def signal_handler(signum, frame):
    """Handle termination signals."""
    global _graceful_shutdown, _termination_reason
    
    signal_names = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT",
        signal.SIGBREAK: "SIGBREAK",
    }
    
    sig_name = signal_names.get(signum, f"Signal {signum}")
    _termination_reason = f"Received {sig_name} signal"
    
    logging.warning(f"Termination signal received: {sig_name}")
    logging.warning(f"Termination reason: {detect_termination_reason()}")
    
    _graceful_shutdown = True
    
    # Force flush logs before cleanup
    for handler in logging.root.handlers:
        if hasattr(handler, 'flush'):
            handler.flush()
    
    cleanup_on_exit()
    
    # Force flush again after cleanup
    for handler in logging.root.handlers:
        if hasattr(handler, 'flush'):
            handler.flush()
    
    sys.exit(0)

def setup_signal_handlers():
    """Setup signal handlers for termination detection."""
    try:
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)
        logging.debug("Signal handlers registered")
    except Exception as e:
        logging.warning(f"Could not set up signal handlers: {e}")

def monitor_process_health():
    """Monitor if process is being terminated externally."""
    global _graceful_shutdown
    
    def check_health():
        while not _graceful_shutdown:
            try:
                time.sleep(30)  # Check every 30 seconds
                
                # Check if process is still running normally
                current_process = psutil.Process()
                status = current_process.status()
                
                if status == psutil.STATUS_ZOMBIE:
                    logging.critical("Process detected as ZOMBIE - may have been killed!")
                    _termination_reason = "Process killed (ZOMBIE status)"
                    break
                    
            except psutil.NoSuchProcess:
                logging.critical("Process no longer exists - was terminated!")
                _termination_reason = "Process terminated externally"
                break
            except Exception as e:
                logging.debug(f"Health check error: {e}")
                time.sleep(60)  # Wait longer on error
    
    # Start health monitor in background
    health_thread = threading.Thread(target=check_health, daemon=True)
    health_thread.start()

def cleanup_on_exit():
    """Comprehensive cleanup on exit."""
    global _graceful_shutdown, _termination_reason, _start_time
    
    try:
        if not _graceful_shutdown:
            # Abnormal termination detected
            reason = detect_termination_reason()
            logging.critical("=" * 60)
            logging.critical("ABNORMAL TERMINATION DETECTED!")
            logging.critical(f"Reason: {reason}")
            logging.critical("=" * 60)
            
            # Log additional diagnostic info
            try:
                current_process = psutil.Process()
                parent = current_process.parent()
                if parent:
                    logging.critical(f"Parent process: {parent.name()} (PID: {parent.pid})")
            except Exception:
                pass
            
            # Calculate uptime
            if _start_time:
                uptime = time.time() - _start_time
                logging.critical(f"Uptime before termination: {uptime:.2f} seconds ({uptime/60:.2f} minutes)")
        else:
            logging.info("Auto launcher shutting down gracefully...")
            if _termination_reason:
                logging.info(f"Shutdown reason: {_termination_reason}")
        
        cleanup_mutex()
        
        # Clean up temp folders - try to clean current process's folder on graceful shutdown
        # If graceful shutdown, try force cleanup; if abnormal, will be cleaned on next startup
        cleanup_temp_folders(force_cleanup=_graceful_shutdown, aggressive=_graceful_shutdown)
        
        if _graceful_shutdown:
            logging.info("Cleanup completed")
        else:
            logging.critical("Cleanup attempted after abnormal termination")
    except Exception as e:
        logging.error(f"Error during exit cleanup: {e}")

atexit.register(cleanup_on_exit)

def ensure_single_instance():
    """Prevent multiple instances of this launcher from running."""
    global mutex_handle
    try:
        mutex_handle = CreateMutex(None, False, MUTEX_NAME)
        if mutex_handle == 0:
            logging.error("Failed to create mutex. Exiting.")
            sys.exit(1)
        
        last_error = GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            logging.info("Another instance is already running. Exiting.")
            CloseHandle(mutex_handle)
            sys.exit(0)
        logging.debug("Single instance mutex acquired")
    except Exception as e:
        logging.error(f"Error creating mutex: {e}\n{traceback.format_exc()}")
        sys.exit(1)

def get_exe_path(filename):
    """Return absolute path of file in the same directory as this script/exe.
    Handles both .py script and PyInstaller .exe cases.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        if getattr(sys, 'frozen', False):
            # Running as compiled .exe
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as .py script
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        exe_path = os.path.join(base_dir, filename)
        # Normalize path (resolve any relative components)
        exe_path = os.path.normpath(os.path.abspath(exe_path))
        return exe_path
    except Exception as e:
        logging.error(f"Error getting exe path: {e}\n{traceback.format_exc()}")
        # Fallback to current directory
        return os.path.join(os.getcwd(), filename)

def is_pulseform_running():
    """Check if PulseForm.exe is already active with improved reliability."""
    try:
        pulseform_count = 0
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                proc_name = proc.info.get('name', '')
                if proc_name and proc_name.lower() == "pulseform.exe":
                    pulseform_count += 1
                    # Verify process is actually running (not zombie)
                    try:
                        proc.status()  # This will raise if process is dead
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logging.debug(f"Error checking process {proc.info.get('pid', 'unknown')}: {e}")
                continue
        return False
    except Exception as e:
        logging.warning(f"Error in is_pulseform_running: {e}\n{traceback.format_exc()}")
        # On error, assume not running to allow launch attempt
        return False

def run_pulseform():
    """Launch PulseForm.exe with comprehensive error handling and validation."""
    try:
        exe_path = get_exe_path("PulseForm.exe")
        logging.debug(f"Checking for PulseForm.exe at: {exe_path}") 
        
        if not os.path.exists(exe_path):
            logging.warning(f"PulseForm.exe not found at: {exe_path}")
            logging.warning(f"Current working directory: {os.getcwd()}")
            logging.warning(f"Script location: {os.path.dirname(os.path.abspath(__file__) if '__file__' in globals() else sys.argv[0])}")
            return False

        # Double-check if already running (race condition protection)
        if is_pulseform_running():
            logging.debug("PulseForm.exe is already running. Skipping launch.")
            return True

        try:
            # Launch with improved error handling
            # Use DETACHED_PROCESS to prevent child from keeping parent's temp folder locked
            # This allows parent's _MEI* folder to be cleaned up when parent exits
            DETACHED_PROCESS = 0x00000008
            exe_dir = os.path.dirname(exe_path)
            process = subprocess.Popen(
                [exe_path], 
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW | DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=exe_dir if exe_dir else None
            )
            
            # Give process a moment to start
            time.sleep(0.5)
            
            # Verify process actually started
            if process.poll() is not None:
                # Process exited immediately (error)
                return_code = process.returncode
                logging.error(f"PulseForm.exe exited immediately with code: {return_code}")
                return False
            
            # Verify it's actually running by checking process list
            if is_pulseform_running():
                logging.info(f"Successfully launched PulseForm.exe (PID: {process.pid})")
                return True
            else:
                logging.warning("PulseForm.exe launch reported success but process not found")
                return False
                
        except subprocess.SubprocessError as e:
            logging.error(f"Subprocess error launching PulseForm.exe: {e}\n{traceback.format_exc()}")
            return False
        except FileNotFoundError:
            logging.error(f"PulseForm.exe not found at: {exe_path}")
            return False
        except PermissionError as e:
            logging.error(f"Permission denied launching PulseForm.exe: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error launching PulseForm.exe: {e}\n{traceback.format_exc()}")
            return False
    except Exception as e:
        logging.error(f"Error in run_pulseform: {e}\n{traceback.format_exc()}")
        return False

def main():
    """Main entry point with comprehensive error handling and recovery."""
    global _graceful_shutdown, _start_time, _termination_reason
    
    _start_time = time.time()
    _graceful_shutdown = False
    _termination_reason = None
    
    try:
        # Check if previous run ended abnormally (BEFORE any other logging)
        abnormal_exit, exit_info = check_previous_run_abnormal()
        if abnormal_exit:
            logging.critical("=" * 60)
            logging.critical("PREVIOUS RUN DETECTED AS ABNORMALLY TERMINATED!")
            logging.critical(f"Last heartbeat: {exit_info['last_heartbeat']:.2f}")
            logging.critical(f"Time since last heartbeat: {exit_info['time_since_heartbeat']:.2f} seconds")
            logging.critical(f"Previous PID: {exit_info['old_pid']}")
            logging.critical("Likely killed by: OS, Antivirus, or Task Manager")
            logging.critical("=" * 60)
            # Force flush to ensure this critical message is written
            for handler in logging.root.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
        
        # Setup signal handlers for termination detection
        setup_signal_handlers()
        
        # Start health monitoring
        monitor_process_health()
        
        # Start heartbeat thread (critical for crash detection)
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        logging.debug("Heartbeat monitoring started")
        
        # Write initial heartbeat
        write_heartbeat()
        
        # Clean up old temp folders on startup (including from previous killed runs)
        # Use aggressive mode to clean ALL _MEI* folders that are not in use
        # This will clean _MEI* folders from processes that were killed
        logging.info("=" * 60)
        logging.info("Starting cleanup of temp folders on startup...")
        # Force flush to ensure message appears
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        try:
            cleanup_temp_folders(force_cleanup=False, aggressive=True)
        except Exception as e:
            logging.error(f"Error during temp folder cleanup: {e}\n{traceback.format_exc()}")
        logging.info("Temp folder cleanup completed.")
        logging.info("=" * 60)
        # Force flush to ensure message appears
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        ensure_single_instance()
        logging.info("=" * 60)
        logging.info("Background launcher started. Running every 10 minutes.")
        logging.info(f"Log file: {LOG_FILE}")
        logging.info(f"Process ID: {os.getpid()}")
        logging.info("=" * 60)
        # Force flush startup message
        for handler in logging.root.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        iteration = 0
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while True:
            iteration += 1
            try:
                # Log heartbeat every 10 iterations (every ~100 minutes)
                if iteration % 10 == 0:
                    logging.info(f"Launcher heartbeat: Still running (iteration {iteration})")
                    # Force flush heartbeat log
                    for handler in logging.root.handlers:
                        if hasattr(handler, 'flush'):
                            handler.flush()
                
                success = run_pulseform()
                
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logging.warning(f"Failed to launch PulseForm.exe {consecutive_failures} times in a row")
                        logging.warning("Waiting 5 minutes before next attempt...")
                        time.sleep(5 * 60)  # Wait 5 minutes on repeated failures
                        consecutive_failures = 0  # Reset counter after wait
                        continue
                
            except KeyboardInterrupt:
                _graceful_shutdown = True
                _termination_reason = "User interrupt (Ctrl+C)"
                logging.info("Launcher interrupted by user (Ctrl+C)")
                logging.info("Shutting down gracefully...")
                break
            except SystemExit:
                _graceful_shutdown = True
                _termination_reason = "System exit requested"
                logging.info("System exit requested")
                logging.info("Shutting down gracefully...")
                raise  # Re-raise to exit properly
            except Exception as e:
                consecutive_failures += 1
                logging.error(f"Unexpected error in main loop (iteration {iteration}): {e}\n{traceback.format_exc()}")
                
                if consecutive_failures >= max_consecutive_failures:
                    logging.warning(f"Multiple consecutive errors ({consecutive_failures}). Waiting 5 minutes...")
                    time.sleep(5 * 60)
                    consecutive_failures = 0
                else:
                    # Wait 1 minute on error, then continue to normal 10-minute cycle
                    logging.info("Waiting 1 minute before retrying...")
                    time.sleep(60)
                    continue
            
            # Normal wait: 10 minutes between launch attempts
            time.sleep(10 * 60)
            
    except KeyboardInterrupt:
        _graceful_shutdown = True
        _termination_reason = "User interrupt (KeyboardInterrupt)"
        logging.info("Launcher stopped by user")
        logging.info("Performing cleanup...")
    except SystemExit:
        _graceful_shutdown = True
        if _termination_reason is None:
            _termination_reason = "System exit"
        logging.info("Launcher exiting")
        logging.info("Performing cleanup...")
        raise
    except Exception as e:
        # Last resort: log critical error
        # This should never happen as all exceptions are caught in the inner loop
        _graceful_shutdown = False
        _termination_reason = f"Fatal exception: {type(e).__name__}"
        logging.critical(f"FATAL ERROR in launcher (outer exception handler): {e}\n{traceback.format_exc()}")
        logging.critical("This should not happen. Exiting.")
        logging.info("Performing cleanup...")
        sys.exit(1)
    finally:
        # Ensure cleanup happens even if something goes wrong
        try:
            # Mark as graceful shutdown if we reach here
            _graceful_shutdown = True
            
            # Delete heartbeat file on normal exit
            try:
                if os.path.exists(HEARTBEAT_FILE):
                    os.remove(HEARTBEAT_FILE)
            except Exception:
                pass
            
            if _graceful_shutdown:
                logging.info("Auto launcher stopped. Cleaning up...")
            else:
                logging.critical("Auto launcher terminated abnormally. Attempting cleanup...")
            
            # Clean up temp folders on exit
            # If graceful, try to clean current folder; if killed, will be cleaned on next startup
            cleanup_temp_folders(force_cleanup=_graceful_shutdown, aggressive=_graceful_shutdown)
            
            if _graceful_shutdown:
                logging.info("Cleanup completed. Exiting.")
            else:
                logging.critical("Cleanup attempted. Process may have been killed by external force.")
                logging.critical(f"Termination reason: {_termination_reason or 'Unknown'}")
                logging.critical("Note: _MEI* folder will be cleaned on next startup if not locked")
            
            # Force flush all logs before exit
            for handler in logging.root.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
        except Exception as e:
            logging.error(f"Error in final cleanup: {e}")
            # Force flush even on error
            for handler in logging.root.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()

if __name__ == "__main__":
    main()