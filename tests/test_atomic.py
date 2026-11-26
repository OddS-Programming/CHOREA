from __future__ import annotations

import os
from pathlib import Path

from choreia import atomic


def test_replace_retries_a_transient_lock(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "track.mp3"
    target.write_bytes(b"old")
    calls = {"count": 0}
    real_replace = os.replace

    def flaky(source, destination):
        calls["count"] += 1
        if calls["count"] < 3:
            raise PermissionError(5, "locked by another process")
        return real_replace(source, destination)

    monkeypatch.setattr(atomic.os, "replace", flaky)
    monkeypatch.setattr(atomic.time, "sleep", lambda seconds: None)

    atomic.write_with_backup(target, lambda temp: temp.write_bytes(b"new"), backup=False)

    assert target.read_bytes() == b"new"
    assert calls["count"] == 3
    assert not (tmp_path / "track.mp3.choreia-tmp").exists()


def test_replace_gives_up_and_keeps_the_original(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "track.mp3"
    target.write_bytes(b"old")

    def always_locked(source, destination):
        raise PermissionError(5, "still locked")

    monkeypatch.setattr(atomic.os, "replace", always_locked)
    monkeypatch.setattr(atomic, "_windows_replace", lambda temporary, target: False)
    monkeypatch.setattr(atomic.time, "sleep", lambda seconds: None)

    try:
        atomic.write_with_backup(target, lambda temp: temp.write_bytes(b"new"), backup=False)
    except PermissionError:
        pass
    else:  # pragma: no cover - the retry loop must surface the failure
        raise AssertionError("expected PermissionError")

    assert target.read_bytes() == b"old"
    assert not (tmp_path / "track.mp3.choreia-tmp").exists()
