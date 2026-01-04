#pyinstaller --clean --name=PulseForm --onefile --windowed --noconsole--noupx --add-data "C:\Pulse\settings\media;settings\media" --hidden-import=win32timezone --hidden-import=win32api --hidden-import=win32con --hidden-import=win32gui --hidden-import=win32com.client --hidden-import=win32process --hidden-import=pythoncom --hidden-import=pywintypes --hidden-import=comtypes --hidden-import=comtypes.client --hidden-import=pycaw --hidden-import=pycaw.pycaw --hidden-import=customtkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=cryptography --hidden-import=cryptography.fernet --hidden-import=keyboard --hidden-import=psutil --hidden-import=requests --hidden-import=zoneinfo --collect-all=customtkinter --collect-all=PIL --collect-all=pycaw --collect-all=comtypes --exclude-module=matplotlib --exclude-module=numpy --exclude-module=scipy --exclude-module=pandas --exclude-module=IPython --exclude-module=jupyter --runtime-tmpdir=. --log-level=WARN PulseForm.py
# Standard library imports
import os
import sys
import time
import json
import socket
import threading
import traceback
import logging
import subprocess
import atexit
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Third-party imports
from tkinter import Tk, Toplevel, IntVar, StringVar, Radiobutton
from tkinter import messagebox
from cryptography.fernet import Fernet
import requests
import keyboard
import psutil
from PIL import Image
import customtkinter as ctk

# Windows API imports
import ctypes
from ctypes import wintypes, windll, POINTER, cast
import win32gui
import win32con
import win32com.client
import win32process
import win32api
import pythoncom
import comtypes
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# Setup logging for crash debugging
LOG_FILE = r"C:\Pulse\settings\pulseform.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

MUTEX_NAME = "Global\\PulseFormMutex"
mutex_handle = None

# Global COM initialization tracking
_com_initialized = threading.local()

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
    if mutex_handle and mutex_handle != 0:
        try:
            CloseHandle(mutex_handle)
            logging.debug("Mutex handle released")
        except Exception as e:
            logging.warning(f"Error releasing mutex: {e}")

atexit.register(cleanup_mutex)

def ensure_single_instance():
    """Prevent multiple instances of this launcher from running."""
    global mutex_handle
    print("Ensuring single instance...")
    try:
        mutex_handle = CreateMutex(None, False, MUTEX_NAME)
        if mutex_handle == 0:
            logging.error("Failed to create mutex. Exiting.")
            sys.exit(1)
        
        last_error = GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            print("[!] Another instance is already running. Exiting.")
            if mutex_handle:
                CloseHandle(mutex_handle)
            sys.exit(0)
        logging.debug("Single instance mutex acquired")
    except Exception as e:
        logging.error(f"Error creating mutex: {e}\n{traceback.format_exc()}")
        sys.exit(1)

ensure_single_instance()

# Global exception handler for unhandled exceptions
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler to log all unhandled exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"Unhandled exception: {error_msg}")
    
    # Try to write to a crash log file
    try:
        crash_log = r"C:\Pulse\settings\crash.log"
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CRASH at {datetime.now().isoformat()}\n")
            f.write(f"{'='*80}\n")
            f.write(error_msg)
            f.write(f"\n{'='*80}\n\n")
    except Exception:
        pass  # If we can't write crash log, continue
    
    # Call default handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = global_exception_handler

user32 = ctypes.windll.user32

def bring_to_front(window):
    """Bring window to front with proper error handling and validation."""
    if not window or not window.winfo_exists():
        logging.warning("Window does not exist, cannot bring to front")
        return
    
    try:
        window_title = window.title()
        hwnd = win32gui.FindWindow(None, window_title)
        
        if not hwnd:
            logging.warning(f"Window handle not found for '{window_title}'")
            return
        
        # Validate window handle is still valid
        try:
            win32gui.IsWindow(hwnd)
        except Exception:
            logging.warning("Invalid window handle")
            return
        
        # Make sure window is visible (restore if minimized)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Check if window is already in foreground (avoid unnecessary operations)
        try:
            current_foreground = win32gui.GetForegroundWindow()
            if current_foreground == hwnd:
                logging.debug(f"Window '{window_title}' is already in foreground")
                return  # Already in front, no need to do anything
        except Exception:
            pass  # Continue if check fails
        
        # Allow this process to set foreground
        try:
            user32.AllowSetForegroundWindow(win32api.GetCurrentProcessId())
        except Exception as e:
            logging.debug(f"Could not allow set foreground: {e}")

        # Send ALT key to bypass Windows restriction (helps with focus stealing prevention)
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%')
        except Exception as e:
            logging.debug(f"Could not send ALT key: {e}")

        # Try to bring window to front
        # Note: Windows may reject this if another app has focus (this is normal Windows behavior)
        try:
            win32gui.SetForegroundWindow(hwnd)
            logging.debug(f"Window '{window_title}' brought to front successfully")
        except Exception as e:
            # This is expected behavior - Windows protects against focus stealing
            # The window is still visible and will appear when user switches to it
            # Only log as debug/warning, not error, since this is normal Windows behavior
            error_msg = str(e)
            if "SetForegroundWindow" in error_msg or "No error message is available" in error_msg:
                # This is Windows' way of saying "focus stealing prevented" - it's normal
                logging.debug(f"Windows prevented focus change (normal behavior): {error_msg}")
            else:
                # Other errors might be worth warning about
                logging.warning(f"Could not set foreground window: {error_msg}")
        
    except Exception as e:
        # Only log as error if it's something unexpected
        error_msg = str(e)
        if "SetForegroundWindow" in error_msg:
            logging.debug(f"Windows focus restriction (expected): {error_msg}")
        else:
            logging.error(f"Unexpected error bringing window to front: {e}\n{traceback.format_exc()}")
 
 
 
 
def keep_window_on_top(window, interval=3):
    """Keep window on top with proper error handling and cleanup."""
    def run():
        pythoncom.CoInitialize()
        try:
            while True:
                try:
                    # Check if window still exists before trying to bring to front
                    if window and window.winfo_exists():
                        bring_to_front(window)
                    else:
                        logging.info("Window destroyed, stopping keep_window_on_top thread")
                        break
                    time.sleep(interval)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logging.error(f"Error in keep_window_on_top loop: {e}\n{traceback.format_exc()}")
                    time.sleep(interval)  # Continue even after error
        except Exception as e:
            logging.error(f"Fatal error in keep_window_on_top thread: {e}\n{traceback.format_exc()}")
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception as e:
                logging.error(f"Error uninitializing COM in keep_window_on_top: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    logging.info("keep_window_on_top thread started")     

#idher function(get_unmute_program_list) bane  ga to check taskmanager k thorugh how many programs are running
#filter by program MS teams, zoom google meet/chrome 
#belo is an example function to check if meeting app is running using psutil

#chrome python tab check krna hai "meet". ne fucntion

# def is_meeting_app_running():
#     """
#     Returns True if MS Teams, Zoom, Google Meet (Chrome tab),
#     or Chrome is running. Otherwise False.
#     """

#     # Process names to check (lowercase)
#     target_processes = {
#         "ms-teams.exe",     # Microsoft Teams (new)
#         "teams.exe",        # Microsoft Teams (classic)
#         "zoom.exe",         # Zoom (Windows)
#         "zoom",             # Zoom (macOS/Linux)
#         "chrome.exe",       # Google Chrome (Windows) #check tabs in "meet"
#         "google-chrome",    # Chrome (Linux)
#         "chrome"            # Chrome (macOS)
#     }

#     for proc in psutil.process_iter(attrs=["name"]):
#         try:
#             if proc.info["name"] and proc.info["name"].lower() in target_processes:
#                 return True
#         except (psutil.NoSuchProcess, psutil.AccessDenied):
#             continue

#     return False


def mute_system():
    """Mute system audio with proper COM lifecycle management."""
    try:
        comtypes.CoInitialize()
        _com_initialized.initialized = True
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(1, None)
        logging.info("System muted successfully")
    except Exception as e:
        logging.error(f"Failed to mute system: {e}\n{traceback.format_exc()}")
    finally:
        try:
            if getattr(_com_initialized, 'initialized', False):
                comtypes.CoUninitialize()
                _com_initialized.initialized = False
        except Exception as e:
            logging.error(f"Error uninitializing COM in mute_system: {e}")

def unmute_system():
    """Unmute system audio with proper COM lifecycle management."""
    try:
        comtypes.CoInitialize()
        _com_initialized.initialized = True
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(0, None)
        logging.info("System unmuted successfully")
    except Exception as e:
        logging.error(f"Failed to unmute system: {e}\n{traceback.format_exc()}")
    finally:
        try:
            if getattr(_com_initialized, 'initialized', False):
                comtypes.CoUninitialize()
                _com_initialized.initialized = False
        except Exception as e:
            logging.error(f"Error uninitializing COM in unmute_system: {e}")



def has_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False



def check_internet_startup():
    """If offline, show a frameless fullscreen dialog with only a Restart button."""
    if has_internet():
        print("Internet connection detected at startup.")
        return 0  # go on if online 
    else:
        print("No internet connection detected at startup.")
        return 1

   


# Global variable to store the process
block_process = None

# Function to start block.exe
def start_block_exe():
    """Start block.exe with proper error handling."""
    global block_process
    try:
        # Try to find block.exe in current directory or same directory as exe
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            block_path = os.path.join(exe_dir, "block.exe")
        else:
            block_path = os.path.join(os.getcwd(), "block.exe")
        
        if not os.path.exists(block_path):
            block_path = "block.exe"  # Fallback to PATH #settings k folder me le jao block.exe ko 
        
        block_process = subprocess.Popen(
            [block_path], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logging.info("block.exe started successfully")
        return "block.exe started successfully"
    except Exception as e:
        logging.error(f"Failed to start block.exe: {e}\n{traceback.format_exc()}")
        block_process = None
        return None

# Function to stop block.exe
def stop_block_exe():
    """Stop block.exe with proper error handling."""
    global block_process
    if block_process:
        try:
            # Terminate the block.exe process when form is submitted successfully
            block_process.terminate()
            # Wait a bit for graceful termination
            try:
                block_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                block_process.kill()
                block_process.wait()
            logging.info("block.exe stopped successfully")
        except Exception as e:
            logging.error(f"Error stopping block.exe: {e}")
        finally:
            block_process = None


#SNOOZE LOGIC

SNOOZE_FILE = "C:\\Pulse\\settings\\snooze_time.txt"

def is_snoozed():
    if not os.path.exists(SNOOZE_FILE):
        return False

    with open(SNOOZE_FILE, "r") as f:
        try:
            snooze_until = datetime.fromisoformat(f.read().strip())
        except Exception:
            return False

    if datetime.now() < snooze_until:
        return True
    else:
        print("Snooze expired, removing file.")
        # os.remove(SNOOZE_FILE)
        return False

def snooze_for_hours(hours):
    snooze_until = datetime.now() + timedelta(hours=hours)
    with open(SNOOZE_FILE, "w") as f:
        f.write(snooze_until.isoformat())

    stop_block_exe() #compulsoory on exit of pulse fomr 
    unmute_system()
    print("Snoozed, Exiting")
    root.destroy()
    SystemExit

    
def show_snooze_popup():
    popup = Toplevel(root)  # ✅ no tk. prefix
    popup.title("Snooze Form")
    popup.geometry("300x300")
    popup.grab_set()
    # Title
    title_label = ctk.CTkLabel(
        popup,
        text="Snooze for how many hours?",
        font=("Segoe UI", 16, "bold"),
        text_color="black"
    )
    title_label.pack(pady=15)
    

    selected_hour = IntVar(value=1)

    for i in range(1, 6):
        Radiobutton(popup, text=f"{i} hour{'s' if i > 1 else ''}",
                    variable=selected_hour, value=i,
                    font=('Segoe UI', 11)).pack(anchor='w', padx=40)

    def confirm_snooze():
        snooze_for_hours(selected_hour.get())

    confirm_btn = ctk.CTkButton(
        popup,
        text="Confirm",
        command=confirm_snooze,
        fg_color="#9C27B0",     # purple
        hover_color="#7B1FA2",  # lighter purple hover
        corner_radius=15,
        font=("Segoe UI", 14, "bold"),
        width=120,
        height=40
    )
    confirm_btn.pack(pady=25)



email=0
password=0
user_name = 0
# File paths
#time.sleep(5)
SESSION_FILE = "C:\\Pulse\\settings\\session.txt"
LOGIN_FILE = r"C:\Pulse\settings\logInfo.txt"

key_file_path = r"C:\Pulse\settings\secret.key"

# Read the key from the file
with open(key_file_path, "rb") as key_file:  # Read in binary mode
    SECRET_KEY = key_file.read()

cipher_suite = Fernet(SECRET_KEY)

# Function to decrypt the file and return its content
def decrypt_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            encrypted_data = file.read()
            if encrypted_data:  # Check if file is not empty
                decrypted_data = cipher_suite.decrypt(encrypted_data).decode()
                return decrypted_data
            else:
                return ""  # Empty file
    except Exception as e:
        print(f"Error decrypting file {file_path}: {e}")
        return ""

# Function to parse login file and extract email and password
def parse_login_file():
    decrypted_content = decrypt_file(LOGIN_FILE)
    if decrypted_content:
        lines = decrypted_content.split(", ")
        email = lines[0].split(": ")[1]
        password = lines[1].split(": ")[1]
        return email, password
    return None, None



def parse_session_file():
    decrypted_content = decrypt_file(SESSION_FILE)
    if decrypted_content:
        lines = decrypted_content.split(", ")
        token = lines[0].split(": ")[1]
        user_id = lines[1].split(": ")[1]
        token_type = lines[2].split(": ")[1]
        company_id = lines[3].split(": ")[1]
        employee_id = lines[4].split(": ")[1]
        time_zone = lines[5].split(": ")[1]
        user_name = lines[6].split(": ")[1] 
        return token, user_id, token_type, company_id, employee_id, time_zone, user_name
    return None, None, None, None, None, None, None


# Example Usage: Decrypt and store data into variables
email, password = parse_login_file()


print(email) 
print(password)
session_data = {}
token, user_id, token_type, company_id, employee_id,time_zone,user_name = parse_session_file()
if token and user_id and token_type and company_id and employee_id:
    session_data = {
        'token': token,
        'user_id': user_id,
        'token_type': token_type,
        'company_id': company_id,
        'employee_id': employee_id,
        'time_zone': time_zone,
        'user_name': user_name
    }

print("before session_data:", session_data)

def fetch_and_store_active_company_id(session_data):
    """
    Fetch user data from the API and store 'active_company_id' into session_data.

    Args:
        session_data (dict): Dictionary containing user token, IDs, etc.

    Returns:
        dict: Updated session_data with 'active_company_id' if found.
    """
    base_url = "https://pulse.workamp.net/api/v1"
    url = f"{base_url}/user/show/{session_data['user_id']}"

    headers = {
        "Authorization": f"{session_data['token_type']} {session_data['token']}",
        "company-id": session_data['company_id'],
        "Accept": "application/json"
    }

    params = {
        "id": session_data['user_id'],
        "company-id": session_data['company_id']
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get('success') and 'data' in data:
            user_data = data['data']
            active_company_id = user_data.get('active_company_id')

            if active_company_id:
                session_data['active_company_id'] = active_company_id
                print(f"active_company_id stored: {active_company_id}")
            else:
                print("active_company_id not found in response.")
        else:
            print("Unexpected response:", data)

    except requests.exceptions.RequestException as e:
        print("API Request Failed:", e)

    return session_data



BASE_URL = "https://pulse.workamp.net/api/v1"
LOGIN_ENDPOINT = "/auth/login"
SHOW_ENDPOINT = "/pulse-survey/questions/showPulseSurvey"
QUESTION_GET = "/pulse-survey/questions/index" 
STORE_QUESTION = "/pulse-survey-answers/store"       
# Dictionary to store session data

#removve login functionality 
def login(email, password):
    url = f"{BASE_URL}{LOGIN_ENDPOINT}"
    params = {"email": email, "password": password}

    try:
        response = requests.post(url, params=params)

        print("Response Status Code:", response.status_code)
        print("Response Text:", response.text)

        if response.status_code == 200:
            try:
                response_data = response.json()

                # Storing session data
                session_data['token'] = response_data['data']['token']
                session_data['token_type'] = response_data['data']['token_type']
                session_data['user_id'] = response_data['data']['user']['id']
                session_data['company_id'] = response_data['data']['company']['id']
                session_data['employee_id'] = response_data['data']['user']['employee']['id']
                print("Session Data Stored:", session_data)
                return response_data
            except ValueError as e:
                print("Failed to parse JSON:", e)
                return None
        else:
            print(f"Failed to login. Status code: {response.status_code}")
            exit()
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        exit()
        return None
    
check_internet= check_internet_startup()  
#login(email, password)
if check_internet==0:
    fetch_and_store_active_company_id(session_data)
    


print("-----------------------------------------")
print("after session_data:", session_data)


def showform():
    url = f"{BASE_URL}{SHOW_ENDPOINT}"
    authorization_header = f"{session_data['token_type']} {session_data['token']}"

    headers = {
        "User-Agent": "postman-request",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": authorization_header,
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(session_data['company_id'])

    }
    try:
        # Sending the get request with timeout
        response = requests.get(url, headers=headers, timeout=10)
        
        # Handling the response
        if response.status_code == 200:
            result = response.json()
            logging.info("Data received successfully from /pulse-survey/questions/showPulseSurvey")

            # Check the 'data' field in the JSON payload
            if result.get('data'):
                # Survey is open (data == True)
                return 1
            else:
                # Survey period has ended (data == False)
                return 0
        else:
            logging.warning(f"HTTP Error for showform: {response.status_code}")
            return 0

    except requests.exceptions.Timeout:
        logging.error("Timeout while checking survey status")
        return 0
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error in showform: {e}")
        return 0
    except Exception as e:
        logging.error(f"Error in showform: {e}\n{traceback.format_exc()}")
        return 0


def getQuestion():
    url = f"{BASE_URL}{QUESTION_GET}"
    authorization_header = f"{session_data['token_type']} {session_data['token']}"

    headers = {
        "User-Agent": "postman-request",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": authorization_header,
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(session_data['company_id'])
    }
    try:
        # Sending the get request with timeout
        response = requests.get(url, headers=headers, timeout=10)
        
        # Handling the response
        if response.status_code == 200:
            data = response.json()
            logging.info("Data received successfully from /pulse-survey/questions/index")
            return data
        else:
            logging.warning(f"HTTP Error in getQuestion: {response.status_code}")
            return 0

    except requests.exceptions.Timeout:
        logging.error("Timeout while fetching questions")
        return 0
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error in getQuestion: {e}")
        return 0
    except Exception as e:
        logging.error(f"Error in getQuestion: {e}\n{traceback.format_exc()}")
        return 0

# def get_questions_dict():
#     raw = getQuestion()
#     # If API explicitly returns data=False, survey has ended
#     if raw and raw.get('data') is False:
#         # Exit the program cleanly
#         SystemExit
#         sys.exit(0)
#
#     if raw and raw.get('success'):
#         q_list = raw['data']['questions']
#         by_id = {q['id']: q for q in q_list}
#         ids   = [q['id'] for q in q_list]
#         return {
#             'by_id':            by_id,
#             'ids':              ids,
#             'can_answer_again': raw['data']['can_answer_again']
#         }
#     else:
#         return None



'''----------------------------------------------------------------offline wala kaam-----------------------------------------------------'''
print("---------------------------------------------------------offline wala function---------------------------------------------------------")  
global questions
questions = []

def getQuestionOffline(date):
    url = f"{BASE_URL}{QUESTION_GET}"
    authorization_header = f"{session_data['token_type']} {session_data['token']}"

    headers = {
        "User-Agent": "postman-request",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": authorization_header,
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(session_data['company_id'])
    }
    
    
    try:
        # Sending the get request with timeout
        response = requests.get(url, headers=headers, params={"date": date}, timeout=10)
        
        # Handling the response
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Fetched questions for date: {date}")
            return data
        else:
            logging.warning(f"HTTP Error in getQuestionOffline for {date}: {response.status_code}")
            return 0

    except requests.exceptions.Timeout:
        logging.error(f"Timeout while fetching questions for {date}")
        return 0
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error in getQuestionOffline for {date}: {e}")
        return 0
    except Exception as e:
        logging.error(f"Error in getQuestionOffline for {date}: {e}\n{traceback.format_exc()}")
        return 0
    
from datetime import datetime, timedelta


#cache api has to be called here instead of this one.
#HIT cache api once to get all unasnswered days questions and store them in settings/questions folder as date wise .txt files.
def call_next_three_days():
    today = datetime.today()
    save_dir = r"C:\Pulse\settings\questions"
    os.makedirs(save_dir, exist_ok=True)  # make sure folder exists

    for i in range(1, 4):  # 1 = tomorrow, 2 = day after, 3 = third day
        target_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        file_path = os.path.join(save_dir, f"{target_date}.txt")

        # Skip API call if file already exists
        if os.path.exists(file_path):
            print(f"File already exists: {file_path} (skipping API call)")
            continue  

        # --- Call API only if file not present ---
        getQuestionOffline(target_date)
        surveyFuture = get_questions_dict()

        if not surveyFuture:
            print(f"No questions found for {target_date}")
            continue

        questions = []
        for api_id in surveyFuture['ids']:
            api_q = surveyFuture['by_id'][api_id]

            # map the API's `type` field into your UI types:
            if api_q['type'] == 'scale':
                q_type = 'scaled'
            elif api_q['type'] == 'nps-style':
                q_type = 'nps'
            elif api_q['type'] in ('boolean', 'binary'):
                q_type = 'binary'
            else:
                q_type = 'open'

            questions.append({
                "id":       api_id,       # the true question ID
                "type":     q_type,       # one of 'scaled','nps','binary','open'
                "question": api_q['name'] # the text to display
            })

        # --- Save to file ---
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=4, ensure_ascii=False)

        print(f" Questions saved to: {file_path}")
        

if check_internet == 0:
    def safe_call_next_three_days():
        try:
            call_next_three_days()
        except Exception as e:
            logging.error(f"Error in call_next_three_days thread: {e}\n{traceback.format_exc()}")
    
    thread = threading.Thread(target=safe_call_next_three_days, daemon=True)
    thread.start()
    logging.info("Background question fetching started")


    
    
def get_questions_dict():
    raw = getQuestion()
    # If API explicitly returns data=False, survey has ended
    if raw and raw.get('data') is False:
        # Exit the program cleanly
        print("Survey has ended. Exiting")
        SystemExit
        sys.exit(0)

    if raw and raw.get('success'):
        q_list = raw['data']['questions']
        by_id = {q['id']: q for q in q_list}
        ids   = [q['id'] for q in q_list]
        return {
            'by_id':            by_id,
            'ids':              ids,
            'can_answer_again': raw['data']['can_answer_again']
        }
    else:
        return None

today = datetime.today()
target_date = (today).strftime("%Y-%m-%d")
show=0
response_file_of_today = os.path.join("C:\\Pulse\\settings\\responses", f"{target_date}-response.txt")
print(response_file_of_today)


def submit_offline_to_api(q_file, r_file, date):
    # print("Submitting offline responses to API...")

    print("Date in offline to api:", date)
    print("------------------------------------------------")
    with open(q_file, "r", encoding="utf-8") as f:
        questions_old = json.load(f)
    with open(r_file, "r", encoding="utf-8") as f:
        answers_old = json.load(f)

    print("Questions:", questions_old)
    print("Answers:", answers_old)
    print("------------------------------------------------")
    answersFinal = [item["answer"] for item in answers_old if "answer" in item]
    print("Final Answers:", answersFinal)
    created_at = [item["created_at"] for item in answers_old if "created_at" in item][0]
    print("Created at:", created_at)
    url = f"{BASE_URL}{STORE_QUESTION}"
    # headers: auth + company
    headers = {
        "Authorization": f"{session_data['token_type']} {session_data['token']}",
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(
            session_data['company_id']),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # base payload: company_id + user_id in the JSON body
    payload = {
        "company_id": session_data["company_id"],
        "user_id": session_data["user_id"],
        "created_at": created_at
    }

    # Now for each question, include:
    #   question_id_{i}   -> the real question ID
    # plus one of:
    #   emoji_rating_{i}
    #   binary_answer_{i}
    #   open_ended_answer_{i}
    #   nps_style_rating{i}
    for idx, q in enumerate(questions_old, start=1):
        # print("Processing Q:", q)
        ans = answersFinal[idx - 1]
        if ans is None:
            continue  # skip unanswered

        # 1) tell the backend which question this is
        payload[f"question_id_{idx}"] = q["id"]

        # 2) send the right field for its type
        if q["type"] == "scaled":
            payload[f"emoji_rating_{idx}"] = ans
        elif q["type"] == "binary":
            payload[f"binary_answer_{idx}"] = ans
        elif q["type"] == "open":
            payload[f"open_ended_answer_{idx}"] = ans
        elif q["type"] == "nps":
            # note: your teammate’s PHP checks for "nps_style_rating{index}"
            payload[f"nps_style_rating{idx}"] = ans

    # fire the request
    print("payload of offline: ", payload)
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error submitting offline response: {e}")
        return False
    
    if resp.status_code == 200:
        data = resp.json()
        print("Submitted successfully:", data)
        return True
    else:
        print(f"Error {resp.status_code}: {resp.text}")
        return False


def sync_offline_responses():
    questions_dir = r"C:\Pulse\settings\questions"
    responses_dir = r"C:\Pulse\settings\responses"

    # Ensure dirs exist
    os.makedirs(questions_dir, exist_ok=True)
    os.makedirs(responses_dir, exist_ok=True)

    # Get filenames without extensions
    question_files = {f[:-4] for f in os.listdir(questions_dir) if f.endswith(".txt")}
    response_files = {f.replace("-response", "")[:-4] for f in os.listdir(responses_dir) if f.endswith(".txt")}

    # Find common dates between questions and responses
    common_dates = question_files.intersection(response_files)
    print("Common dates for offline submission:", common_dates)
    for date_str in common_dates:
        q_file = os.path.join(questions_dir, f"{date_str}.txt")
        r_file = os.path.join(responses_dir, f"{date_str}-response.txt")

        try:
            # Check if response file is a marker file (starts with "Submitted:")
            # Marker files are created after successful submission and should be skipped
            with open(r_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("Submitted:"):
                    logging.info(f"Skipping {date_str} - already submitted (marker file found)")
                    continue
            
            # Load content (both files should be JSON)
            with open(q_file, "r", encoding="utf-8") as f:
                questions_old = json.load(f)
            with open(r_file, "r", encoding="utf-8") as f:
                answers_old = json.load(f)

            logging.info(f"Processing offline data for {date_str}")

            # Submit to API
            success = submit_offline_to_api(q_file, r_file, date_str)

            if success:
                # Delete both files after successful submission
                os.remove(q_file)
                os.remove(r_file)
                print(f"Submitted and deleted {q_file} & {r_file}")
                SystemExit
                sys.exit(0)
                
            else:
                print(f"Submission failed for {date_str}, keeping files.")
        except Exception as e:
            print(f"Error processing {date_str}: {e}")


def run_sync_in_background():
    """Start offline sync in background thread with error handling."""
    def safe_sync():
        try:
            sync_offline_responses()
        except Exception as e:
            logging.error(f"Error in offline sync thread: {e}\n{traceback.format_exc()}")
    
    thread = threading.Thread(target=safe_sync, daemon=True)
    thread.start()
    logging.info("Offline sync started in background")
print("---------------------------------------------------------")
#main conditions are here now

if check_internet==0:
    # Internet available
    logging.info("Internet connection available")
    if os.path.exists(response_file_of_today):
        # Check if it's a marker file or actual JSON response
        try:
            with open(response_file_of_today, "r", encoding="utf-8") as f:
                first_char = f.read(1)
            if first_char in ['{', '[']:
                # It's a JSON response file - means form was filled offline
                # Check if questions file exists to submit it
                today_str = datetime.today().strftime("%Y-%m-%d")
                questions_dir = r"C:\Pulse\settings\questions"
                today_questions_file = os.path.join(questions_dir, f"{today_str}.txt")
                if os.path.exists(today_questions_file):
                    # Offline response exists - silently submit it
                    logging.info("Offline response found - silently submitting to API")
                    print("Offline response found. Submitting silently...")
                    try:
                        success = submit_offline_to_api(today_questions_file, response_file_of_today, today_str)
                        if success:
                            os.remove(today_questions_file)
                            os.remove(response_file_of_today)
                            logging.info("Offline response submitted successfully - files deleted")
                            print("Offline response submitted successfully")
                            show = 0
                            run_sync_in_background()
                        else:
                            logging.warning("Failed to submit offline response, will show form")
                            # Continue to show form if submission failed
                    except Exception as e:
                        logging.error(f"Error submitting offline response: {e}\n{traceback.format_exc()}")
                        # Continue to show form if error occurred
                else:
                    # Response file exists but no questions file - treat as already submitted
                    logging.info("Response file exists but no questions file - form already submitted")
                    show = 0
                    run_sync_in_background()
            else:
                # It's a marker file (starts with "Submitted:") - form already submitted
                logging.info("Response file is marker file - form already submitted today")
                print("response already locally available so form not to be shown")
                show = 0
                run_sync_in_background()
        except Exception as e:
            logging.error(f"Error checking response file: {e}")
            # If we can't read the file, continue to check survey status
    else:
        # No response file exists - check if survey is open
        logging.info("No response file found - checking if survey is open")
        print("internet available and no response available for the day ")
        show=showform()
        if show==1:
            print("survey is open")
        elif show==0:
            logging.info("Survey period has ended - exiting")
            time.sleep(20)
            print("survey period has ended")
            SystemExit
            sys.exit(0)
else:
    # No internet - offline mode
    logging.info("No internet connection - checking offline mode")
    if os.path.exists(response_file_of_today):
        # Get file modification time
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(response_file_of_today))
        current_time = datetime.now()

        # Calculate time difference
        time_diff = current_time - file_mod_time
        hours_diff = time_diff.total_seconds() / 3600

        if hours_diff < 24:
            logging.info(f"Response file found ({hours_diff:.2f} hours old) - form already submitted")
            print(f"Response file found ({hours_diff:.2f} hours old). Form already submitted within 24 hours.")
            show = 0
            SystemExit
            sys.exit(0)
            
        else:
            logging.info(f"Response file is older than 24 hours ({hours_diff:.2f} hrs) - allowing offline form")
            print(f"Response file is older than 24 hours ({hours_diff:.2f} hrs). Showing form in offline mode.")
            show = 1  # allow offline form
    else:
        # No response file - check if questions file exists before showing offline form
        today_str = datetime.today().strftime("%Y-%m-%d")
        questions_dir = r"C:\Pulse\settings\questions"
        questions_file = os.path.join(questions_dir, f"{today_str}.txt")
        
        if os.path.exists(questions_file):
            logging.info("No response file but questions file exists - showing offline form")
            print("No internet and no response available for the day. Showing offline form.")
            show = 1  # allow offline form
        else:
            logging.info("No response file and no questions file - cannot show offline form")
            print("No internet, no response file, and no questions file available. Cannot show form.")
            show = 0  # cannot show form - exit
            # Note: Will exit later in the code after root is created

# survey = None
# if check_internet == 0:
#     survey = get_questions_dict()
#
#
#
#
#
# print("---------------------------------------------------------")
# #print("survey data structure:", survey)
#
# print("Survey data:", survey)
#
# print("---------------------------------------------------------")
# if survey:
#     # iterate over every question in the returned order
#     for q_id in survey['ids']:
#         q = survey['by_id'][q_id]
#         print(f"Q_id({q_id}): {q['name']}  (type={q['type']})")
# else:
#     print("No survey data available. online")



def save_responses_locally(target_date=None):
    """
    Save user responses to local file if API is not available.
    File is saved in C:\Pulse\settings\responses\YYYY-MM-DD-response.txt
    """

    # Use today's date if not provided
    if target_date is None:
        target_date = datetime.today().strftime("%Y-%m-%d")
    current_time = datetime.now()
    # Format: 2025-09-21T15:34:56.123Z
    created_at = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    # Ensure folder exists
    save_dir = r"C:\Pulse\settings\responses"
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, f"{target_date}-response.txt")

    # Build local payload similar to API
    local_payload = []
    for idx, q in enumerate(questions, start=1):
        ans = answers[idx-1]
        if ans is None:
            continue  # skip unanswered

        record = {
            "question_id": q["id"],
            "type": q["type"],
            "answer": ans,
            "question": q["question"]
        }
        local_payload.append(record)
    local_payload.append({"created_at": created_at})
    # Save as JSON
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(local_payload, f, indent=4, ensure_ascii=False)

    print(f"Responses saved locally to: {file_path}")
    return True




import os
from datetime import datetime

def submit_to_api_or_local():
    url = f"{BASE_URL}{STORE_QUESTION}"
    headers = {
        "Authorization": f"{session_data['token_type']} {session_data['token']}",
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(session_data['company_id']),
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    print("-------------------------------------------------")
    print("Questions in online:", questions)
    print("-------------------------------------------------")
    print("Answers in online:", answers)

    current_time = datetime.now()
    # Format: 2025-09-21T15:34:56.123Z
    created_at = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    print("Current time in user's timezone:", created_at)

    payload = {
        "Company-Id": str(session_data['active_company_id']) if 'active_company_id' in session_data else str(session_data['company_id']),
        "user_id":    session_data["user_id"],
        "created_at": created_at
    }

    for idx, q in enumerate(questions, start=1):
        ans = answers[idx-1]
        if ans is None:
            continue

        payload[f"question_id_{idx}"] = q["id"]

        if q["type"] == "scaled":
            payload[f"emoji_rating_{idx}"] = ans
        elif q["type"] == "binary":
            payload[f"binary_answer_{idx}"] = ans
        elif q["type"] == "open":
            payload[f"open_ended_answer_{idx}"] = ans
        elif q["type"] == "nps":
            payload[f"nps_style_rating{idx}"] = ans
        
    print("Payload of online: ", payload)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print("Submitted successfully:", data)

            # Delete today's question file after successful submission
            save_dir = r"C:\Pulse\settings\questions"
            today_str = datetime.now().strftime("%Y-%m-%d")
            question_file = os.path.join(save_dir, f"{today_str}.txt")

            if os.path.exists(question_file):
                os.remove(question_file)
                print(f"Deleted local question file: {question_file}")

            return True
        else:
            print(f"Error {resp.status_code}: {resp.text}")
            # Save locally if server error
            save_responses_locally()
            return True

    except requests.RequestException as e:
        print("Network error:", e)
        # Save locally if network unavailable
        save_responses_locally()
        return True



# Disable closing via Alt+F4 using low-level hook
def block_keys():
    """Block keyboard shortcuts with proper error handling."""
    def on_press(e):
        try:
            if e.name == 'f4' and keyboard.is_pressed('alt'): #nhi chlta
                return False
            if e.name == 'esc' and keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift'):  #nhi chalta
                return False
            if e.name == 'tab' and keyboard.is_pressed('alt'):  #nhi chlta
                return False
            if e.name == 'windows':
                return False
            if keyboard.is_pressed('s') and keyboard.is_pressed('c') and keyboard.is_pressed('i') and e.name == 't': # ye chalta hai 
                logging.info("Admin shortcut detected. Exiting.")
                try:
                    stop_block_exe()
                    unmute_system()
                except Exception as ex:
                    logging.error(f"Error during admin exit: {ex}")
                finally:
                    os._exit(0)  # Secret exit
                    
            return True
        except Exception as ex:
            logging.error(f"Error in block_keys handler: {ex}")
            return True  # Allow key if handler fails

    try:
        keyboard.hook(on_press)
        logging.info("Keyboard blocking enabled")
    except Exception as e:
        logging.error(f"Failed to enable keyboard blocking: {e}\n{traceback.format_exc()}")



# Prevent Task Manager (Warning: Not very reliable with Python only) nhi chalta 
def kill_task_manager():
    """Kill Task Manager with proper error handling."""
    while True:
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and "Taskmgr.exe" in proc.info['name']:
                        proc.kill()
                        logging.debug("Task Manager blocked")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass  # Process already gone or access denied
                except Exception as e:
                    logging.warning(f"Error checking process: {e}")
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Fatal error in kill_task_manager: {e}\n{traceback.format_exc()}")
            time.sleep(5)  # Wait longer on error



# if check_internet == 0:
#     survey = get_questions_dict()
#
# if survey:
    # iterate over every question in the returned order
    # for q_id in survey['ids']:
    #     q = survey['by_id'][q_id]
    #     print(f"Q_id({q_id}): {q['name']}  (type={q['type']})")
# else:
#     print("Error", "Failed to fetch survey questions online, trying offline")



# Only load questions if we're actually going to show the form
survey = None
if show != 0:  # Only load questions if form will be shown
    if check_internet==0:
        survey = get_questions_dict()

        if survey:
            # Build your local `questions` list from the API data:
            print("Building questions from API data...")
            questions = []
            for api_id in survey['ids']:
                api_q = survey['by_id'][api_id]
                # map the API's `type` field into your UI types:
                if api_q['type'] == 'scale':
                    q_type = 'scaled'
                elif api_q['type'] == 'nps-style':
                    q_type = 'nps'
                elif api_q['type'] in ('boolean', 'binary'):
                    q_type = 'binary'
                else:
                    q_type = 'open'

                questions.append({
                    "id":       api_id,            # the true question ID
                    "type":     q_type,            # one of 'scaled','nps','binary','open'
                    "question": api_q['name']      # the text to display
                })
            target_date = datetime.today().strftime("%Y-%m-%d")
            save_dir = r"C:\Pulse\settings\questions"
            os.makedirs(save_dir, exist_ok=True)

            file_path = os.path.join(save_dir, f"{target_date}.txt")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(questions, f, indent=4, ensure_ascii=False)
        else:
            print("Error", "No survey questions available online")
            # If no questions available online and we need to show form, set show=0
            show = 0

    else:
        # Load questions from today's file (offline mode)
        print("Loading questions from today's offline file...")
        save_dir = r"C:\Pulse\settings\questions"
        today_str = datetime.today().strftime("%Y-%m-%d")
        file_path = os.path.join(save_dir, f"{today_str}.txt")

        if not os.path.exists(file_path):
            # No questions file available offline - exit gracefully
            logging.warning(f"No offline questions file found for today: {file_path}")
            print("no questions for today available offline")
            show = 0  # Set show=0, will exit later after root is created
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    questions = json.load(f)
                    print(questions)
                except json.JSONDecodeError:
                    # messagebox.showerror("Error", f"Failed to parse questions file: {file_path}. Exiting.")
                    print("no questions avaible,error failed to parse qestion file")
                    show = 0  # Set show=0, will exit later
else:
    # show == 0, so we don't need to load questions
    logging.info("Form will not be shown (show=0), skipping question loading")
    questions = []  # Set empty list to prevent errors


    
    
# Only check questions length if we're actually going to show the form
if show != 0 and len(questions) == 0:
    logging.warning("No valid questions found and form needs to be shown. Exiting.")
    print("No valid questions found. Exiting. after 8 sec")
    time.sleep(10)
    # root doesn't exist yet at this point, so just exit
    sys.exit(1)
    SystemExit
elif show == 0:
    # Form won't be shown, so questions length doesn't matter
    logging.info("Form will not be shown (show=0), skipping questions validation")
    
# Now that `questions` is dynamic:
total_questions = len(questions) if questions else 0
answers   = [None] * len(questions) if questions else []
current_q = 0
dot_labels = []  # store dot labels

# Only create UI if form will be shown
if show != 0 and total_questions > 0:
    # Modern Pulse Survey UI - Updated Layout

    root = Tk()
    root.title("Pulse Survey Form")
    root.attributes("-fullscreen", True)
    root.configure(bg="#F5F7FA")  # Light background

    # Force window to front after launch
    root.after(3000, lambda: bring_to_front(root))

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Main card dimensions - smaller, centered
    card_width = int(screen_width * 0.5)  # 50% instead of 60%
    card_height = int(screen_height * 0.65)  # 65% height
    x0 = (screen_width - card_width) // 2
    y0 = (screen_height - card_height) // 2

    # Subtle shadow
    shadow_offset = 8
    shadow_frame = ctk.CTkFrame(
        root,
        width=card_width,
        height=card_height,
        fg_color="#E0E0E0",
        corner_radius=20
    )
    shadow_frame.place(x=x0 + shadow_offset, y=y0 + shadow_offset)

    # Main white card
    frame = ctk.CTkFrame(
        root,
        width=card_width,
        height=card_height,
        fg_color="white",
        corner_radius=20,
        border_width=0
    )
    frame.place(x=x0, y=y0)

    # Track interaction
    interacted = [False] * len(questions)
    answers = [None] * len(questions)
    current_q = 0

    # Modern fonts
    header_font = ("Segoe UI", 18, "bold")
    subheader_font = ("Segoe UI", 13)
    question_font = ("Segoe UI", 20, "bold")
    button_font = ("Segoe UI", 12)
    small_font = ("Segoe UI", 11)

    # ===== TOP HEADER SECTION =====
    # App icon (top-left)
    IMAGE_PATH = r"C:\Pulse\settings\media"
    try:
        icon_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(IMAGE_PATH, "logo.png")),
            size=(35, 50)
        )
        icon_label = ctk.CTkLabel(frame, image=icon_img, text="")
        icon_label.place(x=30, y=25)
    except:
        # Fallback to emoji
        icon_label = ctk.CTkLabel(frame, text="⭐", font=("Segoe UI", 24))
        icon_label.place(x=30, y=20)

    # Title: "Daily Pulse"
    title_label = ctk.CTkLabel(
        frame,
        text="Daily Pulse",
        font=header_font,
        text_color="purple"
    )
    title_label.place(x=70, y=28)



    import tkinter as tk
    import customtkinter as ctk

    # --- assume these exist in your code ---
    # frame = your CTkFrame(...)
    # subheader_font = ("Segoe UI", 12)   # example, use your subheader_font
    # user_name = session_data["user_name"]

    # create text widget WITHOUT bg argument
    greeting = tk.Text(
        frame,
        height=2,
        width=30,                # adjust if needed
        borderwidth=0,
        highlightthickness=0
    )

    # try to get a sensible background color from the CTkFrame

    bg_color = None
    for key in ("fg_color", "bg", "background"):
        try:
            bg_color = frame.cget(key)
            if bg_color:
                break
        except Exception:
            bg_color = None

    # fallback if nothing found
    if not bg_color:
        bg_color = "#ffffff"   # or choose another default matching your theme

    # apply background in a way compatible with tkinter
    try:
        greeting.configure(background=bg_color)
    except Exception:
        try:
            greeting.configure(bg=bg_color)
        except Exception:
            pass  # if both fail, leave default — it will still show

    # configure tags (use your real subheader_font variable)
    greeting.tag_configure("normal", font=subheader_font, foreground="gray")
    greeting.tag_configure("bold", font=(subheader_font[0], subheader_font[1], "bold"), foreground="gray")

    # insert text and lock widget
    greeting.insert("end", "Hi ", "normal")
    greeting.insert("end", user_name, "bold")
    greeting.insert("end", ", let's check in!", "normal")
    greeting.config(state="disabled")

    # place exactly as you used to
    greeting.place(x=70, y=53)



    # Greeting text
    # user_name = session_data["user_name"]
    # greeting_label = ctk.CTkLabel(
    #     frame,
    #     text=f"Hi {user_name}, let's check in!",
    #     font=subheader_font,
    #     text_color="gray"
    # )
    # greeting_label.place(x=70, y=53)

    # Question progress (top-left under greeting)
    question_num_label = ctk.CTkLabel(
        frame,
        text="",
        text_color="gray",
        font=small_font
    )
    question_num_label.place(x=30, y=95)

    # Percentage (top-right under greeting)
    question_percentage_label = ctk.CTkLabel(
        frame,
        text="",
        text_color="gray",
        font=small_font
    )
    question_percentage_label.place(x=card_width - 70, y=95)

    # Progress bar (centered, thin)
    progress_bar = ctk.CTkProgressBar(
        frame,
        width=card_width - 60,
        height=4,
        corner_radius=2,
        progress_color="purple",
        fg_color="#E8E8E8"
    )
    progress_bar.place(x=30, y=125)
    if total_questions > 0:
        progress_bar.set((current_q + 1) / total_questions)
    else:
        progress_bar.set(0)
else:
    # Form won't be shown - create minimal root for cleanup
    root = Tk()
    root.withdraw()  # Hide the window
    root.title("Pulse Survey Form")
    # Set dummy values to prevent errors
    frame = None
    question_num_label = None
    question_percentage_label = None
    progress_bar = None
    card_width = 0
    card_height = 0
    # Set dummy UI elements to prevent errors
    question_label = None
    answer_frame = None
    back_btn = None
    next_btn = None
    submit_btn = None
    dot_frame = None
    dot_labels = []

# Only create UI elements if form will be shown
if show != 0 and total_questions > 0:
    # ===== QUESTION SECTION =====
    question_label = ctk.CTkLabel(
        frame,
        text="",
        text_color="#2F2D2D",
        font=question_font,
        wraplength=card_width - 80,
        justify="center"
    )
    question_label.place(relx=0.5, y=180, anchor="center")

    # Answer frame
    answer_frame = ctk.CTkFrame(frame, fg_color="transparent")
    answer_frame.place(relx=0.5, rely=0.6, anchor="center")

    # ===== BOTTOM NAVIGATION =====
    # Back button
    back_btn = ctk.CTkButton(
        frame,
        text="← Back",
        fg_color="transparent",
        text_color="gray",
        hover_color="#F5F5F5",
        corner_radius=8,
        font=button_font,
        width=100,
        height=40,
        border_width=0
    )
    back_btn.place(x=30, y=card_height - 70)

    button_X = card_width - 130
    button_Y = card_height - 70
    # Next button
    next_btn = ctk.CTkButton(
        frame,
        text="Next →",
        fg_color="#E8E8E8",
        text_color="gray",
        hover_color="purple",
        corner_radius=8,
        font=button_font,
        width=100,
        height=40
    )

    def on_hover_next(event):
        if next_btn.cget("fg_color") == "purple":
            next_btn.configure(text_color="white")
        
    def on_leave_next(event):
        if next_btn.cget("fg_color") == "#E8E8E8":
            next_btn.configure(text_color="gray")

    next_btn.bind("<Enter>", on_hover_next)
    next_btn.bind("<Leave>", on_leave_next)
    next_btn.place(x=button_X, y=button_Y)

    submit_active = False
    # Submit button
    submit_btn = ctk.CTkButton(
        frame,
        text="Submit",
        fg_color="#E8E8E8",
        text_color="gray",
        hover_color="#228B22",
        corner_radius=8,
        font=button_font,
        width=100,
        height=40
    )

    def on_hover_submit(event):
        if submit_active:
            submit_btn.configure(text_color="white")

    def on_leave_submit(event):
        if submit_active:
            submit_btn.configure(text_color="gray")

    submit_btn.bind("<Enter>", on_hover_submit)
    submit_btn.bind("<Leave>", on_leave_submit)
    submit_btn.place(x=button_X, y=button_Y)

    #Snooze button only on first question
    if current_q == 0 and not os.path.exists(SNOOZE_FILE):
        #Load the image for the snooze button
        IMAGE_PATH = r"C:\Pulse\settings\media"

        snooze_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(IMAGE_PATH, "snooze_icon.png")),
            dark_image=Image.open(os.path.join(IMAGE_PATH, "snooze_icon.png")),
            size=(40, 40)  # Adjust icon size
        )

        #Snooze button
        snooze_btn = ctk.CTkButton(
            frame,
            text="",                 # No text
            image=snooze_img,        # Image only
            corner_radius=10,
            width=40,    # smaller width
            height=40,   # smaller height
            border_width=0,          # No border
            fg_color="white",
            hover_color= "white",
            command=show_snooze_popup
        )

        # Position Snooze button relative to Next button
        snooze_btn.place(x = button_X- 40, y = button_Y + 43 , anchor='s') 
        snooze_btn.custom_tag = "SNOOZE_BUTTON"

    # Later, when removing:
    else:
        for widget in frame.place_slaves():
            if getattr(widget, "custom_tag", None) == "SNOOZE_BUTTON":
                widget.place_forget()

    # Snooze/Remind button (centered at bottom)
    # snooze_label = ctk.CTkLabel(
    #     frame,
    #     text="Remind me in 2 hours",
    #     text_color="gray",
    #     font=("Segoe UI", 11),
    #     cursor="hand2"
    # )
    # snooze_label.place(relx=0.5, y=card_height - 35, anchor="center")

    # def on_snooze_click(event):
    #     show_snooze_popup()

    # snooze_label.bind("<Button-1>", on_snooze_click)

    # Page dots (hidden in minimal design, but keeping for compatibility)
    dot_frame = ctk.CTkFrame(frame, fg_color="transparent")
    dot_labels = []
    # keep_window_on_top will be called only if form is actually shown (moved to start logic)

# Variables (needed for form functions even if not showing)
scaled_var = IntVar()
binary_var = StringVar()
open_var = StringVar()
nps_var = IntVar()

def clear_frame(f):
    if f is None:
        return
    for widget in f.winfo_children():
        widget.destroy()

def save_current_answer():
    q = questions[current_q]
    if q["type"] == "scaled":
        answers[current_q] = scaled_var.get() if interacted[current_q] else None
    elif q["type"] == "nps":
        answers[current_q] = nps_var.get() if interacted[current_q] else None
    elif q["type"] == "binary":
        val = binary_var.get()
        answers[current_q] = val if val else None
    elif q["type"] == "open":
        val = open_var.get()
        answers[current_q] = val if val.strip() and val.strip().lower() != "answer here.." else None

def render_question():
    global current_q
    # Only render if UI elements exist (form is being shown)
    if show == 0 or total_questions == 0 or answer_frame is None:
        return
    
    clear_frame(answer_frame)
    
    q = questions[current_q]
    if question_num_label is not None:
        question_num_label.configure(text=f"Question {current_q + 1} of {total_questions}")
    if question_percentage_label is not None:
        question_percentage_label.configure(text=f"{int((current_q + 1) / total_questions * 100)}%")
    if progress_bar is not None and total_questions > 0:
        progress_bar.set((current_q + 1) / total_questions)
    if question_label is not None:
        question_label.configure(text=q["question"])
    
    # ===== SCALED QUESTION =====
    if q["type"] == "scaled":
        scaled_var.set(answers[current_q] or 0)
        
        IMAGE_FOLDER = r"C:\Pulse\settings\media"
        image_paths = [
            os.path.join(IMAGE_FOLDER, "exhausted.png"),
            os.path.join(IMAGE_FOLDER, "tired.png"),
            os.path.join(IMAGE_FOLDER, "neutral.png"),
            os.path.join(IMAGE_FOLDER, "energized.png"),
            os.path.join(IMAGE_FOLDER, "high_energy.png")
        ]
        labels = ["Exhausted", "Low Level", "Neutral", "Energized", "High Energy"]
        emoji_buttons = []
        
        try:
            loaded_images = [
                ctk.CTkImage(
                    light_image=Image.open(path),
                    size=(50, 50)
                ) for path in image_paths
            ]
        except:
            loaded_images = [None] * 5
        
        def select(val):
            scaled_var.set(val)
            answers[current_q] = val
            interacted[current_q] = True
            
            for idx, btn in enumerate(emoji_buttons, 1):
                if idx == val:
                    btn.configure(fg_color="purple", border_color="purple", text_color="white")
                else:
                    btn.configure(fg_color="white", border_color="#E0E0E0", text_color="black")
            
            next_btn.configure(fg_color="purple", text_color="white")
            submit_btn.configure(fg_color="#228B22", text_color="white")
            submit_active = True
        
        # Create horizontal layout
        options_frame = ctk.CTkFrame(answer_frame, fg_color="transparent")
        options_frame.pack()
        
        for i in range(1, 6):
            selected = scaled_var.get() == i
            
            btn_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
            btn_frame.grid(row=0, column=i-1, padx=8)
            
            btn = ctk.CTkButton(
                btn_frame,
                image=loaded_images[i-1] if loaded_images[i-1] else None,
                text="" if loaded_images[i-1] else labels[i-1][:1],
                width=90,
                height=90,
                fg_color="purple" if selected else "white",
                border_width=2,
                border_color="purple" if selected else "#E0E0E0",
                hover_color="#F0F0F0",
                corner_radius=12,
                command=lambda val=i: select(val)
            )
            btn.pack()
            emoji_buttons.append(btn)
            
            lbl = ctk.CTkLabel(
                btn_frame,
                text=labels[i-1],
                text_color="black",
                font=("Segoe UI", 11)
            )
            lbl.pack(pady=(5, 0))
    
    # ===== BINARY QUESTION =====
    elif q["type"] == "binary":
        binary_var.set(answers[current_q] or "")
        
        IMAGE_FOLDER = r"C:\Pulse\settings\media"
        try:
            thumbs_up_img = ctk.CTkImage(
                light_image=Image.open(os.path.join(IMAGE_FOLDER, "thumbsup.png")),
                size=(60, 60)
            )
            thumbs_down_img = ctk.CTkImage(
                light_image=Image.open(os.path.join(IMAGE_FOLDER, "thumbsdown.png")),
                size=(60, 60)
            )
        except:
            thumbs_up_img = None
            thumbs_down_img = None
        
        def select_yes():
            binary_var.set("Yes")
            answers[current_q] = "Yes"
            yes_btn.configure(fg_color="purple", text_color="white", border_color="purple")
            no_btn.configure(fg_color="white", text_color="black", border_color="#E0E0E0")
            next_btn.configure(fg_color="purple", text_color="white")
            submit_btn.configure(fg_color="#228B22", text_color="white")
            submit_active = True
        
        def select_no():
            binary_var.set("No")
            answers[current_q] = "No"
            no_btn.configure(fg_color="purple", text_color="white", border_color="purple")
            yes_btn.configure(fg_color="white", text_color="black", border_color="#E0E0E0")
            next_btn.configure(fg_color="purple", text_color="white")
            submit_btn.configure(fg_color="#228B22", text_color="white")
            submit_active = True
        
        yes_btn = ctk.CTkButton(
            answer_frame,
            text="Yes",
            font=("Segoe UI", 16),
            image=thumbs_up_img,
            compound="top",
            fg_color="white",
            border_color="#E0E0E0",
            border_width=2,
            text_color="black",
            hover_color="#F5F5F5",
            corner_radius=12,
            width=160,
            height=140,
            command=select_yes
        )
        
        no_btn = ctk.CTkButton(
            answer_frame,
            text="No",
            font=("Segoe UI", 16),
            image=thumbs_down_img,
            compound="top",
            fg_color="white",
            border_color="#E0E0E0",
            border_width=2,
            text_color="black",
            hover_color="#F5F5F5",
            corner_radius=12,
            width=160,
            height=140,
            command=select_no
        )
        
        yes_btn.grid(row=0, column=0, padx=15)
        no_btn.grid(row=0, column=1, padx=15)
        
        if binary_var.get() == "Yes":
            select_yes()
        elif binary_var.get() == "No":
            select_no()
    
    # ===== OPEN QUESTION =====
    elif q["type"] == "open":
        open_var.set(answers[current_q] or "")
        
        entry = ctk.CTkEntry(
            answer_frame,
            textvariable=open_var,
            width=400,
            height=50,
            fg_color="#F8F8F8",
            text_color="black",
            corner_radius=10,
            border_width=2,
            border_color="#E0E0E0",
            placeholder_text="Type your answer here..."
        )
        
        def on_entry_change(*args):
            if open_var.get().strip():
                answers[current_q] = open_var.get()
                interacted[current_q] = True
                next_btn.configure(fg_color="purple", text_color="white")
                submit_btn.configure(fg_color="#228B22", text_color="white")
                submit_active = True
        
        open_var.trace("w", on_entry_change)
        entry.pack(pady=20)
    
    # ===== NPS QUESTION =====
    elif q["type"] == "nps":
        nps_var.set(answers[current_q] or 0)
        
        slider_frame = ctk.CTkFrame(answer_frame, fg_color="transparent")
        slider_frame.pack(pady=20)
        
        def on_slider_change(value):
            answers[current_q] = int(value)
            interacted[current_q] = True
            next_btn.configure(fg_color="purple", text_color="white")
            submit_btn.configure(fg_color="#228B22", text_color="white")
            submit_active = True
        
        slider = ctk.CTkSlider(
            slider_frame,
            from_=0,
            to=10,
            number_of_steps=10,
            variable=nps_var,
            width=450,
            height=16,
            fg_color="#E8E8E8",
            progress_color="purple",
            button_color="purple",
            button_hover_color="#9370DB",
            command=on_slider_change
        )
        slider.pack()
        
        numbers_frame = ctk.CTkFrame(answer_frame, fg_color="transparent")
        numbers_frame.pack(pady=(10, 0))
        
        for i in range(11):
            ctk.CTkLabel(
                numbers_frame,
                text=str(i),
                text_color="gray",
                font=("Segoe UI", 10)
            ).grid(row=0, column=i, padx=18)
        
        desc_frame = ctk.CTkFrame(answer_frame, fg_color="transparent")
        desc_frame.pack(fill="x", pady=(5, 0))
        
        ctk.CTkLabel(
            desc_frame,
            text="Not at all likely",
            text_color="gray",
            font=small_font
        ).pack(side="left")
        
        ctk.CTkLabel(
            desc_frame,
            text="Extremely likely",
            text_color="gray",
            font=small_font
        ).pack(side="right")
    
    # Button visibility
    if current_q == len(questions) - 1:
        next_btn.place_forget()
        submit_btn.place(x=card_width - 130, y=card_height - 70)
    else:
        submit_btn.place_forget()
        next_btn.place(x=card_width - 130, y=card_height - 70)
    
    # Snooze visibility (only on first question)
    # if current_q == 0 and not os.path.exists(SNOOZE_FILE):
    #     snooze_label.place(relx=0.5, y=card_height - 35, anchor="center")
    # else:
    #     snooze_label.place_forget()
    
    # Back button state
    if current_q == 0:
        back_btn.configure(state="disabled", text_color="#CCCCCC")
    else:
        back_btn.configure(state="normal", text_color="gray")

def next_question():
    global current_q
    save_current_answer()
    if current_q < len(questions) - 1:
        current_q += 1
        render_question()

def prev_question():
    global current_q
    save_current_answer()
    if current_q > 0:
        current_q -= 1
        render_question()

def show_thankyou_screen(duration_ms=5000):
    """Modern thank you screen"""
    thank_frame = ctk.CTkFrame(
        root,
        width=card_width,
        height=card_height,
        fg_color="white",
        corner_radius=20
    )
    thank_frame.place(x=x0, y=y0)
    thank_frame.lift()
    
    # Success icon
    icon_label = ctk.CTkLabel(
        thank_frame,
        text="✓",
        font=("Segoe UI", 64, "bold"),
        text_color="purple"
    )
    icon_label.place(relx=0.5, rely=0.25, anchor="center")
    
    # Heading
    heading = ctk.CTkLabel(
        thank_frame,
        text="Thank You!",
        font=("Segoe UI", 32, "bold"),
        text_color="#2F2D2D"
    )
    heading.place(relx=0.5, rely=0.4, anchor="center")
    
    # Subtitle
    subtitle = ctk.CTkLabel(
        thank_frame,
        text="Your feedback has been submitted successfully",
        font=("Segoe UI", 14),
        text_color="gray"
    )
    subtitle.place(relx=0.5, rely=0.48, anchor="center")
    
    # Summary box
    answered_count = sum(1 for a in answers if a is not None)
    
    summary = ctk.CTkLabel(
        thank_frame,
        text=f"• {answered_count} questions answered\n• Data securely stored\n• Survey complete",
        font=("Segoe UI", 13),
        text_color="#555555",
        justify="left"
    )
    summary.place(relx=0.5, rely=0.62, anchor="center")
    
    def finish_and_exit():
        try:
            # Don't call unmute_system() here - it's already called in submit_form()
            # Just ensure block.exe is stopped (in case it wasn't already)
            stop_block_exe()
        finally:
            root.destroy()#sytem.exit(0)
    
    root.after(duration_ms, finish_and_exit)

def submit_form():
    save_current_answer()
    
    missed_questions = [i + 1 for i, ans in enumerate(answers) if ans is None]
    
    if missed_questions:
        missed_str = ', '.join(map(str, missed_questions))
        messagebox.showwarning(
            "Missing Answers",
            f"You missed answering question(s): {missed_str}"
        )
        return
    
    if check_internet == 0:
        success = submit_to_api_or_local()
    else:
        success = save_responses_locally()
    
    if success:
        # Save detailed responses for reference (optional)
        try:
            with open(r"C:\Pulse\settings\responses.txt", "w") as f:
                for idx, ans in enumerate(answers):
                    f.write(f"Q{idx+1}: {questions[idx]['question']}\nAnswer: {ans}\n\n")
        except Exception as e:
            logging.warning(f"Could not save detailed responses: {e}")
        
        # Note: No marker file needed - response file existence is checked directly
        # If online submission succeeded, response file doesn't exist (wasn't created)
        # If offline submission happened, response file exists as JSON and will be synced when online
        
        stop_block_exe()
        unmute_system()  # Unmute once here
        
        if os.path.exists(SNOOZE_FILE):
            os.remove(SNOOZE_FILE)
        
        # Mark that form was submitted to prevent duplicate unmute calls
        root._form_submitted = True
        
        show_thankyou_screen()
    else:
        messagebox.showerror("Submission Failed", "Could not submit your answers. Please try again.")

# Bind commands (only if UI elements exist)
if show != 0 and total_questions > 0 and back_btn is not None:
    back_btn.configure(command=prev_question)
    next_btn.configure(command=next_question)
    submit_btn.configure(command=submit_form)

# Start logic with comprehensive error handling
try:
    if show == 0:
        time.sleep(3)
        logging.info("Form already filled for today. Exiting.")
        try:
            root.destroy()
        except Exception as e:
            logging.error(f"Error destroying root: {e}")
        sys.exit(0)
    elif is_snoozed():
        logging.info("Snoozed. Exiting.")
        try:
            root.destroy()
        except Exception as e:
            logging.error(f"Error destroying root: {e}")
        sys.exit(0)
    else:
        logging.info("Starting survey...")
        
        try:
            render_question()
        except Exception as e:
            logging.critical(f"Failed to render question: {e}\n{traceback.format_exc()}")
            try:
                messagebox.showerror("Error", "Failed to load survey. Please contact support.")
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass
            sys.exit(1)
        
        # Only start window management and blocking if form is actually showing
        try:
            keep_window_on_top(root, interval=3)
        except Exception as e:
            logging.warning(f"Failed to start keep_window_on_top: {e}")
        
        try:
            block_keys()
        except Exception as e:
            logging.warning(f"Failed to block keys: {e}")
        
        try:
            mute_system()
        except Exception as e:
            logging.warning(f"Failed to mute system: {e}")
        
        try:
            start_block_exe()
        except Exception as e:
            logging.warning(f"Failed to start block.exe: {e}")
        
        try:
            root.mainloop()
        except KeyboardInterrupt:
            logging.info("Interrupted by user")
        except Exception as e:
            logging.critical(f"Fatal error in mainloop: {e}\n{traceback.format_exc()}")
            raise
        finally:
            # Cleanup on exit
            # Note: unmute_system() is already called in submit_form() or finish_and_exit()
            # Only cleanup if we're exiting without submitting (e.g., admin shortcut, error)
            try:
                stop_block_exe()
                # Only unmute if form wasn't submitted (check if form was submitted)
                # If form was submitted, unmute was already called
                # If form wasn't submitted (error/admin exit), we need to unmute here
                if not hasattr(root, '_form_submitted'):
                    unmute_system()
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")
            try:
                root.destroy()
            except Exception:
                pass

except SystemExit:
    logging.info("System exit requested")
    raise
except Exception as e:
    logging.critical(f"Fatal error in main execution: {e}\n{traceback.format_exc()}")
    try:
        stop_block_exe()
        unmute_system()
    except Exception:
        pass
    sys.exit(1)



