import os
import sys
import time
import shutil
import winreg

# Get the actual directory where the .exe is running
script_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

def remove_from_startup_registry():
    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.DeleteValue(reg_key, "pulse")
        print("pulseform.exe successfully removed from startup (Registry Method).")
    except FileNotFoundError:
        print("pulseform not found in startup registry.")
    except Exception as e:
        print(f"Failed to remove pulseform.exe from startup: {e}")

def remove_from_startup_registry2():
    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.DeleteValue(reg_key, "launcher")
        print("launcher.exe successfully removed from startup (Registry Method).")
    except FileNotFoundError:
        print("launcher not found in startup registry.")
    except Exception as e:
        print(f"Failed to remove launcher.exe from startup: {e}")

def delete_files():
    """Delete tracker.exe and setup2.exe in the same folder as this script"""
    try:
        files_to_delete = ["PulseForm.exe", "setupT.exe","auto_launcher.exe"]
        for file_name in files_to_delete:
            file_path = os.path.join(script_dir, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            else:
                print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Error deleting files: {e}")

def delete_folder():
    """Delete the folder C:\settings_noSS if it exists"""
    folder_path = r"C:\Pulse\settings"
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            print(f"Deleted folder: {folder_path}")
        else:
            print(f"Folder not found: {folder_path}")
    except Exception as e:
        print(f"Error deleting folder: {e}")

# Execute functions
#remove_from_startup_registry()
remove_from_startup_registry2()
#delete_files()
#delete_folder()

# Wait before closing
time.sleep(5)
print("Program closing.")