from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from coverfix.gui import App
import helpers


@pytest.fixture(scope="session")
def tk_root():
    # A single root per process: creating a second Tk() after destroying the
    # first one breaks Tcl's library lookup on Windows.
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - only on a headless machine
        pytest.skip(f"cannot create Tk root: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture
def window(tk_root: tk.Tk):
    top = tk.Toplevel(tk_root)
    top.withdraw()
    app = App(top, dnd_available=False)
    try:
        yield app
    finally:
        top.destroy()


def test_window_builds(window: App) -> None:
    assert window.file_tree is not None
    assert set(window.vars) == {"title", "artist", "album", "album_artist", "track", "disc", "year", "genre"}


def test_adding_a_file_shows_its_covers(window: App, tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.add_mp3_pictures(path)

    window.add_paths([path])

    assert len(window.reports) == 1
    assert window.chosen is not None
    assert window.chosen.type == 3
    assert len(window.picture_tree.get_children()) == 3
    assert window.vars["title"].get() == "Original title"
