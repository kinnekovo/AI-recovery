$ErrorActionPreference = "Stop"

$backendEnv = Join-Path $PSScriptRoot "..\backend\.env"
$backendExample = Join-Path $PSScriptRoot "..\backend\.env.example"
if (-not (Test-Path -LiteralPath $backendEnv)) {
    Copy-Item -LiteralPath $backendExample -Destination $backendEnv
}

$appKey = (Read-Host "Enter AppKey").Trim()
$secureAccessToken = Read-Host "Enter AccessToken (input is hidden)" -AsSecureString
$accessTokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAccessToken)
try {
    $accessToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($accessTokenPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($accessTokenPtr)
}
$assetKey = (Read-Host "Enter 2D Premium AssetVirtualmanKey").Trim()

if (-not $appKey -or -not $accessToken -or -not $assetKey) {
    throw "AppKey, AccessToken and AssetVirtualmanKey are all required."
}

$values = [ordered]@{
    TENCENT_AVATAR_ENABLED = "true"
    TENCENT_AVATAR_APP_KEY = $appKey
    TENCENT_AVATAR_ACCESS_TOKEN = $accessToken
    TENCENT_AVATAR_ASSET_VIRTUALMAN_KEY = $assetKey
    TENCENT_AVATAR_PROTOCOL = "webrtc"
    TENCENT_AVATAR_DRIVER_TYPE = "3"
}

$lines = [Collections.Generic.List[string]]::new()
[IO.File]::ReadAllLines((Resolve-Path -LiteralPath $backendEnv)) | ForEach-Object { $lines.Add($_) }
foreach ($entry in $values.GetEnumerator()) {
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index += 1) {
        if ($lines[$index] -match "^$([Regex]::Escape($entry.Key))=") {
            $lines[$index] = "$($entry.Key)=$($entry.Value)"
            $found = $true
            break
        }
    }
    if (-not $found) { $lines.Add("$($entry.Key)=$($entry.Value)") }
}

$utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllLines((Resolve-Path -LiteralPath $backendEnv), $lines, $utf8NoBom)
$accessToken = $null
Write-Host "Tencent avatar settings saved to backend/.env. Restart the backend before testing." -ForegroundColor Green
