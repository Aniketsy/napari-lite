"""The view-only canvas: a stack and points, nothing to edit.

    python examples/view_only.py

Drag to pan, wheel to zoom, the slider steps through the stack.
"""

import numpy as np

from napari_lite.view import show

rng = np.random.default_rng(0)
z, y, x = np.mgrid[0:12, 0:200, 0:260]
stack = np.exp(-((z - 6) ** 2 / 10 + ((y - 90) ** 2 + (x - 130) ** 2) / 900))
stack = (stack + 0.1 * rng.random(stack.shape)).astype(np.float32)

# points on three slices, in (slice, row, column) order like the stack
points = np.concatenate(
    [
        np.column_stack(
            [
                np.full(20, s),
                rng.uniform(10, 190, 20),
                rng.uniform(10, 250, 20),
            ]
        )
        for s in (4, 6, 8)
    ]
)

widget = show(stack, points, colormap='magma', size=6, color='cyan', run=False)
widget.view.current_step = (6,)
widget.view.items[0].contrast_limits = (0.0, 1.0)

from napari_lite import run  # noqa: E402

run()
