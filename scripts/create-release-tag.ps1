# PowerShell script to create a release tag and ensure build artifacts are generated
# Usage: .\scripts\create-release-tag.ps1 -Version "1.0.15" -Message "Add new feature"

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$ErrorActionPreference = "Stop"

# Validate version format (X.Y.Z)
if ($Version -notmatch '^v?[0-9]+\.[0-9]+\.[0-9]+$') {
    Write-Host "Error: Version must be in format X.Y.Z (e.g., 1.0.15)" -ForegroundColor Red
    exit 1
}

# Ensure version starts with 'v'
if ($Version -notmatch '^v') {
    $Version = "v$Version"
}

Write-Host "Creating release tag: $Version" -ForegroundColor Cyan
Write-Host "Message: $Message"
Write-Host ""

# Check if we're on main branch
$currentBranch = git branch --show-current
if ($currentBranch -ne "main") {
    Write-Host "Warning: Not on main branch (currently on $currentBranch)" -ForegroundColor Yellow
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
}

# Check for uncommitted changes
$status = git status --short
if ($status) {
    Write-Host "Warning: You have uncommitted changes" -ForegroundColor Yellow
    Write-Host $status
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
}

# Update version in package.json
$versionNum = $Version -replace '^v', ''
if (Test-Path "package.json") {
    Write-Host "Updating version in package.json to $versionNum..." -ForegroundColor Yellow
    $packageJson = Get-Content "package.json" | ConvertFrom-Json
    $packageJson.version = $versionNum
    $packageJson | ConvertTo-Json -Depth 10 | Set-Content "package.json"
    
    # Update version in App.tsx if it exists
    if (Test-Path "src/App.tsx") {
        Write-Host "Updating version in src/App.tsx to $versionNum..." -ForegroundColor Yellow
        (Get-Content "src/App.tsx") -replace 'const APP_VERSION = "[^"]*"', "const APP_VERSION = `"$versionNum`"" | Set-Content "src/App.tsx"
    }
    
    git add package.json src/App.tsx
    git commit -m "chore: Bump version to $versionNum"
}

# Build web assets
Write-Host ""
Write-Host "Building web assets..." -ForegroundColor Yellow
npm run build:web

# Create annotated tag
Write-Host ""
Write-Host "Creating tag $Version..." -ForegroundColor Yellow
git tag -a "$Version" -m "$Version`: $Message"

Write-Host ""
Write-Host "✅ Release tag $Version created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Review the tag: git show $Version"
Write-Host "  2. Push the tag: git push origin $Version"
Write-Host "  3. Push commits: git push origin main"
Write-Host ""
Write-Host "The build workflow will automatically create artifacts for this tag."

