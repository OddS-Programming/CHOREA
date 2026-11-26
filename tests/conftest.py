from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))


@pytest.fixture
def asset():
    from helpers import copy_asset

    def _make(ext: str, dest: Path) -> Path:
        return copy_asset(ext, dest)

    return _make
