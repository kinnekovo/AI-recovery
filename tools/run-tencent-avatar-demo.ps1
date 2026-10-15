$ErrorActionPreference = "Stop"

$demoRoot = Join-Path $PSScriptRoot "tencent-avatar-demo\interact_avatar_demo"
$pythonExe = Join-Path $PSScriptRoot "tencent-avatar-demo\.venv\Scripts\python.exe"
$demoScript = Join-Path $demoRoot "tencent_virtual_human_completeV2.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python 3.11 environment not found: $pythonExe"
}

if (-not (Test-Path -LiteralPath $demoScript)) {
    throw "Tencent avatar demo not found: $demoScript"
}

$env:TENCENT_IVH_APPKEY = Read-Host "Enter AppKey"
$secureAccessToken = Read-Host "Enter AccessToken (input is hidden)" -AsSecureString
$accessTokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAccessToken)
try {
    $env:TENCENT_IVH_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($accessTokenPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($accessTokenPtr)
}
$env:TENCENT_IVH_ASSET_KEY = Read-Host "Enter 2D Premium AssetVirtualmanKey"
$ffmpegDir = Join-Path $PSScriptRoot "tencent-avatar-demo\.venv\Lib\site-packages\imageio_ffmpeg\binaries"
if (-not (Test-Path -LiteralPath $ffmpegDir)) {
    throw "Local ffmpeg runtime not found: $ffmpegDir"
}
$originalPath = $env:PATH
$env:PATH = "$ffmpegDir;$originalPath"
$env:PYTHONIOENCODING = "utf-8"

try {
    Push-Location $demoRoot
    & $pythonExe $demoScript
}
finally {
    Pop-Location
    Remove-Item Env:TENCENT_IVH_APPKEY -ErrorAction SilentlyContinue
    Remove-Item Env:TENCENT_IVH_ACCESS_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:TENCENT_IVH_ASSET_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    $env:PATH = $originalPath
}
