"""Layers are the viewable objects that can be added to a viewer.

Custom layers must inherit from Layer and pass along the
`visual node <https://vispy.org/api/vispy.scene.visuals.html>`_
to the super constructor.
"""

import inspect as _inspect

from napari_lite.layers.base import Layer, LayerLock
from napari_lite.layers.image import Image
from napari_lite.layers.labels import Labels
from napari_lite.layers.points import Points
from napari_lite.layers.shapes import Shapes
from napari_lite.layers.surface import Surface
from napari_lite.layers.tracks import Tracks
from napari_lite.layers.vectors import Vectors
from napari_lite.utils.misc import all_subclasses as _all_subcls

# isabstract check is to exclude _ImageBase class
NAMES: set[str] = {
    subclass.__name__.lower()
    for subclass in _all_subcls(Layer)
    if not _inspect.isabstract(subclass)
}

__all__ = [
    'NAMES',
    'Image',
    'Labels',
    'Layer',
    'LayerLock',
    'Points',
    'Shapes',
    'Surface',
    'Tracks',
    'Vectors',
]
