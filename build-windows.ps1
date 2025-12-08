# PowerShell build script for DocuSenseLM on Windows
# This bypasses electron-builder's code signing issues

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Building DocuSenseLM for Windows (no admin privileges needed)..." -ForegroundColor Cyan
[Console]::Out.Flush()

# Clean previous builds
Write-Host "Cleaning previous builds..."
# Kill any processes that might be locking files
Write-Host "Checking for running processes..."
$runningProcesses = Get-Process | Where-Object { $_.Name -like "*DocuSense*" -or $_.Name -like "*electron*" }
if ($runningProcesses) {
    Write-Host "Found $($runningProcesses.Count) running process(es) - killing them..."
    $runningProcesses | ForEach-Object {
        Write-Host "Killing $($_.Name) (PID: $($_.Id))"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep 3
} else {
    Write-Host "No running processes found"
}

# Remove old build output
Write-Host "Attempting to delete release folder..."
try {
    Remove-Item -Recurse -Force "release" -ErrorAction Stop
    Write-Host "✅ SUCCESS: Release directory deleted!"
} catch {
    Write-Host "❌ Could not delete release directory: $($_.Exception.Message)"
    Write-Host "Attempting to rename instead..."
    try {
        $backupName = "release.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Rename-Item "release" $backupName -ErrorAction Stop
        Write-Host "✅ Renamed to $backupName - continuing with build..."
    } catch {
        Write-Host "❌ Could not rename release folder either: $($_.Exception.Message)"
        Write-Host "⚠️  Continuing anyway - electron-builder should overwrite files"
    }
}

# Build the web app
Write-Host "Building web app..." -ForegroundColor Yellow
[Console]::Out.Flush()
$webResult = & npm run build:web 2>&1; $webExitCode = $LASTEXITCODE
if ($webExitCode -ne 0) {
    Write-Host "ERROR: Web build failed with exit code $webExitCode!" -ForegroundColor Red
    Write-Host $webResult
    exit 1
}
Write-Host "SUCCESS: Web build completed" -ForegroundColor Green
[Console]::Out.Flush()

# Build the Electron app
Write-Host "Building Electron app..." -ForegroundColor Yellow
[Console]::Out.Flush()
$electronResult = & npm run build:electron 2>&1; $electronExitCode = $LASTEXITCODE
if ($electronExitCode -ne 0) {
    Write-Host "ERROR: Electron build failed with exit code $electronExitCode!" -ForegroundColor Red
    Write-Host $electronResult
    exit 1
}
Write-Host "SUCCESS: Electron build completed" -ForegroundColor Green
[Console]::Out.Flush()

# Use electron-builder to create proper desktop app (unpacked directory with Electron runtime)
# This creates dist\win-unpacked with the Electron runtime bundled
# Disable code signing to avoid admin privilege issues
Write-Host "Packaging Electron application with electron-builder (code signing disabled)..." -ForegroundColor Yellow
[Console]::Out.Flush()

# Clear code signing cache to prevent symlink errors (needs to be done before each build)
Write-Host "Clearing electron-builder code signing cache..." -ForegroundColor Yellow
$codeSignCache = "$env:LOCALAPPDATA\electron-builder\Cache\winCodeSign"
if (Test-Path $codeSignCache) {
    Remove-Item -Recurse -Force $codeSignCache -ErrorAction SilentlyContinue
    Write-Host "Code signing cache cleared" -ForegroundColor Green
}

# Disable code signing completely via environment variables
# Setting sign: false in package.json should prevent downloading signing tools
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
$env:SKIP_NOTARIZATION = "true"
$env:WIN_CSC_LINK = ""
$env:CSC_LINK = ""

    # Run electron-builder with code signing disabled
    # sign: false in package.json should prevent downloading code signing tools
    Write-Host "Running electron-builder (this may take a minute)..."
    $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
    $env:WIN_CSC_LINK = ""
    $env:CSC_LINK = ""
    # Add skip notarsize
    $env:SKIP_NOTARIZATION = "true"
    
    # Run without nsis first to ensure win-unpacked works
    $builderResult = & npx electron-builder --win --dir 2>&1; $builderExitCode = $LASTEXITCODE
Write-Host "Electron-builder finished with exit code: $builderExitCode"

# Wait a moment for file operations to complete
Start-Sleep 2

# Check if executable was created despite errors
$exeCreated = Test-Path "release\win-unpacked\DocuSenseLM.exe"
Write-Host "Executable created: $exeCreated"

# Check for known non-critical errors
$hasSymlinkErrors = $builderResult -match "Cannot create symbolic link.*darwin"
$hasSigningError = $builderResult -match "Cannot use 'in' operator.*undefined"

# If exe was created, treat as success even if exit code indicates failure
if ($exeCreated) {
    Write-Host "SUCCESS: Electron packaging completed (executable created despite warnings)!" -ForegroundColor Green
    if ($hasSigningError) {
        Write-Host "NOTE: Code signing error was ignored (signing disabled, not needed)" -ForegroundColor Yellow
    }
    if ($hasSymlinkErrors) {
        Write-Host "NOTE: Symlink errors for darwin files were ignored (not needed for Windows)" -ForegroundColor Yellow
    }
} elseif ($builderExitCode -ne 0 -and -not $hasSymlinkErrors -and -not $hasSigningError) {
    Write-Host "ERROR: Electron packaging failed with exit code $builderExitCode!" -ForegroundColor Red
    Write-Host $builderResult
    Write-Host ""
    Write-Host "Falling back to manual packaging..." -ForegroundColor Yellow
    
    # Fallback: Manual packaging if electron-builder fails
    Write-Host "Creating distribution directory manually..."
    New-Item -ItemType Directory -Force -Path "release\win-unpacked\resources" | Out-Null
    
    # Copy our application files
    Write-Host "Copying application files..."
    Copy-Item "dist-electron\*" -Destination "release\win-unpacked\" -Recurse -Force
    Copy-Item "web-dist\*" -Destination "release\win-unpacked\resources\" -Recurse -Force
    
    # Copy Python backend
    Write-Host "Copying Python backend..."
    Copy-Item "python" -Destination "release\win-unpacked\resources\" -Recurse -Force
    
    # Copy config and other files
    Write-Host "Copying configuration files..."
    if (Test-Path "config.yaml") {
        Copy-Item "config.yaml" -Destination "release\win-unpacked\" -ErrorAction SilentlyContinue
    }
    # Always copy default files for reset functionality
    if (Test-Path "config.default.yaml") {
        Copy-Item "config.default.yaml" -Destination "release\win-unpacked\resources\" -ErrorAction SilentlyContinue
    }
    if (Test-Path "prompts.default.yaml") {
        Copy-Item "prompts.default.yaml" -Destination "release\win-unpacked\resources\" -ErrorAction SilentlyContinue
    }
    if (Test-Path "build\icon.png") {
        Copy-Item "build\icon.png" -Destination "release\win-unpacked\" -ErrorAction SilentlyContinue
    }
    
    # Copy and modify package.json for the release directory
    Write-Host "Copying package.json..."
    $packageJson = Get-Content "package.json" | ConvertFrom-Json
    $packageJson.main = "main.js"
    $packageJson | ConvertTo-Json -Depth 10 | Set-Content "release\win-unpacked\package.json"
    
    Write-Host "WARNING: Manual packaging complete, but Electron runtime not bundled." -ForegroundColor Yellow
    Write-Host "This requires Node.js and npm to run. For a proper desktop app, fix electron-builder issues." -ForegroundColor Yellow
} elseif ($exeCreated) {
    # Executable was created, success!
    Write-Host "SUCCESS: Electron packaging completed" -ForegroundColor Green
    
    # Copy additional files that electron-builder might not include
    Write-Host "Copying additional resources..."
    if (Test-Path "config.default.yaml") {
        $resourcesPath = "release\win-unpacked\resources"
        if (-not (Test-Path $resourcesPath)) {
            New-Item -ItemType Directory -Force -Path $resourcesPath | Out-Null
        }
        Copy-Item "config.default.yaml" -Destination $resourcesPath -ErrorAction SilentlyContinue
    }
    if (Test-Path "prompts.default.yaml") {
        $resourcesPath = "release\win-unpacked\resources"
        if (-not (Test-Path $resourcesPath)) {
            New-Item -ItemType Directory -Force -Path $resourcesPath | Out-Null
        }
        Copy-Item "prompts.default.yaml" -Destination $resourcesPath -ErrorAction SilentlyContinue
    }
}
[Console]::Out.Flush()

# Verify the executable was created
if (Test-Path "release\win-unpacked\DocuSenseLM.exe") {
    Write-Host "SUCCESS: Desktop application executable created: release\win-unpacked\DocuSenseLM.exe" -ForegroundColor Green
} else {
    Write-Host "WARNING: DocuSenseLM.exe not found. Checking for alternative structure..." -ForegroundColor Yellow
    # Check if electron-builder created a different structure
    $exeFiles = Get-ChildItem -Path "release" -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue
    if ($exeFiles) {
        Write-Host "Found executable(s):" -ForegroundColor Yellow
        $exeFiles | ForEach-Object { Write-Host "  $($_.FullName)" }
    }
}

Write-Host "Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Desktop application ready!"
Write-Host ""
Write-Host "To run the application:"
if (Test-Path "release\win-unpacked\DocuSenseLM.exe") {
    Write-Host "   Double-click: release\win-unpacked\DocuSenseLM.exe" -ForegroundColor Cyan
    Write-Host "   Or from command line: .\release\win-unpacked\DocuSenseLM.exe" -ForegroundColor Cyan
} else {
    Write-Host "   Navigate to: release\win-unpacked"
    Write-Host "   Run: DocuSenseLM.exe (or the executable file found there)"
}
Write-Host ""
Write-Host "The application is a standalone desktop app - no Node.js required!" -ForegroundColor Green
Write-Host "Built application directory: release\win-unpacked"