# CI Test Debugging Guide

## Current Status

We're debugging the "Test embeddable Python backend" step in `.github/workflows/build-windows.yml` which is failing at step #52.

## Recent Improvements Made

### 1. Enhanced Error Logging
- Added comprehensive file verification before starting tests
- Added directory structure logging
- Added stdout/stderr capture to files
- Added process monitoring to detect crashes

### 2. Better Retry Logic
- Increased retry attempts to 30 (up to 60 seconds total)
- Added 2-second intervals between health checks
- Added 3-second initialization delay after process start

### 3. Diagnostic Checks
- Verify Python executable exists
- Verify server.py exists
- Check for config files in parent directory
- Test Python imports before starting server
- Monitor process exit codes

### 4. PowerShell Syntax Fixes
- Fixed environment variable copying to use Process scope
- Improved exit code checking for import test

## Expected Build Structure

After electron-builder runs, the structure should be:
```
release/win-unpacked/
  resources/
    python/
      python_embed/
        python.exe
        (Python embeddable files)
      server.py
    config.default.yaml
    prompts.default.yaml
```

## Test Flow

1. Change directory to `release/win-unpacked/resources/python`
2. Verify files exist
3. Test Python imports
4. Start Python backend process with output redirection
5. Wait for health endpoint (http://127.0.0.1:14242/health)
6. Verify response status is "ok"
7. Clean up process

## Common Failure Points

### 1. Missing Files
- **Symptom**: Test fails immediately with "file not found"
- **Check**: Verify electron-builder copied files correctly
- **Fix**: Check `extraResources` configuration in `electron-builder.config.js`

### 2. Python Import Errors
- **Symptom**: Import test fails
- **Check**: Verify dependencies installed in embeddable Python
- **Fix**: Check `python/requirements.txt` and pip install process

### 3. Server Startup Failure
- **Symptom**: Process exits before health check passes
- **Check**: Review stdout/stderr files in `$env:TEMP`
- **Common causes**:
  - Missing config files
  - Import errors
  - Port already in use
  - BASE_DIR resolution issues

### 4. Health Check Timeout
- **Symptom**: Health checks fail after 30 attempts
- **Check**: Verify server is actually listening on port 14242
- **Fix**: Check server logs, verify PORT environment variable

### 5. BASE_DIR Resolution
- **Issue**: Server.py determines BASE_DIR based on current directory
- **Expected**: When running from `resources/python`, BASE_DIR should be `resources/`
- **Check**: Server logs should show BASE_DIR path

## Debugging Commands

If you need to debug locally:

```powershell
# Navigate to test directory
cd release/win-unpacked/resources/python

# Test Python imports
python_embed\python.exe -c "import sys; import fastapi; import uvicorn; print('OK')"

# Start server manually
$env:USER_DATA_DIR = "$env:TEMP\docusenselm_test"
$env:PORT = "14242"
python_embed\python.exe server.py

# In another terminal, test health
Invoke-WebRequest -Uri "http://127.0.0.1:14242/health"
```

## Next Steps

1. Monitor GitHub Actions workflow run
2. Review stdout/stderr logs from failed test
3. Identify specific failure point
4. Apply targeted fix
5. Re-test until passing

## Files Modified

- `.github/workflows/build-windows.yml` - Enhanced test step with better error handling

