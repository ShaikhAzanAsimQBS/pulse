@echo off
REM ============================================
REM PyInstaller Build Script for Pulse Applications
REM Optimized for Windows Stability
REM ============================================

echo Building PulseForm.exe...
pyinstaller --clean ^
    --name=PulseForm ^
    --onefile ^
    --windowed ^
    --noupx ^
    --add-data "C:\Pulse\settings\media;settings\media" ^
    --hidden-import=win32timezone ^
    --hidden-import=win32api ^
    --hidden-import=win32con ^
    --hidden-import=win32gui ^
    --hidden-import=win32com.client ^
    --hidden-import=win32process ^
    --hidden-import=pythoncom ^
    --hidden-import=pywintypes ^
    --hidden-import=comtypes ^
    --hidden-import=comtypes.client ^
    --hidden-import=pycaw ^
    --hidden-import=pycaw.pycaw ^
    --hidden-import=customtkinter ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=cryptography ^
    --hidden-import=cryptography.fernet ^
    --hidden-import=keyboard ^
    --hidden-import=psutil ^
    --hidden-import=requests ^
    --hidden-import=zoneinfo ^
    --hidden-import=tzdata ^
    --collect-submodules=zoneinfo ^
    --collect-all=customtkinter ^
    --collect-all=PIL ^
    --collect-all=pycaw ^
    --collect-all=comtypes ^
    --exclude-module=matplotlib ^
    --exclude-module=numpy ^
    --exclude-module=scipy ^
    --exclude-module=pandas ^
    --exclude-module=IPython ^
    --exclude-module=jupyter ^
    --runtime-tmpdir=. ^
    --log-level=WARN ^
    PulseForm.py

if %ERRORLEVEL% NEQ 0 (
    echo PulseForm.exe build failed!
    pause
    exit /b 1
)

echo.
echo Building auto_launcher.exe...
pyinstaller --clean ^
    --name=auto_launcher ^
    --onefile ^
    --console ^
    --noupx ^
    --hidden-import=psutil ^
    --hidden-import=ctypes ^
    --hidden-import=ctypes.wintypes ^
    --exclude-module=matplotlib ^
    --exclude-module=numpy ^
    --exclude-module=scipy ^
    --exclude-module=pandas ^
    --exclude-module=IPython ^
    --exclude-module=jupyter ^
    --runtime-tmpdir=. ^
    --log-level=WARN ^
    auto_launcher.py

if %ERRORLEVEL% NEQ 0 (
    echo auto_launcher.exe build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build completed successfully!
echo Executables are in: dist\
echo ============================================
pause

