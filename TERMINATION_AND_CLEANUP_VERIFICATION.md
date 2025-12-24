# Termination Detection & _MEI* Folder Cleanup Verification

## ✅ Issues Fixed

### 1. **UnboundLocalError Fixed**
- **Problem:** `_termination_reason` accessed before global declaration
- **Fix:** Added `_termination_reason` to global declaration at start of `main()`
- **Result:** No more errors when handling Ctrl+C or SystemExit

### 2. **Force Kill Detection Working**
- ✅ **Task Manager Kill:** Detected on next startup (lines 542-548 in terminal)
- ✅ **Ctrl+C:** Handled gracefully with proper logging
- ✅ **Heartbeat System:** Working correctly

### 3. **_MEI* Folder Cleanup**

#### Current Behavior:
1. **On Graceful Shutdown (Ctrl+C, normal exit):**
   - Calls `cleanup_temp_folders(force_cleanup=True)`
   - Attempts to clean current process's `_MEI*` folder immediately
   - If folder is locked, skips it (will be cleaned on next startup)

2. **On Force Kill (Task Manager, Antivirus):**
   - Process killed before cleanup runs
   - `_MEI*` folder remains in temp directory
   - **On Next Startup:**
     - Calls `cleanup_temp_folders(force_cleanup=False)`
     - Cleans folders older than 5 minutes
     - Since killed process's folder is now >5 minutes old, it gets cleaned

3. **Cleanup Logic:**
   - Checks folder age (5 minutes threshold)
   - Tests if folder is accessible (not locked)
   - Only deletes if accessible
   - Logs cleanup actions

## 📋 Verification Results

### Test 1: Task Manager Kill ✅
```
2025-12-20 02:51:57 - CRITICAL - PREVIOUS RUN DETECTED AS ABNORMALLY TERMINATED!
2025-12-20 02:51:57 - CRITICAL - Time since last heartbeat: 97.52 seconds
2025-12-20 02:51:57 - CRITICAL - Previous PID: 10072
2025-12-20 02:51:57 - CRITICAL - Likely killed by: OS, Antivirus, or Task Manager
```
**Result:** ✅ Detection working perfectly!

### Test 2: Ctrl+C ✅
```
2025-12-20 02:52:24 - WARNING - Termination signal received: SIGINT
2025-12-20 02:52:24 - INFO - Auto launcher shutting down gracefully...
2025-12-20 02:52:24 - INFO - Cleanup completed
```
**Result:** ✅ Graceful shutdown working (error was fixed)

## 🔧 _MEI* Folder Cleanup Flow

### Scenario 1: Normal Exit (Ctrl+C)
1. User presses Ctrl+C
2. Signal handler called → `_graceful_shutdown = True`
3. `cleanup_on_exit()` called
4. `cleanup_temp_folders(force_cleanup=True)` called
5. Attempts to clean current `_MEI*` folder
6. If successful → folder deleted
7. If locked → skipped (will be cleaned later)

### Scenario 2: Force Kill (Task Manager)
1. Process killed instantly
2. No cleanup code runs
3. `_MEI*` folder remains in temp
4. **Next Startup:**
   - Detects abnormal termination (heartbeat check)
   - Logs critical message
   - Calls `cleanup_temp_folders(force_cleanup=False)`
   - Finds `_MEI*` folder from killed process
   - Checks age: >5 minutes → attempts cleanup
   - If accessible → deletes folder
   - If locked → skips (process might still be cleaning up)

### Scenario 3: Antivirus Kill
1. Same as Task Manager kill
2. Detected on next startup
3. Folder cleaned on next startup (if >5 minutes old)

## ⚠️ Important Notes

### _MEI* Folder Cleanup Limitations:
1. **Immediate Cleanup:** Only works if process exits gracefully
2. **Force Kill:** Folder remains until next startup
3. **5-Minute Threshold:** Folders must be >5 minutes old to be cleaned (safety measure)
4. **Locked Folders:** If folder is locked by another process, it's skipped

### Why 5-Minute Threshold?
- Prevents deleting folders from processes that just started
- Gives killed processes time to fully terminate
- Windows may keep folder locked briefly after process death

### When Will _MEI* Folder Be Deleted?

| Scenario | When Deleted |
|----------|-------------|
| Normal exit (Ctrl+C) | Immediately on exit (if not locked) |
| Force kill (Task Manager) | On next startup (if >5 min old, not locked) |
| Antivirus kill | On next startup (if >5 min old, not locked) |
| Process crash | On next startup (if >5 min old, not locked) |

## 🧪 Testing Checklist

- [x] Task Manager kill detected on next startup
- [x] Ctrl+C handled gracefully
- [x] Heartbeat file system working
- [x] Logs written immediately (flush working)
- [ ] _MEI* folder deleted on graceful exit (needs testing)
- [ ] _MEI* folder deleted on next startup after kill (needs testing)

## 📝 Recommendations

1. **Test _MEI* Cleanup:**
   - Run `auto_launcher.exe`
   - Wait 10+ seconds
   - Kill via Task Manager
   - Wait 5+ minutes
   - Run again
   - Check temp directory - `_MEI*` folder should be gone

2. **Monitor Logs:**
   - Check for "Cleaned up temp folder" messages
   - Check for "locked, skipping" messages
   - Verify cleanup happens on startup

3. **If Folders Still Accumulate:**
   - Reduce 5-minute threshold to 1 minute (more aggressive)
   - Or add periodic cleanup (every hour) in main loop

