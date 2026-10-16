# napari-lite: own code
"""Names imported by ``components/layerlist.py``; never instantiated here
because ``create_context`` returns None."""

from __future__ import annotations

from typing import Any


class _NoContext:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError('napari-lite has no app-model context')


class LayerListContextKeys(_NoContext):
    pass


class LayerListSelectionContextKeys(_NoContext):
    pass
