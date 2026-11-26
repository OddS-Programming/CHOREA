"""CoverFix — see what is really inside an audio file and keep exactly one cover."""

from __future__ import annotations

from .core import UnsupportedFormat, clean_file, inspect_file
from .model import FIELD_LABELS, FileReport, Picture, make_picture

__version__ = "1.0.0"

__all__ = [
    "FIELD_LABELS",
    "FileReport",
    "Picture",
    "UnsupportedFormat",
    "clean_file",
    "inspect_file",
    "make_picture",
    "__version__",
]
