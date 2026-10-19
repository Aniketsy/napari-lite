# napari-lite: own code
"""A figure from a viewer that has no window: ``Viewer(gui=None)``.

Runs wherever a GL context can be made: a desktop, CI, a server.  On
Linux vispy draws through EGL or OSMesa with no Qt in the process;
elsewhere Qt draws into a widget kept off the screen.  ``screenshot``
and ``export_figure`` work; ``viewer.window`` and ``show`` do not exist.
Writes headless_figure.png where it runs.
"""

import numpy as np

from napari_lite import Viewer

yy, xx = np.mgrid[0:200, 0:300]
waves = np.sin(xx / 18.0) * np.cos(yy / 14.0)

viewer = Viewer(gui=None)
viewer.add_image(waves, colormap='viridis', name='waves')
viewer.add_points(
    [[40, 60], [100, 150], [160, 240]],
    size=18,
    face_color='orange',
    border_color='white',
    text={'string': ['one', 'two', 'three'], 'color': 'white', 'size': 12},
    name='marks',
)
viewer.scale_bar.visible = True

# one data pixel per figure pixel, times two
figure = viewer.export_figure('headless_figure.png', scale_factor=2)
print('wrote headless_figure.png', figure.shape)
viewer.close()
