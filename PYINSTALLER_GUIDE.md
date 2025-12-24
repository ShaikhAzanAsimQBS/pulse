# PyInstaller Build Guide - Production Ready

## 🎯 Build Commands

### Option 1: Using Batch Script (Windows)
```batch
build_exe.bat
```

### Option 2: Manual Commands

#### PulseForm.exe
```bash
pyinstaller --clean --name=PulseForm --onefile --windowed --noupx --add-data "C:\Pulse\settings\media;settings\media" --hidden-import=win32timezone --hidden-import=win32api --hidden-import=win32con --hidden-import=win32gui --hidden-import=win32com.client --hidden-import=win32process --hidden-import=pythoncom --hidden-import=pywintypes --hidden-import=comtypes --hidden-import=comtypes.client --hidden-import=pycaw --hidden-import=pycaw.pycaw --hidden-import=customtkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=cryptography --hidden-import=cryptography.fernet --hidden-import=keyboard --hidden-import=psutil --hidden-import=requests --hidden-import=zoneinfo --collect-all=customtkinter --collect-all=PIL --collect-all=pycaw --collect-all=comtypes --exclude-module=matplotlib --exclude-module=numpy --exclude-module=scipy --exclude-module=pandas --exclude-module=IPython --exclude-module=jupyter --runtime-tmpdir=. --log-level=WARN PulseForm.py
```

#### auto_launcher.exe
```bash
pyinstaller --clean --name=auto_launcher --onefile --console --noupx --hidden-import=psutil --hidden-import=ctypes --hidden-import=ctypes.wintypes --exclude-module=matplotlib --exclude-module=numpy --exclude-module=scipy --exclude-module=pandas --exclude-module=IPython --exclude-module=jupyter --runtime-tmpdir=. --log-level=WARN auto_launcher.py
```

## 🔧 Key Flags Explained

### Stability Flags
- `--onefile`: Single executable (easier deployment)
- `--noupx`: Disable UPX compression (prevents false positives from antivirus)
- `--windowed`: No console window for GUI app (PulseForm)
- `--console`: Keep console for background service (auto_launcher)
- `--runtime-tmpdir=.`: Extract to current directory (not temp, more stable)

### Import Flags
- `--hidden-import`: Force include modules that PyInstaller might miss
- `--collect-all`: Include all submodules and dependencies
- `--exclude-module`: Remove unnecessary modules (reduces size, faster startup)

### Windows-Specific
- `--add-data`: Include media files (images, icons)
- Hidden imports for Windows API (win32*, comtypes, pycaw)

## 🛡️ Making Executables Less Prone to Windows Killing

### 1. **Use Windows Service (Recommended)**
Convert `auto_launcher.exe` to a Windows Service using `pywin32`:
```python
# Install: pip install pywin32
# Use: python -m win32com.client.makepy
```

### 2. **Registry Startup (Current Method)**
Already implemented in `setupT.py` - ensures auto-start

### 3. **Process Priority**
Add to `auto_launcher.py`:
```python
import psutil
p = psutil.Process()
p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)  # Less likely to be killed
```

### 4. **Anti-Kill Techniques**
- Use `--noupx` flag (already included)
- Sign executables with code signing certificate
- Add to Windows Defender exclusions
- Run with appropriate user permissions

### 5. **Error Recovery**
Already implemented:
- Comprehensive error handling
- Automatic retry logic
- Logging for debugging
- Graceful degradation

## 📋 Pre-Build Checklist

- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Media files exist at `C:\Pulse\settings\media\`
- [ ] Test scripts run successfully as `.py` files
- [ ] No syntax errors or import issues
- [ ] PyInstaller version >= 5.0

## 🧪 Post-Build Testing

1. **Test PulseForm.exe:**
   - Run from different directories
   - Test with/without internet
   - Test offline mode
   - Verify UI displays correctly
   - Check logs for errors

2. **Test auto_launcher.exe:**
   - Run and verify it launches PulseForm.exe
   - Check mutex prevents multiple instances
   - Verify logging works
   - Test error recovery

3. **Integration Testing:**
   - Install both to startup
   - Reboot system
   - Verify both start automatically
   - Check logs after 10 minutes

## ⚠️ Common Issues & Solutions

### Issue: "Failed to execute script"
**Solution:** Check hidden imports, use `--debug=all` to see missing modules

### Issue: Antivirus blocks executable
**Solution:** 
- Use `--noupx` (already included)
- Sign executable with certificate
- Add to antivirus exclusions

### Issue: Executable too large
**Solution:** 
- Use `--exclude-module` for unused libraries
- Consider `--onedir` instead of `--onefile`

### Issue: Missing DLL errors
**Solution:** 
- Use `--collect-all` for problematic packages
- Install Visual C++ Redistributable on target machines

### Issue: Process killed by Windows
**Solution:**
- Run as Windows Service (best)
- Lower process priority
- Add to Windows Defender exclusions
- Ensure proper error handling (already implemented)

## 📦 Requirements File

Create `requirements.txt`:
```
pyinstaller>=5.0
pywin32>=300
pycaw>=20230407
customtkinter>=5.0
Pillow>=10.0
cryptography>=41.0
requests>=2.31
psutil>=5.9
keyboard>=0.13
comtypes>=1.2
```

## 🚀 Deployment Steps

1. Build executables using provided commands
2. Copy `dist\PulseForm.exe` and `dist\auto_launcher.exe` to deployment folder
3. Copy `block.exe` to same folder
4. Copy `C:\Pulse\settings\media\` folder
5. Run `setupT.exe` on target machine for initial setup
6. Verify startup entries in Registry
7. Test on clean Windows installation

