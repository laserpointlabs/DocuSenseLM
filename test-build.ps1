# Test build script to capture all output
$ErrorActionPreference = "Continue"
$output = @()

# Redirect all output
$output += "=== Starting Build Test ==="
$output += ""

# Test electron-builder directly
$output += "Testing electron-builder..."
$env:forceCodeSigning = "false"
$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
$env:CSC_LINK = ""
$env:WIN_CSC_LINK = ""

$result = & npx electron-builder --win --dir 2>&1
$output += $result
$output += ""
$output += "Exit code: $LASTEXITCODE"
$output += ""

# Check results
if (Test-Path "dist\win-unpacked\DocuSenseLM.exe") {
    $output += "SUCCESS: DocuSenseLM.exe created!"
} else {
    $output += "FAILED: DocuSenseLM.exe not found"
    $exeFiles = Get-ChildItem -Path "dist" -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue
    if ($exeFiles) {
        $output += "Found executables:"
        $exeFiles | ForEach-Object { $output += "  $($_.FullName)" }
    }
}

# Write all output
$output | Out-File -FilePath "test-build-output.txt" -Encoding UTF8
$output | Write-Host







