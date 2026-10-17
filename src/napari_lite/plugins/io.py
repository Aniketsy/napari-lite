# napari-lite: own code
"""Reading and writing through plugins: not available in napari-lite."""

from __future__ import annotations

from typing import Any

from napari_lite.plugins import NO_WRITERS, no_plugins, no_readers


def read_data_with_plugins(paths: Any = (), *args: Any, **kwargs: Any) -> Any:
    raise no_readers(paths)


def save_layers(path: Any = None, *args: Any, **kwargs: Any) -> Any:
    raise no_plugins(NO_WRITERS, path)
