__doc__ = """
"""
import importlib.metadata

from compact_json.formatter import Formatter, EolStyle

__version__ = importlib.metadata.version("compact-json")


def _get_version():
    return __version__
