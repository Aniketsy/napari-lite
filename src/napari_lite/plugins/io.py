# napari-lite: own code
"""Reading and writing through plugins: not available in napari-lite."""

from __future__ import annotations

from typing import Any

from napari_lite.plugins import NO_READERS, NO_WRITERS


def read_data_with_plugins(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(NO_READERS)


def save_layers(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(NO_WRITERS)
