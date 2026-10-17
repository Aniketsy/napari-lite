"""A numpy image in a QtCanvas: no viewer window, no layer list."""

import numpy as np

from napari_lite.components import ViewerModel
from napari_lite.qt import QtCanvas, get_qapp, run

get_qapp()
viewer = ViewerModel()
viewer.add_image(np.random.random((512, 512)), name='noise')
canvas = QtCanvas(viewer)
canvas.setWindowTitle('napari-lite canvas')
canvas.resize(800, 600)
canvas.show()
run()
