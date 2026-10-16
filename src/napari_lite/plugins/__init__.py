# napari-lite: own code
"""No plugins.

napari discovers readers, writers, sample data and widgets through npe2
plugins.  napari-lite has no plugin manager (the position agreed in napari
issue 5940): load data with your own library and call ``add_image`` or
another ``add_*`` method.  The functions the copied core imports from here
exist so the imports succeed, and raise a clear error when called.
"""

from __future__ import annotations

from typing import Any

NO_READERS = (
    'napari-lite has no file readers: load data with your own library '
    '(tifffile, imageio, zarr, ...) and use viewer.add_image(array).'
)
NO_WRITERS = (
    'napari-lite has no file writers: save layer.data with your own library '
    '(tifffile, imageio, numpy, ...).'
)
NO_SAMPLES = (
    'napari-lite has no sample data: build an array with numpy or '
    'scikit-image and use viewer.add_image(array).'
)


class NoPluginsError(NotImplementedError, ValueError):
    """Raised where napari would call a plugin.

    Also a ValueError, like napari's own "no reader found" errors, so code
    written for napari can catch it the same way.
    """


def no_plugins(message: str, *what: Any) -> NoPluginsError:
    """Build the error, naming what was asked for (paths, sample names)."""
    asked = ', '.join(str(w) for w in what if w)
    return NoPluginsError(
        f'{message} Requested: {asked}' if asked else message
    )


def available_samples() -> tuple:
    """napari-lite ships no sample data."""
    return ()


__all__ = [
    'NO_READERS',
    'NO_SAMPLES',
    'NO_WRITERS',
    'NoPluginsError',
    'available_samples',
    'no_plugins',
]
