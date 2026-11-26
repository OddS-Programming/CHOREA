from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from choreia.core import inspect_file
import helpers

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "choreia", *args],
        capture_output=True,
        text=True,
        env=ENV,
        cwd=ROOT,
    )


def test_inspect_json_shape(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.add_mp3_pictures(path)

    result = run("inspect", "--json", str(path))

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["container"] == "mp3"
    assert len(data["pictures"]) == 3
    assert "regions" in data
    assert "warnings" in data


def test_clean_keep_index(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    payloads = helpers.add_mp3_pictures(path)

    result = run("clean", str(path), "--keep", "2", "--title", "CLI", "--no-backup")

    assert result.returncode == 0, result.stderr
    after = inspect_file(path)
    assert len(after.pictures) == 1
    assert after.pictures[0].data == payloads[2]
    assert after.fields["title"] == "CLI"


def test_dry_run_changes_nothing(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.add_mp3_pictures(path)
    before = path.read_bytes()

    result = run("clean", str(path), "--keep", "0", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == before


def test_inspect_human_output_lists_pictures(tmp_path: Path, asset) -> None:
    path = asset("mp3", tmp_path / "tone.mp3")
    helpers.add_mp3_pictures(path)

    result = run("inspect", str(path))

    assert result.returncode == 0, result.stderr
    assert "Front Cover" in result.stdout
    assert "ID3v2.3" in result.stdout
