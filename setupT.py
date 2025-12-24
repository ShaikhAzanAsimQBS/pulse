import os
import sys
import shutil
import subprocess
import ctypes
from cryptography.fernet import Fernet
import requests
import customtkinter as ctk
from tkinter import simpledialog, messagebox
import winreg

# -----------------------
# Privilege helpers
# -----------------------
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def relaunch_as_admin():
    """Relaunch current script/exe elevated (shows UAC). Returns True if ShellExecute succeeded."""
    if sys.platform != "win32":
        raise RuntimeError("This helper only works on Windows.")
    # Determine executable & args
    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    else:
        executable = sys.executable  # path to python.exe
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{arg}"' for arg in [script] + sys.argv[1:])
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        return int(ret) > 32
    except Exception as e:
        print("Failed to relaunch elevated:", e)
        return False

# -----------------------
# Paths & utilities
# -----------------------
def get_base_path():
    """Folder of the running exe/script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SETTINGS_FOLDER = r"C:\Pulse\settings"
KEY_FILE = os.path.join(SETTINGS_FOLDER, "secret.key")
LOGIN_FILE = os.path.join(SETTINGS_FOLDER, "logInfo.txt")
SESSION_FILE = os.path.join(SETTINGS_FOLDER, "session.txt")

def ensure_settings_folder():
    os.makedirs(SETTINGS_FOLDER, exist_ok=True)

# -----------------------
# Move media folder (privileged action)
# -----------------------
def move_media_folder():
    base_path = get_base_path()
    source_folder = os.path.join(base_path, "media")
    destination_parent = r"C:\Pulse\settings"
    destination_folder = os.path.join(destination_parent, "media")

    if not os.path.exists(source_folder):
        print("No 'media' folder found, skipping move.")
        return
    os.makedirs(destination_parent, exist_ok=True)
    if os.path.exists(destination_folder):
        try:
            shutil.rmtree(destination_folder)
        except Exception as e:
            print("Failed to remove existing destination media folder:", e)
    try:
        shutil.move(source_folder, destination_folder)
        print(f"Moved media -> {destination_folder}")
    except Exception as e:
        print("Failed to move media folder:", e)

# -----------------------
# ADD TO STARTUP
# -----------------------

def add_to_startup_registry():
    exe_path = os.path.join(os.getcwd(), "PulseForm.exe")

    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, "pulse", 0, winreg.REG_SZ, exe_path)
        print("pulseform.exe successfully added to startup (Registry Method).")
    except Exception as e:
        print(f"Failed to add pulseform.exe to startup: {e}")


def add_to_startup_registry2():
    exe_path = os.path.join(os.getcwd(), "auto_launcher.exe")

    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, "launcher", 0, winreg.REG_SZ, exe_path)
        print("auto_launcher.exe successfully added to startup (Registry Method).")
    except Exception as e:
        print(f"Failed to add auto_launcher.exe to startup: {e}")

# -----------------------
# Task scheduler creation
# -----------------------
# TASK_NAME = "PulseFormTask"

# def task_exists(task_name: str) -> bool:
#     """Return True if task exists."""
#     try:
#         completed = subprocess.run(
#             ['schtasks', '/Query', '/TN', task_name],
#             capture_output=True, text=True, check=False
#         )
#         return completed.returncode == 0
#     except Exception:
#         return False

# def show_msg(title, message, style=0):
#     # style=0: OK only, style=1: OK/Cancel, etc.
#     ctypes.windll.user32.MessageBoxW(0, message, title, style)

# def create_task_every_30min():
#     base_dir = get_base_path()
#     exe_path = os.path.join(base_dir, "PulseForm.exe")
#     exe_quoted = f'"{exe_path}"'

#     cmd = f'schtasks /Create /TN "{TASK_NAME}" /TR {exe_quoted} /SC MINUTE /MO 30 /RL HIGHEST /F'
#     try:
#         completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
#         if completed.returncode == 0:
#             show_msg("Success", "Successfully added to Task Scheduler.", 0)
#         else:
#             error_msg = (
#                 f"Failed to create scheduled task.\n\n"
#                 f"Error: {completed.stderr.strip()}\n\n"
#                 f"Please disable Windows Defender temporarily and run as Administrator."
#             )
#             show_msg("Error", error_msg, 0)
#     except Exception as e:
#         show_msg("Exception", f"Unexpected error: {e}", 0)
        


# def add_defender_exclusion(path):
#     """Add file path to Defender exclusion list via registry."""
#     try:
#         key_path = r"SOFTWARE\Microsoft\Windows Defender\Exclusions\Paths"
#         reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
#         key = winreg.OpenKey(reg, key_path, 0, winreg.KEY_WRITE)
#         winreg.SetValueEx(key, path, 0, winreg.REG_SZ, "")
#         winreg.CloseKey(key)
#         return True
#     except Exception as e:
#         return str(e)


# def add_exclusions():
#     base_dir = get_base_path()
#     files_to_exclude = [
#         os.path.join(base_dir, "PulseForm.exe"),
#         os.path.join(base_dir, "block.exe")
#     ]
#     all_ok, errors = True, []
#     for file in files_to_exclude:
#         result = add_defender_exclusion(file)
#         if result is not True:
#             all_ok = False
#             errors.append(f"{os.path.basename(file)}: {result}")
#     if all_ok:
#         show_msg("Success", "PulseForm.exe and block.exe added to Defender exclusions.", 64)
#     else:
#         error_text = "Some exclusions failed:\n\n" + "\n".join(errors) + \
#                      "\n\nIf Tamper Protection is enabled, please disable it and try again."
#         show_msg("Failure", error_text, 48)







# -----------------------
# Crypto / session helpers (kept mostly as-is)
# -----------------------
def init_crypto():
    ensure_settings_folder()
    if not os.path.exists(KEY_FILE):
        with open(KEY_FILE, "wb") as kf:
            kf.write(Fernet.generate_key())
    with open(KEY_FILE, "rb") as kf:
        key = kf.read()
    return Fernet(key)

cipher_suite = init_crypto()

def encrypt_data(data: str) -> bytes:
    return cipher_suite.encrypt(data.encode())

def decrypt_data_bytes(data_bytes: bytes) -> str:
    return cipher_suite.decrypt(data_bytes).decode()

def save_to_file_encrypted(filename: str, data: str):
    with open(filename, "wb") as f:
        f.write(encrypt_data(data))

def read_from_file_decrypted(filename: str) -> str:
    if not os.path.exists(filename):
        return ""
    try:
        with open(filename, "rb") as f:
            enc = f.read()
        if not enc:
            return ""
        return decrypt_data_bytes(enc)
    except Exception:
        return ""

def clear_files():
    open(LOGIN_FILE, "w").close()
    open(SESSION_FILE, "w").close()

# -----------------------
# Network / login (kept similar)
# -----------------------
BASE_URL = "https://pulse.workamp.net/api/v1"
LOGIN_ENDPOINT = "/auth/login"
session_data = {}

def login(email, password):
    url = f"{BASE_URL}{LOGIN_ENDPOINT}"
    params = {"email": email, "password": password}
    try:
        resp = requests.post(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            print("Login successful.")
            print(data)
            # store expected values (guard with try)
            try:
                session_data['token'] = data['data']['token']
                session_data['token_type'] = data['data']['token_type']
                session_data['user_id'] = data['data']['user']['id'] 
                session_data['company_id'] = data['data']['company']['id']
                session_data['employee_id'] = data['data']['user']['employee']['id']
                session_data['time_zone'] = data['data']['user']['companies'][0]['timezone']
                session_data['user_name'] = data['data']['user']['name']
                print("Extracted session data:", session_data)
            except Exception as e:
                print("Unexpected login response format:", e)
            return data
        else:
            print("Login failed:", resp.status_code, resp.text)
            return None
    except Exception as e:
        print("Network error during login:", e)
        return None

# -----------------------
# GUI (single root, no duplicates)
# -----------------------
def on_hover(event, btn):
    btn.configure(text_color="white", fg_color="#800080")

def on_leave(event, btn):
    btn.configure(text_color="black", fg_color="#d3d3d3")

def show_password_prompt(root):
    password = simpledialog.askstring("Password Required", "Enter password:", show="*", parent=root)
    if password == "shaikh20743":
        clear_files()
        messagebox.showinfo("Success", "Files cleared successfully!", parent=root)
        create_main_page(root)
    else:
        messagebox.showwarning("Error", "Incorrect password!", parent=root)
        create_main_page(root, update_only=True)

def submit_login(root, email_entry, password_entry):
    email = email_entry.get()
    password = password_entry.get()
    if email and password:
        confirm = messagebox.askyesno("Confirm Submission", "Are you sure you want to submit the login details?", parent=root)
        if confirm:
            save_to_file_encrypted(LOGIN_FILE, f"Email: {email}, Password: {password}")
            e, p = parse_login_file()
            print(e)
            print(p)
            login(e, p)
            if not session_data:
                messagebox.showwarning("Error", "Login failed. Please check your credentials.", parent=root)
            else:
                save_to_file_encrypted(SESSION_FILE,
                                       f"Token: {session_data['token']}, UserID: {session_data['user_id']}, TokenType: {session_data['token_type']}, CompanyID: {session_data['company_id']}, EmployeeID: {session_data['employee_id']}, TimeZone: {session_data['time_zone']}, UserName: {session_data['user_name']}")
                messagebox.showinfo("Success", "Login data saved securely!", parent=root)
            create_main_page(root)
    else:
        messagebox.showwarning("Error", "All fields are required.", parent=root)

def parse_login_file():
    content = read_from_file_decrypted(LOGIN_FILE)
    if content:
        try:
            parts = content.split(", ")
            email = parts[0].split(": ")[1]
            password = parts[1].split(": ")[1]
            return email, password
        except Exception:
            return None, None
    return None, None

def parse_session_file():
    content = read_from_file_decrypted(SESSION_FILE)
    if content:
        try:
            parts = content.split(", ")
            token = parts[0].split(": ")[1]
            user_id = parts[1].split(": ")[1]
            token_type = parts[2].split(": ")[1]
            company_id = parts[3].split(": ")[1]
            employee_id = parts[4].split(": ")[1]
            time_zone = parts[5].split(": ")[1]
            user_name = parts[6].split(": ")[1]
            return token, user_id, token_type, company_id, employee_id, time_zone, user_name
        except Exception:
            return (None,)*7
    return (None,)*7

def create_main_page(root, update_only=False):
    for w in root.winfo_children():
        w.destroy()

    # Ensure login/session files exist
    open(LOGIN_FILE, "a").close()
    open(SESSION_FILE, "a").close()

    login_empty = not read_from_file_decrypted(LOGIN_FILE) and not read_from_file_decrypted(SESSION_FILE)

    title = ctk.CTkLabel(root, text="Configuration Screen", font=("Segoe UI", 22, "bold"), text_color="#6A0DAD")
    title.pack(pady=25)

    btn_style = {"width": 220, "height": 40, "corner_radius": 12, "fg_color": "#d3d3d3", "text_color": "black"}

    if update_only:
        update_btn = ctk.CTkButton(root, text="Update", command=lambda: show_password_prompt(root), **btn_style)
        update_btn.pack(pady=12)
        exit_btn = ctk.CTkButton(root, text="Exit", command=root.quit, **btn_style)
        exit_btn.pack(pady=12)
        update_btn.bind("<Enter>", lambda e: on_hover(e, update_btn))
        update_btn.bind("<Leave>", lambda e: on_leave(e, update_btn))
        exit_btn.bind("<Enter>", lambda e: on_hover(e, exit_btn))
        exit_btn.bind("<Leave>", lambda e: on_leave(e, exit_btn))

    elif login_empty:
        login_btn = ctk.CTkButton(root, text="Login", command=lambda: show_login_page(root), **btn_style)
        login_btn.pack(pady=12)
        login_btn.bind("<Enter>", lambda e: on_hover(e, login_btn))
        login_btn.bind("<Leave>", lambda e: on_leave(e, login_btn))
    else:
        update_btn = ctk.CTkButton(root, text="Update", command=lambda: show_password_prompt(root), **btn_style)
        update_btn.pack(pady=16)
        exit_btn = ctk.CTkButton(root, text="Exit", command=root.quit, **btn_style)
        exit_btn.pack(pady=16)
        update_btn.bind("<Enter>", lambda e: on_hover(e, update_btn))
        update_btn.bind("<Leave>", lambda e: on_leave(e, update_btn))
        exit_btn.bind("<Enter>", lambda e: on_hover(e, exit_btn))
        exit_btn.bind("<Leave>", lambda e: on_leave(e, exit_btn))

def show_login_page(root):
    for w in root.winfo_children():
        w.destroy()

    back_btn = ctk.CTkButton(root, text="← Back", command=lambda: create_main_page(root), fg_color="lightgray", text_color="black", corner_radius=12)
    back_btn.place(x=10, y=10)
    back_btn.bind("<Enter>", lambda e: on_hover(e, back_btn))
    back_btn.bind("<Leave>", lambda e: on_leave(e, back_btn))

    title = ctk.CTkLabel(root, text="Login Page", font=("Segoe UI", 18, "bold"), text_color="#6A0DAD")
    title.pack(pady=20)

    ctk.CTkLabel(root, text="Email:", font=("Segoe UI", 13), text_color="black").pack(pady=(5,0))
    email_entry = ctk.CTkEntry(root, width=250, corner_radius=8, fg_color="white", text_color="black", border_color="gray")
    email_entry.pack(pady=5)

    ctk.CTkLabel(root, text="Password:", font=("Segoe UI", 13), text_color="black").pack(pady=(10,0))
    password_entry = ctk.CTkEntry(root, width=250, show="*", corner_radius=8, fg_color="white", text_color="black", border_color="gray")
    password_entry.pack(pady=5)

    submit_btn = ctk.CTkButton(root, text="Submit", command=lambda: submit_login(root, email_entry, password_entry), fg_color="lightgray", text_color="black", corner_radius=12, width=120)
    submit_btn.pack(pady=15)
    submit_btn.bind("<Enter>", lambda e: on_hover(e, submit_btn))
    submit_btn.bind("<Leave>", lambda e: on_leave(e, submit_btn))

# -----------------------
# Main entry
# -----------------------
def main():
    # Request elevation early
    if not is_admin():
        ok = relaunch_as_admin()
        if ok:
            # Elevated process started; exit this non-elevated instance
            sys.exit(0)
        else:
            messagebox.showerror("Admin required", "This installer requires administrative privileges. Exiting.")
            sys.exit(1)

    # Now running elevated — perform privileged setup
    ensure_settings_folder()
    move_media_folder()
    #add_to_startup_registry()
    add_to_startup_registry2()
    # create_task_every_30min()
    # add_exclusions()
    # Start GUI (single root)
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.title("Pulse Form Set Up")
    root.geometry("420x320")
    root.configure(fg_color="white")

    create_main_page(root)
    root.mainloop()

if __name__ == "__main__":
    main()
