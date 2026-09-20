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
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    Write-Host "`n启动失败：$Message" -ForegroundColor Red
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

if (-not (Test-Path -LiteralPath $requirements)) { Fail "未找到 $requirements" }
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'package.json'))) { Fail "未找到 frontend/package.json" }

Write-Host "Speech Rehab Agent 本地开发启动器" -ForegroundColor Cyan
Write-Host "项目目录：$projectRoot"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "`n[1/5] 创建 backend/.venv ..." -ForegroundColor Yellow
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        & py -3.13 -m venv $venvDir
    }
    else {
        & python -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Fail '无法创建 Python 虚拟环境。请安装 Python 3.11 或更高版本，并确保 py 或 python 在 PATH 中。'
    }
    $InstallDependencies = $true
}

if ($InstallDependencies) {
    Write-Host "`n[2/5] 安装后端依赖（首次运行可能需要几分钟）..." -ForegroundColor Yellow
    Invoke-Checked { & $venvPython -m pip install --upgrade pip } 'pip 升级失败。'
    Invoke-Checked { & $venvPython -m pip install -r $requirements } '后端依赖安装失败。'
}
else {
    Write-Host "`n[2/5] 复用已有 backend/.venv（如依赖有更新，请加 -InstallDependencies）" -ForegroundColor DarkGray
}

if (-not $SkipMigration) {
    Write-Host "`n[3/5] 执行数据库迁移 ..." -ForegroundColor Yellow
    Push-Location $backendDir
    try {
        Invoke-Checked { & $venvPython -m alembic upgrade head } '数据库迁移失败。请确认 PostgreSQL 已启动，且 backend/.env 中 DATABASE_URL 正确。'
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "`n[3/5] 跳过数据库迁移" -ForegroundColor DarkGray
}

Write-Host "`n[4/5] 检查前端依赖 ..." -ForegroundColor Yellow
if ($null -eq (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail '未找到 npm。请安装 Node.js 20 或更高版本。'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules'))) {
    Push-Location $frontendDir
    try {
        Invoke-Checked { npm install } '前端依赖安装失败。'
    }
    finally {
        Pop-Location
    }
}

Write-Host "`n[5/5] 在两个新窗口启动服务 ..." -ForegroundColor Yellow
$backendCommand = @"
Set-Location -LiteralPath '$backendDir'
& '$venvPython' -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort
"@
$frontendCommand = @"
Set-Location -LiteralPath '$frontendDir'
npm run dev -- --port $FrontendPort
"@

Start-Process powershell.exe -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', (To-EncodedCommand $backendCommand)
Start-Process powershell.exe -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', (To-EncodedCommand $frontendCommand)

Write-Host "`n已启动：" -ForegroundColor Green
Write-Host "  前端：http://127.0.0.1:$FrontendPort"
Write-Host "  后端：http://127.0.0.1:$BackendPort"
Write-Host "  健康检查：http://127.0.0.1:$BackendPort/api/health"
Write-Host "`n关闭服务：分别在后端和前端弹出的窗口中按 Ctrl+C。"
