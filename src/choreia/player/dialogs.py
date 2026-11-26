"""Native dialogs without a GUI toolkit dependency."""

from __future__ import annotations

import subprocess

SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$owner = New-Object System.Windows.Forms.Form;"
    "$owner.TopMost = $true;"
    "$owner.ShowInTaskbar = $false;"
    "$owner.WindowState = 'Minimized';"
    "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
    "if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.SelectedPath }"
)


def pick_folder() -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", SCRIPT],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception:
        return ""
    return result.stdout.strip()


FILES_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$owner = New-Object System.Windows.Forms.Form;"
    "$owner.TopMost = $true;"
    "$owner.ShowInTaskbar = $false;"
    "$owner.WindowState = 'Minimized';"
    "$dialog = New-Object System.Windows.Forms.OpenFileDialog;"
    "$dialog.Multiselect = $true;"
    "$dialog.Filter = 'Audio|*.mp3;*.flac;*.m4a;*.m4b;*.ogg;*.opus;*.aac;*.wav|All files|*.*';"
    "if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.FileNames -join \"`n\" }"
)


def pick_files() -> list[str]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", FILES_SCRIPT],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
