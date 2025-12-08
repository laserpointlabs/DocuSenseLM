# PowerShell build script for DocuSenseLM on Windows
# This bypasses electron-builder's code signing issues

Write-Host "🏗️  Building DocuSenseLM for Windows (no admin privileges needed)..."

# Clean previous builds
Write-Host "🧹 Cleaning previous builds..."
if (Test-Path "dist") {
    # Kill any processes that might be locking files
    Get-Process | Where-Object { $_.Path -like "*dist*" -or $_.Name -like "*electron*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2

    # Try to remove dist directory multiple times in case of locks
    for ($i = 0; $i -lt 5; $i++) {
        try {
            Remove-Item -Recurse -Force "dist" -ErrorAction Stop
            break
        } catch {
            Write-Host "Retrying dist cleanup (attempt $($i+1))..."
            Start-Sleep 1
        }
    }
}

# Build the web app
Write-Host "🌐 Building web app..."
& npm run build:web
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Web build failed!"
    exit 1
}

# Build the Electron app
Write-Host "⚡ Building Electron app..."
& npm run build:electron
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Electron build failed!"
    exit 1
}

# Create distribution directory
Write-Host "📁 Creating distribution directory..."
New-Item -ItemType Directory -Force -Path "dist\win-unpacked\resources" | Out-Null

# Copy our application files
Write-Host "📋 Copying application files..."
Copy-Item "dist-electron\*" -Destination "dist\win-unpacked\" -Recurse -Force
Copy-Item "web-dist\*" -Destination "dist\win-unpacked\resources\" -Recurse -Force

# Copy Python backend
Write-Host "🐍 Copying Python backend..."
Copy-Item "python" -Destination "dist\win-unpacked\resources\" -Recurse -Force

# Copy config and other files
Write-Host "📋 Copying configuration files..."
if (Test-Path "config.yaml") {
    Copy-Item "config.yaml" -Destination "dist\win-unpacked\" -ErrorAction SilentlyContinue
}
if (Test-Path "config.default.yaml") {
    Copy-Item "config.default.yaml" -Destination "dist\win-unpacked\resources\" -ErrorAction SilentlyContinue
}
if (Test-Path "prompts.default.yaml") {
    Copy-Item "prompts.default.yaml" -Destination "dist\win-unpacked\resources\" -ErrorAction SilentlyContinue
}
if (Test-Path "build\icon.png") {
    Copy-Item "build\icon.png" -Destination "dist\win-unpacked\" -ErrorAction SilentlyContinue
}

# Copy and modify package.json for the dist directory
Write-Host "📋 Copying package.json..."
$packageJson = Get-Content "package.json" | ConvertFrom-Json
$packageJson.main = "main.js"  # Update main to point to the built file
$packageJson | ConvertTo-Json -Depth 10 | Set-Content "dist\win-unpacked\package.json"

# Create a simple batch file to run the app
Write-Host "📝 Creating run script..."
$batchContent = @"
@echo off
echo Starting DocuSenseLM...
cd /d "%~dp0"
cd ..\..
npx electron dist\win-unpacked
"@
$batchContent | Out-File -FilePath "dist\win-unpacked\run.bat" -Encoding ASCII

# Create a PowerShell script as well
Write-Host "📝 Creating PowerShell run script..."
$psContent = @'
Write-Host "Starting DocuSenseLM..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path (Split-Path $scriptDir))
npx electron dist\win-unpacked
'@
$psContent | Out-File -FilePath "dist\win-unpacked\run.ps1" -Encoding ASCII

Write-Host "✅ Build complete!"
Write-Host ""
Write-Host "🚀 To test the app:"
Write-Host "   cd dist\win-unpacked"
Write-Host "   .\run.bat"
Write-Host "   or"
Write-Host "   .\run.ps1"
Write-Host ""
Write-Host "📦 Built application is in: dist\win-unpacked\"