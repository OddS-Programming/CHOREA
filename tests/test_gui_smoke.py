from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from choreia.gui import App
import helpers


@pytest.fixture(scope="session")
def tk_root():
    # One root per process: a second Tk() after the first is destroyed breaks
    # Tcl's library lookup on Windows.
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
    assert window.track_list is not None
    assert set(window.vars) == {"title", "artist", "album", "album_artist", "track", "disc", "year", "genre"}


def test_adding_a_file_shows_it_in_the_list(window: App, tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.add_mp3_pictures(path)

    window.add_paths([path])

    assert len(window.order) == 1
    assert len(window.track_list.reports) == 1
    assert window.current is not None
    assert window.chosen is not None and window.chosen.type == 3
    assert window.vars["title"].get() == "Original title"


def test_open_folder_lists_every_track(window: App, tmp_path: Path, asset) -> None:
    folder = tmp_path / "album"
    folder.mkdir()
    helpers.copy_asset("mp3", folder / "01-song.mp3")
    helpers.copy_asset("flac", folder / "02-song.flac")

    window.load_folder(folder)

    assert len(window.order) == 2
    assert len(window.track_list.reports) == 2


def test_multi_selection_applies_only_changed_fields(window: App, tmp_path: Path, asset) -> None:
    from choreia.core import inspect_file

    folder = tmp_path / "album"
    folder.mkdir()
    first = helpers.copy_asset("mp3", folder / "01.mp3")
    second = helpers.copy_asset("mp3", folder / "02.mp3")
    helpers.add_mp3_pictures(first)
    helpers.add_mp3_pictures(second)
    window.load_folder(folder)

    window.track_list.select_paths({first.resolve(), second.resolve()})
    assert len(window.selection) == 2
    assert window.vars["title"].get() == "Original title"

    window._confirm = lambda *args, **kwargs: True
    window.vars["artist"].set("Общий исполнитель")
    window.apply_current()

    reports = [inspect_file(first), inspect_file(second)]
    assert [report.fields["artist"] for report in reports] == ["Общий исполнитель"] * 2
    assert [report.fields["title"] for report in reports] == ["Original title"] * 2
    assert [len(report.pictures) for report in reports] == [1, 1]


def test_search_filters_the_list(window: App, tmp_path: Path, asset) -> None:
    folder = tmp_path / "album"
    folder.mkdir()
    helpers.copy_asset("mp3", folder / "alpha.mp3")
    helpers.copy_asset("mp3", folder / "beta.mp3")
    window.load_folder(folder)

    window.search_var.set("alpha")

    assert len(window.track_list.reports) == 1
    assert window.track_list.reports[0].path.name == "alpha.mp3"
