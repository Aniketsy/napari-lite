# napari-lite: own code
"""Where napari calls plugins: a built-in reader and built-in samples.

napari discovers readers, writers, sample data and widgets through npe2
plugins.  napari-lite has no plugin manager (the position agreed in napari
issue 5940).  It reads a few common formats itself (``READABLE``: images
through imageio, ``.npy``/``.npz`` through numpy, TIFF through tifffile
when installed, imageio otherwise; ``io.py``) and ships a few samples
(``samples.py``), so ``viewer.open``, drag and drop, Ctrl+O and
``viewer.open_sample`` work for those.  Everything else, and every
writer, raises a clear error: load or save the data with your own library.

The functions the copied core imports from here exist so the imports
succeed.
"""

from __future__ import annotations

import os
from typing import Any

from napari_lite.errors.reader_errors import NoAvailableReaderError

READER = 'napari-lite'
"""The built-in reader's name (``viewer.open(path, plugin='napari-lite')``;
``'napari'`` is accepted too, so scripts written for napari's built-in
reader run)."""

READABLE = frozenset(
    {
        '.png',
        '.jpg',
        '.jpeg',
        '.bmp',
        '.gif',
        '.webp',
        '.tif',
        '.tiff',
        '.npy',
        '.npz',
    }
)
"""File suffixes the built-in reader opens."""

NO_READERS = (
    'napari-lite reads png, jpg, bmp, gif, webp, tif, npy and npz files '
    'with its built-in reader and has no plugins: for anything else load '
    'the data with your own library (tifffile, imageio, zarr, ...) and use '
    'viewer.add_image(array).'
)
NO_WRITERS = (
    'napari-lite has no file writers: save layer.data with your own library '
    '(tifffile, imageio, numpy, ...).'
)


class NoPluginsError(NotImplementedError, ValueError):
    """Raised where napari would call a plugin.

    Also a ValueError, like napari's own "no reader found" errors, so code
    written for napari can catch it the same way.
    """


class NoReadersError(NoAvailableReaderError, NotImplementedError):
    """Raised where napari would look for a reader plugin.

    Also napari's ``NoAvailableReaderError`` (with ``paths``), so code and
    tests written for napari's "no plugin found" error keep working.
    """

    def __init__(self, message: str, paths: list[Any]) -> None:
        super().__init__(message, paths)


def no_plugins(message: str, *what: Any) -> NoPluginsError:
    """Build the error, naming what was asked for (paths, plugin names)."""
    asked = ', '.join(str(w) for w in what if w)
    return NoPluginsError(
        f'{message} Requested: {asked}' if asked else message
    )


def no_readers(paths: Any) -> NoReadersError:
    """The reader error for ``paths`` (one path or a list)."""
    paths = list(paths) if isinstance(paths, list | tuple) else [paths]
    shown = ', '.join(str(p) for p in paths)
    return NoReadersError(
        f'No plugin found capable of reading {shown}. {NO_READERS}', paths
    )


def is_readable(path: Any) -> bool:
    """True if the built-in reader opens files with this suffix."""
    return os.path.splitext(os.fspath(path))[1].lower() in READABLE


def readers_for(path: Any) -> dict[str, str]:
    """The readers of ``path`` as napari lists them (name to description):
    the built-in one, or none."""
    if is_readable(path):
        return {READER: 'napari-lite built-in reader'}
    return {}


def available_samples() -> tuple[tuple[str, str], ...]:
    """``(plugin, sample)`` pairs of the built-in samples, as napari's
    ``available_samples`` lists them."""
    from napari_lite.plugins.samples import SAMPLES

    return tuple((READER, name) for name in SAMPLES)


__all__ = [
    'NO_READERS',
    'NO_WRITERS',
    'READABLE',
    'READER',
    'NoPluginsError',
    'NoReadersError',
    'available_samples',
    'is_readable',
    'no_plugins',
    'no_readers',
    'readers_for',
]
