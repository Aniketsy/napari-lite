# napari-lite: own code
"""Menu ids: napari-lite has no menus, but the copied layer list names
its context menu by napari's id."""

from __future__ import annotations

from enum import StrEnum

__all__ = ['MenuId']


class MenuId(StrEnum):
    LAYERLIST_CONTEXT = 'napari/layers/context'
