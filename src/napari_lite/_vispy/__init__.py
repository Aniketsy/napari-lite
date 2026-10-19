import logging

# napari-lite: vispy's application (the Qt binding, or egl/osmesa for the
# headless viewer) is chosen by the front end that makes the first canvas
# (_vispy/_qt_optional.py), so that this package imports without Qt
# (docs/backends.md)

# set vispy logger to show warning and errors only
vispy_logger = logging.getLogger('vispy')
vispy_logger.setLevel(logging.WARNING)


from napari_lite._vispy.camera import VispyCamera
from napari_lite._vispy.canvas import VispyCanvas
from napari_lite._vispy.overlays.interaction_box import (
    VispySelectionBoxOverlay,
    VispyTransformBoxOverlay,
)
from napari_lite._vispy.overlays.labels_polygon import VispyLabelsPolygonOverlay
from napari_lite._vispy.overlays.scale_bar import VispyScaleBarOverlay
from napari_lite._vispy.overlays.scene_axes import VispySceneAxesOverlay
from napari_lite._vispy.overlays.text import VispyTextOverlay
from napari_lite._vispy.utils.visual import create_vispy_layer, create_vispy_overlay

__all__ = [
    'VispyCamera',
    'VispyCanvas',
    'VispyLabelsPolygonOverlay',
    'VispyScaleBarOverlay',
    'VispySceneAxesOverlay',
    'VispySelectionBoxOverlay',
    'VispyTextOverlay',
    'VispyTransformBoxOverlay',
    'create_vispy_layer',
    'create_vispy_overlay',
]
