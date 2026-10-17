# napari-lite: own code
"""Stand-ins for napari's layer-list context keys.

``components/layerlist.py`` creates these and connects their ``update``
to the list's events so that app-model menus follow the selection.
napari-lite's layer menu looks at the layer list itself, so nothing is
tracked here.
"""

from __future__ import annotations

from typing import Any

__all__ = ['LayerListContextKeys', 'LayerListSelectionContextKeys']


class LayerListContextKeys:
    def __init__(self, ctx: Any = None) -> None:
        self._ctx = ctx

    def update(self, event: Any = None) -> None:
        return None


class LayerListSelectionContextKeys(LayerListContextKeys):
    pass
