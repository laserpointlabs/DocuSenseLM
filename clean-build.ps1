# PowerShell script to clean up build artifacts and prepare for fresh build
# This ensures a clean environment for testing builds

Write-Host "Cleaning up DocuSenseLM build artifacts..." -ForegroundColor Cyan
Write-Host ""

# Kill any running processes that might lock files
Write-Host "Killing running processes..." -ForegroundColor Yellow
$runningProcesses = Get-Process | Where-Object {
    $_.Name -like "*DocuSense*" -or
    $_.Name -like "*electron*" -or
    $_.Name -like "*python*"
} -ErrorAction SilentlyContinue

if ($runningProcesses) {
    Write-Host "Found $($runningProcesses.Count) process(es) to kill:"
    $runningProcesses | ForEach-Object {
        Write-Host "  - $($_.Name) (PID: $($_.Id))"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep 2
    Write-Host "Processes killed" -ForegroundColor Green
} else {
    Write-Host "No running processes found" -ForegroundColor Green
}

Write-Host ""

# Clean build directories
Write-Host "Removing build artifacts..." -ForegroundColor Yellow
$buildDirs = @("release", "dist-electron", "web-dist", "python/python_embed")
foreach ($dir in $buildDirs) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
            Write-Host "  Removed: $dir" -ForegroundColor Green
        } catch {
            Write-Host "  Warning: Could not remove: $dir ($($_.Exception.Message))" -ForegroundColor Yellow
        }
    }
}

# Clean installer files
Write-Host "Removing installer files..." -ForegroundColor Yellow
$installerPatterns = @("*.exe", "*.msi", "*.dmg", "*.pkg", "*.deb", "*.rpm", "*.snap", "*.appimage")
foreach ($pattern in $installerPatterns) {
    $files = Get-ChildItem -Path "." -Filter $pattern -File -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item -Path $file.FullName -Force -ErrorAction Stop
            Write-Host "  Removed: $($file.Name)" -ForegroundColor Green
        } catch {
            Write-Host "  Warning: Could not remove: $($file.Name) ($($_.Exception.Message))" -ForegroundColor Yellow
        }
    }
}

# Clean test directories
Write-Host "Removing test directories..." -ForegroundColor Yellow
$testDirs = Get-ChildItem -Path "." -Filter "ci-test-*" -Directory -ErrorAction SilentlyContinue
foreach ($dir in $testDirs) {
    try {
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction Stop
        Write-Host "  Removed: $($dir.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  Warning: Could not remove: $($dir.Name) ($($_.Exception.Message))" -ForegroundColor Yellow
    }
}

# Clean AppData directory
Write-Host "Cleaning AppData user data..." -ForegroundColor Yellow
$appDataPath = "$env:APPDATA\DocuSenseLM"
if (Test-Path $appDataPath) {
    try {
        Remove-Item -Path $appDataPath -Recurse -Force -ErrorAction Stop
        Write-Host "  Removed: $appDataPath" -ForegroundColor Green
    } catch {
        Write-Host "  Warning: Could not remove AppData: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No AppData directory found" -ForegroundColor Blue
}

Write-Host ""
Write-Host "Cleanup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Cleaned:"
Write-Host "  - Build artifacts (release/, dist-electron/, web-dist/)"
Write-Host "  - Python embeddable (python/python_embed/)"
Write-Host "  - Installers (*.exe, *.msi, etc.)"
Write-Host "  - Test directories (ci-test-*)"
Write-Host "  - User data ($env:APPDATA\DocuSenseLM)"
Write-Host ""
Write-Host "Ready for fresh build. Run:"
Write-Host "  npm run build:windows"
Write-Host ""
Write-Host "Or run the full test cycle:"
Write-Host "  .\clean-build.ps1; npm run build:windows; .\run-windows.ps1"