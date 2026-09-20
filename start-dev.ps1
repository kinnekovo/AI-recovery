<#
    One-click local development launcher for Speech Rehab Agent.

    Usage (from the repository root):
      .\start-dev.ps1
      .\start-dev.ps1 -InstallDependencies
      .\start-dev.ps1 -SkipMigration
#>
[CmdletBinding()]
param(
    [switch]$InstallDependencies,
    [switch]$SkipMigration,
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Host "`nStartup failed: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Fail $Description
    }
}

function To-EncodedCommand([string]$Command) {
    [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
}

$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$venvDir = Join-Path $backendDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$requirements = Join-Path $backendDir 'requirements.txt'

if (-not (Test-Path -LiteralPath $requirements)) { Fail "Missing $requirements" }
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'package.json'))) { Fail 'Missing frontend/package.json' }

Write-Host 'Speech Rehab Agent development launcher' -ForegroundColor Cyan
Write-Host "Project directory: $projectRoot"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "`n[1/5] Creating backend/.venv ..." -ForegroundColor Yellow
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        & py -3.13 -m venv $venvDir
    }
    else {
        & python -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Fail 'Could not create the Python virtual environment. Install Python 3.11+ and ensure py or python is on PATH.'
    }
    $InstallDependencies = $true
}

if ($InstallDependencies) {
    Write-Host "`n[2/5] Installing backend dependencies (the first run may take a few minutes) ..." -ForegroundColor Yellow
    Invoke-Checked { & $venvPython -m pip install --upgrade pip } 'pip upgrade failed.'
    Invoke-Checked { & $venvPython -m pip install -r $requirements } 'Backend dependency installation failed.'
}
else {
    Write-Host "`n[2/5] Reusing backend/.venv (use -InstallDependencies after dependency changes)" -ForegroundColor DarkGray
}

if (-not $SkipMigration) {
    Write-Host "`n[3/5] Applying database migrations ..." -ForegroundColor Yellow
    Push-Location $backendDir
    try {
        Invoke-Checked { & $venvPython -m alembic upgrade head } 'Database migration failed. Confirm PostgreSQL is running and backend/.env has the correct DATABASE_URL.'
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "`n[3/5] Skipping database migrations" -ForegroundColor DarkGray
}

Write-Host "`n[4/5] Checking frontend dependencies ..." -ForegroundColor Yellow
if ($null -eq (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail 'npm was not found. Install Node.js 20 or later.'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules'))) {
    Push-Location $frontendDir
    try {
        Invoke-Checked { npm install } 'Frontend dependency installation failed.'
    }
    finally {
        Pop-Location
    }
}

Write-Host "`n[5/5] Starting services in two new windows ..." -ForegroundColor Yellow
$backendCommand = @"
Set-Location -LiteralPath '$backendDir'
& '$venvPython' -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort
"@
$frontendCommand = @"
Set-Location -LiteralPath '$frontendDir'
`$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:$BackendPort'
npm run dev -- --port $FrontendPort
"@

Start-Process powershell.exe -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', (To-EncodedCommand $backendCommand)
Start-Process powershell.exe -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', (To-EncodedCommand $frontendCommand)

Write-Host "`nStarted:" -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Backend: http://127.0.0.1:$BackendPort"
Write-Host "  Health: http://127.0.0.1:$BackendPort/api/health"
Write-Host "`nTo stop services, press Ctrl+C in each service window."
