from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite._qt.layer_controls.dynamic.buttons.qt_layer_buttons_base import (
    QtLayerButtons,
)
from napari_lite.layers.base._base_constants import Mode

if TYPE_CHECKING:
    import napari_lite.layers


class QtVectorsButtons(QtLayerButtons):
    """Qt view and controls for the napari Vectors layer.

    Parameters
    ----------
    layer : napari_lite.layers.Vectors
        An instance of a napari Vectors layer.

    Attributes
    ----------
    """

    layer: napari_lite.layers.Vectors
    MODE = Mode
    PAN_ZOOM_ACTION_NAME = 'activate_tracks_pan_zoom_mode'
    TRANSFORM_ACTION_NAME = 'activate_tracks_transform_mode'

    def __init__(self, layer) -> None:
        super().__init__(layer)
