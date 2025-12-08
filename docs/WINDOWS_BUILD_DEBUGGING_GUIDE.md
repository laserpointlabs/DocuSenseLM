# Windows Build Debugging Guide

## Overview

This document comprehensively documents the debugging and resolution of critical Windows build issues encountered during the DocuSenseLM development process. This serves as both a historical record and a troubleshooting guide for future developers.

## Issue Timeline

### Phase 1: Initial Build Issues (TypeScript Compilation)
**Date:** December 8, 2025
**Symptoms:**
- TypeScript compilation not updating `dist-electron/main.js`
- Source changes in `electron/main.ts` not reflected in compiled output
- Build process completing but with stale compiled code

**Root Cause:**
- TypeScript incremental compilation cache corruption
- Missing `incremental: false` and `tsBuildInfoFile: null` in `tsconfig.electron.json`
- Build cache files preventing proper recompilation

**Resolution:**
```json
// tsconfig.electron.json - Fixed configuration
{
  "compilerOptions": {
    "incremental": false,
    "tsBuildInfoFile": null,
    "exclude": ["node_modules", "dist", "dist-electron", "web-dist"]
  }
}
```

### Phase 2: Environment Detection Issues
**Symptoms:**
- Electron app loading localhost:5173 (dev server) instead of bundled HTML
- Python backend looking for venv in wrong locations
- Application behavior inconsistent between dev and production

**Root Cause:**
- Missing `isDistBuild()` function in compiled code
- Incorrect logic: `if (isDev)` instead of `if (isDev && !distBuild)`
- Python backend path resolution failing

**Resolution:**
```typescript
// electron/main.ts - Environment detection
function isDistBuild(): boolean {
  return __dirname.includes('dist') || __dirname.includes('win-unpacked');
}

// Fixed logic
if (isDev && !distBuild) {
  // True dev mode - Vite dev server
  mainWindow.loadURL('http://localhost:5173');
} else {
  // Production/dist mode - load from file system
  const htmlPath = distBuild
    ? path.join(__dirname, 'resources', 'index.html')
    : path.join(__dirname, '../dist/index.html');
}
```

### Phase 3: Missing Configuration Files
**Date:** December 8, 2025 (Critical Issue)
**Symptoms:**
```
[Python Stderr]: ERROR:nda-tool:Failed to load default prompts: [Errno 2] No such file or directory
[Python Stderr]: ERROR:nda-tool:Failed to load default config: [Errno 2] No such file or directory
Python process exit event - code: 1, signal: null
Python backend crashed with exit code 1
```

**Root Cause:**
- Build script (`build-windows.ps1`) not copying `config.default.yaml` and `prompts.default.yaml`
- Python backend requiring these files to initialize properly
- Files existed in source but not included in distribution

**Resolution:**
```powershell
# build-windows.ps1 - Added config file copying
if (Test-Path "config.default.yaml") {
    Copy-Item "config.default.yaml" -Destination "dist\win-unpacked\resources\" -ErrorAction SilentlyContinue
}
if (Test-Path "prompts.default.yaml") {
    Copy-Item "prompts.default.yaml" -Destination "dist\win-unpacked\resources\" -ErrorAction SilentlyContinue
}
```

### Phase 4: Python Backend Startup Issues
**Symptoms:**
- Python process spawning but immediately crashing
- Missing BASE_DIR calculation for config file location
- Incomplete error handling around config file operations

**Root Cause:**
- BASE_DIR calculation not accounting for dist build directory structure
- Missing error handling for file operations
- Config files in wrong location relative to Python script

**Resolution:**
```python
# python/server.py - Fixed BASE_DIR calculation
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# For dist builds, config files are in the resources directory alongside the python folder
if BASE_DIR.endswith('python'):
    BASE_DIR = os.path.dirname(BASE_DIR)
```

## Root Cause Analysis

### Primary Issue: Build Script Incomplete
The fundamental problem was that the `build-windows.ps1` script was not copying all necessary files to the distribution directory. Specifically:

1. **Missing Config Files:** `config.default.yaml` and `prompts.default.yaml` were not being copied to `resources/`
2. **Missing Error Context:** When the Python backend failed, the error messages clearly indicated missing files, but this was misinterpreted as an Electron issue

### Secondary Issues:
1. **TypeScript Configuration:** Incremental compilation settings were causing stale builds
2. **Environment Detection:** Logic didn't properly distinguish between dev, dist, and packaged builds
3. **Error Message Misinterpretation:** Clear Python backend errors were ignored in favor of assuming Electron issues

## Files Modified

### Configuration Files
- `tsconfig.electron.json` - Added incremental compilation fixes
- `build-windows.ps1` - Added config file copying
- `electron/main.ts` - Added environment detection logic
- `python/server.py` - Fixed BASE_DIR calculation and error handling

### New Files Created
- `dist\win-unpacked\resources\config.default.yaml` - Complete configuration
- `dist\win-unpacked\resources\prompts.default.yaml` - Analysis prompts

## Prevention Measures

### 1. Build Script Verification
```powershell
# Add to build-windows.ps1
Write-Host "=== BUILD VERIFICATION ==="
$requiredFiles = @(
    "dist\win-unpacked\main.js",
    "dist\win-unpacked\resources\index.html",
    "dist\win-unpacked\resources\config.default.yaml",
    "dist\win-unpacked\resources\prompts.default.yaml"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file - OK"
    } else {
        Write-Error "❌ $file - MISSING"
        exit 1
    }
}
```

### 2. Post-Build Testing
```powershell
# Test script for build verification
Write-Host "=== POST-BUILD TEST ==="
cd dist\win-unpacked

# Test Electron startup (should show debug output)
Write-Host "Testing Electron startup..."
.\run.bat > test-output.log 2>&1
Start-Sleep 3

# Check for success indicators
if (Select-String -Path test-output.log -Pattern "DEBUG: app.whenReady fired") {
    Write-Host "✅ Electron startup - OK"
} else {
    Write-Error "❌ Electron startup - FAILED"
}

# Check Python backend
if (netstat -ano | findstr 14242) {
    Write-Host "✅ Python backend - OK"
} else {
    Write-Error "❌ Python backend - FAILED"
}
```

### 3. TypeScript Configuration Standards
```json
// tsconfig.electron.json - Recommended settings
{
  "compilerOptions": {
    "incremental": false,
    "tsBuildInfoFile": null,
    "noEmitOnError": true,
    "strict": true
  },
  "exclude": [
    "node_modules",
    "dist",
    "dist-electron",
    "web-dist"
  ]
}
```

## Troubleshooting Guide

### Issue: TypeScript Not Compiling Changes
**Symptoms:** Source changes not reflected in compiled output
**Solution:**
1. Clear TypeScript cache: `Remove-Item *.tsbuildinfo -Recurse -Force`
2. Check `tsconfig.electron.json` has `"incremental": false`
3. Rebuild: `npm run build:electron`

### Issue: Electron Loading Wrong Content
**Symptoms:** App loads localhost:5173 instead of bundled HTML
**Solution:**
1. Check `isDistBuild()` function exists in compiled code
2. Verify logic uses `if (isDev && !distBuild)` pattern
3. Test: `__dirname.includes('win-unpacked')` should return true

### Issue: Python Backend Crashing
**Symptoms:** "Failed to load default config" errors
**Solution:**
1. Verify config files exist in `dist\win-unpacked\resources\`
2. Check BASE_DIR calculation in Python script
3. Ensure build script copies config files

### Issue: Build Script Not Working
**Symptoms:** Files missing from distribution
**Solution:**
1. Run build manually: `npm run build:web && npm run build:electron`
2. Check PowerShell execution: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
3. Verify all paths in `build-windows.ps1`

## Build Process Documentation

### Complete Build Sequence
```bash
# 1. Install dependencies
npm install

# 2. Build web assets
npm run build:web

# 3. Build Electron main process
npm run build:electron

# 4. Create distribution (Windows)
npm run build:windows

# 5. Verify build
cd dist\win-unpacked
.\run.bat
```

### File Structure After Build
```
dist\win-unpacked\
├── main.js                    # Compiled Electron main process
├── preload.js                 # Electron preload script
├── package.json              # App metadata
├── run.bat                   # Launch script
└── resources\
    ├── index.html            # Bundled web app
    ├── config.default.yaml   # Application configuration
    ├── prompts.default.yaml  # Analysis prompts
    └── python\               # Python backend
        ├── server.py         # FastAPI server
        └── venv\             # Virtual environment
```

## Lessons Learned

1. **Read Error Messages Carefully:** The most obvious errors are often the real issues
2. **Don't Assume Root Causes:** What seems like an Electron issue might be a Python backend problem
3. **Verify Build Outputs:** Always check that distribution contains all required files
4. **Test Incrementally:** Fix one issue at a time and verify each fix
5. **Document Everything:** Complex debugging sessions need comprehensive documentation

## Future Improvements

### Automated Testing
- Add build verification scripts
- Implement automated post-build testing
- Create integration tests for full application startup

### Build Tooling
- Consider switching to Electron Forge for better Windows support
- Implement proper file watching for development
- Add build caching with proper invalidation

### Error Handling
- Improve error messages in Python backend
- Add startup logging to Electron main process
- Implement graceful degradation when config files are missing

## Conclusion

This debugging session revealed critical gaps in the Windows build process and error handling. The root cause was incomplete build scripts that didn't copy essential configuration files, leading to Python backend failures that were misinterpreted as Electron issues.

The fixes implemented ensure:
- ✅ Proper TypeScript compilation
- ✅ Correct environment detection
- ✅ Complete file distribution
- ✅ Robust error handling

This documentation serves as both a historical record and a comprehensive guide for preventing similar issues in the future.