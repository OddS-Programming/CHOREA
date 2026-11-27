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

FOLDER_SCRIPT = """
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.WindowState = 'Minimized'
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Выберите папку с музыкой'
$dialog.UseDescriptionForTitle = $true
$dialog.ShowNewFolderButton = $true
if ($env:CHOREIA_INITIAL -and (Test-Path -LiteralPath $env:CHOREIA_INITIAL)) {
    $dialog.SelectedPath = $env:CHOREIA_INITIAL
}
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
    [System.IO.File]::WriteAllText($env:CHOREIA_OUT, $dialog.SelectedPath, (New-Object System.Text.UTF8Encoding($false)))
}
"""


def pick_folder(initial: str = "") -> str | None:
    """Show the native Windows folder picker. Returns None when cancelled."""
    import os
    import tempfile

    out = Path(tempfile.gettempdir()) / f"choreia-pick-{os.getpid()}.txt"
    out.unlink(missing_ok=True)
    env = {**os.environ, "CHOREIA_INITIAL": initial or "", "CHOREIA_OUT": str(out)}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-WindowStyle",
                "Hidden",
                "-Command",
                FOLDER_SCRIPT,
            ],
            capture_output=True,
            text=True,
            timeout=1800,
            env=env,
            creationflags=flags,
        )
    except OSError as exc:
        raise RuntimeError("PowerShell недоступен") from exc
    except subprocess.SubprocessError as exc:
        raise RuntimeError("диалог выбора папки не открылся") from exc

    if result.returncode != 0:
        message = (result.stderr or "").strip().splitlines()
        raise RuntimeError(message[-1][:200] if message else "диалог выбора папки не открылся")
    if not out.exists():
        return None
    try:
        chosen = out.read_text(encoding="utf-8").strip()
    finally:
        out.unlink(missing_ok=True)
    return chosen or None


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
