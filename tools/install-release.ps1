# Choreia installer: downloads the latest release and installs it for the current user.
#
#   powershell -ExecutionPolicy Bypass -Command "irm https://github.com/OddS-Programming/CHOREA/releases/latest/download/install.ps1 | iex"
#
# The app goes to %LOCALAPPDATA%\Programs\Choreia, shortcuts appear on the
# Desktop and in the Start Menu, then the player starts. Library data stays in
# %LOCALAPPDATA%\Choreia and is never touched.

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = "OddS-Programming/CHOREA"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Choreia"
$api = "https://api.github.com/repos/$repo/releases/latest"

Write-Host "Looking for the latest Choreia release..." -ForegroundColor Cyan
$release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "Choreia-Installer" }
$asset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
if (-not $asset) { throw "Release $($release.tag_name) has no application archive." }
Write-Host "Version: $($release.tag_name)" -ForegroundColor Cyan

$temp = Join-Path $env:TEMP ("choreia-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temp -Force | Out-Null
$zip = Join-Path $temp "choreia.zip"

try {
    $sizeMb = [math]::Round($asset.size / 1MB, 1)
    Write-Host "Downloading $($asset.name) ($sizeMb MB)..."
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -UseBasicParsing

    Write-Host "Unpacking..."
    Expand-Archive -Path $zip -DestinationPath $temp -Force
    $exe = Get-ChildItem -Path $temp -Recurse -Filter "Choreia.exe" | Select-Object -First 1
    if (-not $exe) { throw "The archive has no Choreia.exe." }

    # Close a running copy so files can be replaced.
    Get-Process Choreia -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -like "*Choreia\edge*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2

    Write-Host "Installing to $installDir..."
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Copy-Item -Path (Join-Path $exe.DirectoryName "*") -Destination $installDir -Recurse -Force

    $exePath = Join-Path $installDir "Choreia.exe"
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    foreach ($link in @((Join-Path $desktop "Choreia.lnk"), (Join-Path $startMenu "Choreia.lnk"))) {
        $shortcut = $shell.CreateShortcut($link)
        $shortcut.TargetPath = $exePath
        $shortcut.WorkingDirectory = $installDir
        $shortcut.IconLocation = "$exePath,0"
        $shortcut.Save()
    }

    Write-Host "Done. Starting Choreia..." -ForegroundColor Green
    Start-Process $exePath
}
finally {
    Remove-Item -Path $temp -Recurse -Force -ErrorAction SilentlyContinue
}
