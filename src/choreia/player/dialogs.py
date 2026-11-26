"""Native dialogs without a GUI toolkit dependency."""

from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path


def recycle(path: Path) -> bool:
    """Move a file to the Windows Recycle Bin via SHFileOperation."""
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x40
    FOF_NOCONFIRMATION = 0x10
    FOF_SILENT = 0x4

    operation = SHFILEOPSTRUCTW()
    operation.hwnd = None
    operation.wFunc = FO_DELETE
    operation.pFrom = str(path) + "\0\0"
    operation.pTo = None
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    return result == 0

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
