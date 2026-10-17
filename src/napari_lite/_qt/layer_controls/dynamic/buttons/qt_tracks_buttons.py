from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite._qt.layer_controls.dynamic.buttons.qt_layer_buttons_base import (
    QtLayerButtons,
)
from napari_lite.layers.base._base_constants import Mode

if TYPE_CHECKING:
    import napari_lite.layers


class QtTracksButtons(QtLayerButtons):
    """Qt view and controls for the Tracks layer.

    Parameters
    ----------
    layer : napari_lite.layers.Tracks
        An instance of a Tracks layer.

    Attributes
    ----------
    """

    layer: napari_lite.layers.Tracks
    MODE = Mode
    PAN_ZOOM_ACTION_NAME = 'activate_tracks_pan_zoom_mode'
    TRANSFORM_ACTION_NAME = 'activate_tracks_transform_mode'

    def __init__(self, layer) -> None:
        super().__init__(layer)
