# PowerShell script to run the Windows build from project root
# This script starts the DocuSenseLM application from the built distribution

Write-Host "🚀 Starting DocuSenseLM (Windows Build)..."
Write-Host ""

# Check if the build exists
if (-not (Test-Path "release\win-unpacked\DocuSenseLM.exe")) {
    Write-Error "❌ Build not found! Run 'npm run build:windows' first."
    exit 1
}

# Check if required files exist
$requiredFiles = @(
    "release\win-unpacked\DocuSenseLM.exe",
    "release\win-unpacked\resources\web-dist\index.html",
    "release\win-unpacked\resources\config.default.yaml",
    "release\win-unpacked\resources\prompts.default.yaml",
    "release\win-unpacked\resources\python\server.py"
)

Write-Host "📋 Checking required files..."
$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file"
    } else {
        Write-Host "❌ $file - MISSING"
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Error "❌ Some required files are missing. Please run 'npm run build:windows' again."
    exit 1
}

Write-Host ""
Write-Host "🎯 Launching DocuSenseLM..."
Write-Host "📁 Working directory: $(Get-Location)"
Write-Host "🎮 Application: release\win-unpacked\main.js"
Write-Host ""

# Launch the executable directly
Write-Host "Starting Electron application..."
Write-Host "Launching: release\win-unpacked\DocuSenseLM.exe"
& "release\win-unpacked\DocuSenseLM.exe"

Write-Host ""
Write-Host "👋 DocuSenseLM closed."

