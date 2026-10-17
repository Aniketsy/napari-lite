from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite._qt.layer_controls.dynamic.buttons.qt_layer_buttons_base import (
    QtLayerButtons,
)

if TYPE_CHECKING:
    import napari_lite.layers


class QtSurfaceButtons(QtLayerButtons):
    """Qt view and controls for the napari Surface layer.

    Parameters
    ----------
    layer : napari_lite.layers.Surface
        An instance of a napari Surface layer.

    Attributes
    ----------
    """

    PAN_ZOOM_ACTION_NAME = 'activate_surface_pan_zoom_mode'
    TRANSFORM_ACTION_NAME = 'activate_surface_transform_mode'

    def __init__(self, layer: napari_lite.layers.Surface) -> None:
        super().__init__(layer)
