"""A napari-lite viewer with one layer of each kind: run it and look around.

    python examples/viewer_demo.py

Keys: arrows step through the stack, Ctrl+Y toggles 3D, Ctrl+G grid mode,
Ctrl+R resets the view, Ctrl+Alt+/ lists every key binding.  Select the
labels layer in code (``viewer.layers.selection.active = labels``) and
press P to paint, E to erase, F to fill.
"""

import numpy as np

import napari_lite as napari

rng = np.random.default_rng(0)

# a 3D stack: a bright sphere moving through the slices
z, y, x = np.mgrid[0:16, 0:256, 0:256]
center = np.stack([np.full_like(z, 8), 96 + 4 * z, 96 + 4 * z])
stack = np.exp(
    -(
        (z - center[0]) ** 2 / 20
        + ((y - center[1]) ** 2 + (x - center[2]) ** 2) / 1200
    )
)
stack = (stack + 0.08 * rng.random(stack.shape)).astype(np.float32)

labels = np.zeros((256, 256), dtype=np.uint8)
labels[40:100, 150:220] = 1
labels[150:230, 40:110] = 2
labels[170:210, 170:240] = 3

points = rng.uniform(20, 236, size=(30, 2))
shapes = [
    np.array([[20, 20], [20, 90], [60, 90], [60, 20]]),  # rectangle
    np.array([[200, 130], [230, 160], [200, 190], [170, 160]]),  # polygon
    np.array([[120, 10], [140, 60], [110, 120]]),  # path
]
origins = rng.uniform(0, 256, size=(40, 2))
directions = rng.normal(size=(40, 2)) * 15
vectors = np.stack([origins, directions], axis=1)

viewer = napari.Viewer(title='napari-lite demo')
viewer.add_image(
    stack, name='sphere', colormap='magma', contrast_limits=(0, 1)
)
viewer.add_labels(labels, name='labels', opacity=0.6)
viewer.add_points(points, name='points', size=8, face_color='cyan')
viewer.add_shapes(
    shapes,
    name='shapes',
    shape_type=['rectangle', 'polygon', 'path'],
    edge_color='yellow',
    face_color='transparent',
    edge_width=2,
)
viewer.add_vectors(
    vectors, name='vectors', edge_color='orange', edge_width=1.5
)
viewer.canvas.overlays.scale_bar.visible = True
viewer.scene.overlays.axes.visible = True
viewer.dims.current_step = (8, 0, 0)
viewer.status = 'arrows: slices, Ctrl+Y: 3D, Ctrl+G: grid, Ctrl+Alt+/: keys'

napari.run()
