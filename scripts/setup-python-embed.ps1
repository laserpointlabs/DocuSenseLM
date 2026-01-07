$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Setting up Python embeddable distribution for packaging..." -ForegroundColor Cyan

$pythonDir = "python"
$embedDir = Join-Path $pythonDir "python_embed"
$pythonExe = Join-Path $embedDir "python.exe"

if (Test-Path $pythonExe) {
  Write-Host "✅ python_embed already present at $pythonExe" -ForegroundColor Green
  exit 0
}

New-Item -ItemType Directory -Force -Path $embedDir | Out-Null

$pythonUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
$pythonZip = "python-embed.zip"

Write-Host "Downloading Python embeddable from $pythonUrl..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip

Write-Host "Extracting to $embedDir..." -ForegroundColor Yellow
Expand-Archive -Path $pythonZip -DestinationPath $embedDir -Force
Remove-Item $pythonZip -Force

# Enable site-packages (pip) in embeddable python by uncommenting `import site` in the ._pth file.
$pthFile = Get-ChildItem $embedDir -Filter "*._pth" | Select-Object -First 1
if (-not $pthFile) {
  throw "Could not find ._pth file in $embedDir"
}
$pthContent = Get-Content $pthFile.FullName
$pthContent = $pthContent -replace "#import site", "import site"
$pthContent | Set-Content $pthFile.FullName

Write-Host "Bootstrapping pip..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile (Join-Path $embedDir "get-pip.py")

Push-Location $embedDir
try {
  .\python.exe get-pip.py
  .\python.exe -m pip install setuptools wheel
  Write-Host "Installing backend Python dependencies..." -ForegroundColor Yellow
  .\python.exe -m pip install -r ..\requirements.txt
} finally {
  if (Test-Path "get-pip.py") { Remove-Item "get-pip.py" -Force }
  Pop-Location
}

if (-not (Test-Path $pythonExe)) {
  throw "python_embed setup failed: $pythonExe not found"
}

Write-Host "✅ Python embeddable setup completed" -ForegroundColor Green


