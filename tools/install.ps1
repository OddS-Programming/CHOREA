# Copy CoverFix.exe into %LOCALAPPDATA%\Programs and create desktop + Start menu shortcuts.
$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent
$Source = Join-Path $Root 'dist\CoverFix.exe'
if (-not (Test-Path $Source)) {
    throw "Сначала соберите exe: $Source"
}

$Install = Join-Path $env:LOCALAPPDATA 'Programs\CoverFix'
New-Item -ItemType Directory -Force -Path $Install | Out-Null
Copy-Item $Source (Join-Path $Install 'CoverFix.exe') -Force
$Exe = Join-Path $Install 'CoverFix.exe'

$Shell = New-Object -ComObject WScript.Shell
$Targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)
foreach ($Dir in $Targets) {
    $Link = Join-Path $Dir 'CoverFix.lnk'
    $Shortcut = $Shell.CreateShortcut($Link)
    $Shortcut.TargetPath = $Exe
    $Shortcut.WorkingDirectory = $Install
    $Shortcut.IconLocation = "$Exe,0"
    $Shortcut.Description = 'CoverFix - обложки и теги аудиофайлов'
    $Shortcut.Save()
    Write-Host "shortcut: $Link"
}

Write-Host "installed: $Exe"
Write-Host "Windows Search (Win+S) finds it as CoverFix after a few seconds."
