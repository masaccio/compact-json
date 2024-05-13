"""JSON formatting package."""

import importlib.metadata

from compact_json.formatter import EolStyle, Formatter  # noqa: F401

__version__ = importlib.metadata.version("compact-json")


def _get_version() -> str:
    return __version__
