from __future__ import annotations

import json
from pathlib import Path

from choreia.app import load_credentials
from choreia.library.db import Library


def test_credentials_seed_the_token_only_once(tmp_path: Path) -> None:
    (tmp_path / "credentials.json").write_text(
        json.dumps({"genius_token": "file-token"}), encoding="utf-8"
    )
    library = Library(tmp_path / "library.db")

    load_credentials(library, tmp_path)
    assert library.setting("genius_token") == "file-token"

    library.set_setting("genius_token", "")
    load_credentials(library, tmp_path)
    assert library.setting("genius_token") == ""

    library.set_setting("genius_token", "ui-token")
    load_credentials(library, tmp_path)
    assert library.setting("genius_token") == "ui-token"
    library.close()


def test_credentials_without_a_file_keep_settings(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.db")
    library.set_setting("genius_token", "ui-token")

    load_credentials(library, tmp_path)

    assert library.setting("genius_token") == "ui-token"
    library.close()
