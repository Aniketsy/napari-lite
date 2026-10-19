# napari-lite: own code
"""A view-only canvas for images and points, without napari's layers.

You hand it arrays and it draws them.  Contrast limits, colormap,
opacity, zoom and the slice shown can be changed; nothing can be edited:
no painting, no drawing, no clicking to add points (GitHub issue #4).

    from napari_lite.view import show
    show(image)                                   # one window, 2D or N-D
    show(image, points, colormap='magma')         # points over the image

    from napari_lite.view import View, QtView
    view = View()
    img = view.add_image(stack, contrast_limits=(0, 1000))
    pts = view.add_points(coords, size=6, color='yellow')
    widget = QtView(view)                         # a QWidget for your window
    img.colormap = 'viridis'; view.current_step = (3,); view.camera.zoom(2)

Three small parts: ``View`` and its items are the model (numpy and
psygnal only); ``VispyRenderer`` draws it with vispy and is the one place
another renderer would replace; ``QtView`` adds a slider per
non-displayed axis.  Importing this package loads none of Qt or vispy:
they come with ``QtView``, ``VispyRenderer`` and ``show``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napari_lite.view._model import (
    COLORMAPS,
    Camera,
    ImageItem,
    Item,
    PointsItem,
    View,
)

if TYPE_CHECKING:
    from napari_lite.view._qt import QtView, show
    from napari_lite.view._vispy import VispyRenderer

__all__ = [
    'COLORMAPS',
    'Camera',
    'ImageItem',
    'Item',
    'PointsItem',
    'QtView',
    'View',
    'VispyRenderer',
    'show',
]

_LAZY = {
    'QtView': 'napari_lite.view._qt',
    'show': 'napari_lite.view._qt',
    'VispyRenderer': 'napari_lite.view._vispy',
}


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    from importlib import import_module

    return getattr(import_module(module), name)


def __dir__() -> list[str]:
    return sorted(__all__)
