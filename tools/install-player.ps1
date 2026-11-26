# Install the Choreia player: copy the exe and create desktop + Start menu shortcuts.
$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent
$Source = Join-Path $Root 'dist\Choreia.exe'
if (-not (Test-Path $Source)) {
    throw "Сначала соберите dist\Choreia.exe"
}

$Install = Join-Path $env:LOCALAPPDATA 'Programs\Choreia'
New-Item -ItemType Directory -Force -Path $Install | Out-Null
Copy-Item $Source (Join-Path $Install 'Choreia.exe') -Force
$Exe = Join-Path $Install 'Choreia.exe'

$Shell = New-Object -ComObject WScript.Shell
$Targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)
foreach ($Dir in $Targets) {
    $Link = Join-Path $Dir 'Choreia.lnk'
    $Shortcut = $Shell.CreateShortcut($Link)
    $Shortcut.TargetPath = $Exe
    $Shortcut.WorkingDirectory = $Install
    $Shortcut.IconLocation = "$Exe,0"
    $Shortcut.Description = 'χορεία - музыкальный плеер'
    $Shortcut.Save()
    Write-Host "shortcut: $Link"
}
Write-Host "installed: $Exe"
