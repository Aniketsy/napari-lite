# napari-lite: own code
"""Where napari-lite writes files: nowhere but the temp directory.

napari keeps settings, logs, plugin data and a cache in the user's
platform directories (the ``platformdirs`` package).  The copied code
reaches this module only for the themed icons (``resources/_icons.py``),
which napari-lite writes under the system temp directory instead.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

__all__ = ['user_cache_dir']


def user_cache_dir(*args: object, **kwargs: object) -> str:
    """The directory for files napari-lite can regenerate at any time."""
    return str(Path(tempfile.gettempdir()) / 'napari_lite')
