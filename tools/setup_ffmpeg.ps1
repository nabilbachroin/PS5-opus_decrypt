[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$packageVersion = "0.5.1"
$wheelUrl = "https://files.pythonhosted.org/packages/a9/1c/1b9c72bf839def47626436ea5ebaf643404f7850482c5fafd71a3deeaa94/imageio_ffmpeg-0.5.1-py3-none-win_amd64.whl"
$wheelSha256 = "1521e79e253bedbdd36a547e0cbd94a025ba0b558e17f08fea687d805a0e4698"
$installDir = Join-Path $PSScriptRoot ".vendor\ffmpeg"
$ffmpegPath = Join-Path $installDir "ffmpeg.exe"
$sourceInfoPath = Join-Path $installDir "SOURCE.txt"

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "This setup script supports only 64-bit Windows. Install FFmpeg manually and pass --ffmpeg instead."
}

if ((Test-Path -LiteralPath $ffmpegPath) -and -not $Force) {
    Write-Host "FFmpeg is already installed at:"
    Write-Host "  $ffmpegPath"
    & $ffmpegPath -version | Select-Object -First 1
    Write-Host "Use -Force to download and replace it."
    exit 0
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempDir = Join-Path $tempRoot ("ps5-opus-ffmpeg-" + [Guid]::NewGuid().ToString("N"))
$wheelPath = Join-Path $tempDir "imageio_ffmpeg.whl"
$extractDir = Join-Path $tempDir "extracted"

try {
    New-Item -ItemType Directory -Force -Path $tempDir, $extractDir | Out-Null

    Write-Host "Downloading imageio-ffmpeg $packageVersion for Windows x64..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $wheelUrl -OutFile $wheelPath -UseBasicParsing

    Write-Host "Verifying wheel SHA-256..."
    $actualHash = (Get-FileHash -LiteralPath $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $wheelSha256) {
        throw "SHA-256 mismatch. Expected $wheelSha256 but received $actualHash."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($wheelPath, $extractDir)

    $bundledFfmpeg = Get-ChildItem -LiteralPath $extractDir -Recurse -File -Filter "ffmpeg*.exe" |
        Select-Object -First 1
    if (-not $bundledFfmpeg) {
        throw "The verified wheel does not contain an FFmpeg executable."
    }

    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    Copy-Item -LiteralPath $bundledFfmpeg.FullName -Destination $ffmpegPath -Force

    @(
        "Package: imageio-ffmpeg"
        "Version: $packageVersion"
        "Source: $wheelUrl"
        "Wheel SHA-256: $wheelSha256"
        "Installed: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
    ) | Set-Content -LiteralPath $sourceInfoPath -Encoding Ascii

    Write-Host "FFmpeg installed successfully:"
    Write-Host "  $ffmpegPath"
    & $ffmpegPath -version | Select-Object -First 1
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        $resolvedTempDir = [IO.Path]::GetFullPath($tempDir)
        if (-not $resolvedTempDir.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected temporary path: $resolvedTempDir"
        }
        Remove-Item -LiteralPath $resolvedTempDir -Recurse -Force
    }
}
