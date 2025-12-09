param(
  [Parameter(Mandatory = $false)][string]$RunId,
  [Parameter(Mandatory = $false)][string]$ArtifactName = "DocuSenseLM-unpacked",
  [switch]$Latest
)

$ErrorActionPreference = "Stop"

function Write-Status($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host $msg -ForegroundColor Green }
function Write-Fail($msg) { Write-Host $msg -ForegroundColor Red }

try {
  # Determine RunId if -Latest is provided
  if ($Latest -and [string]::IsNullOrEmpty($RunId)) {
    $run = gh run list --limit 1 --branch $(git rev-parse --abbrev-ref HEAD) --json databaseId |
      ConvertFrom-Json
    if (-not $run) { throw "No runs found for current branch" }
    $RunId = $run[0].databaseId
  }

  if ([string]::IsNullOrEmpty($RunId)) {
    throw "Please provide -RunId or use -Latest"
  }

  $targetDir = Join-Path (Get-Location) "release\ci-verify"
  if (Test-Path $targetDir) { Remove-Item -Recurse -Force $targetDir }
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

  Write-Status "Downloading artifact $ArtifactName from run $RunId..."
  gh run download $RunId --name $ArtifactName --dir $targetDir

  # Find the executable
  $exe = Get-ChildItem -Path $targetDir -Filter "DocuSenseLM.exe" -Recurse | Select-Object -First 1
  if (-not $exe) { throw "DocuSenseLM.exe not found in artifact" }
  Write-Status "Found executable: $($exe.FullName)"

  # Launch the app
  Write-Status "Starting app..."
  $proc = Start-Process -FilePath $exe.FullName -PassThru
  $startTime = Get-Date

  # Poll health
  $deadline = (Get-Date).AddSeconds(90)
  $healthOk = $false
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    try {
      $resp = Invoke-WebRequest -Uri "http://127.0.0.1:14242/health" -TimeoutSec 5
      if ($resp.StatusCode -eq 200) {
        $json = $resp.Content | ConvertFrom-Json
        if ($json.status -eq "ok") {
          $healthOk = $true
          break
        }
      }
    } catch {
      # ignore and retry
    }
  }

  if ($healthOk) {
    Write-Success "it works!! Backend healthy."
    exit 0
  } else {
    Write-Fail "I failed!! Backend did not become healthy."
    exit 1
  }
}
finally {
  # Cleanup processes started after the script began
  try {
    $procs = Get-Process DocuSenseLM, python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt $startTime }
    if ($procs) { $procs | Stop-Process -Force -ErrorAction SilentlyContinue }
  } catch {}
  # Remove downloaded artifact directory
  try {
    if ($targetDir -and (Test-Path $targetDir)) {
      Remove-Item -Recurse -Force $targetDir -ErrorAction SilentlyContinue
    }
  } catch {}
}

