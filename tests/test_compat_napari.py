# napari-lite: own code
"""One-line swap: the same script gives the same layers with napari and
with napari-lite.  Runs only where napari is installed."""

from __future__ import annotations

import numpy as np
import pytest

napari = pytest.importorskip('napari')


def _script(mod):
    """A small viewing script written against the napari API."""
    rng = np.random.default_rng(0)
    image = rng.random((3, 16, 16))
    labels = (rng.random((16, 16)) > 0.5).astype(np.uint8)
    points = rng.random((5, 2)) * 16

    viewer, layer = mod.imshow(
        image, name='img', colormap='magma', contrast_limits=(0, 1), show=False
    )
    try:
        viewer.add_labels(labels, name='lbl', opacity=0.5)
        viewer.add_points(points, name='pts', size=3)
        viewer.add_shapes(
            [np.array([[0, 0], [0, 4], [4, 4]])], shape_type='polygon'
        )
        viewer.dims.current_step = (1, 0, 0)
        summary = {
            'layers': [
                (
                    type(lay).__name__,
                    lay.name,
                    tuple(lay.data.shape)
                    if hasattr(lay.data, 'shape')
                    else len(lay.data),
                )
                for lay in viewer.layers
            ],
            'image_colormap': layer.colormap.name,
            'image_contrast': tuple(layer.contrast_limits),
            'labels_opacity': viewer.layers['lbl'].opacity,
            'dims_ndim': viewer.dims.ndim,
            'dims_step': tuple(viewer.dims.current_step),
            'dims_displayed': tuple(viewer.dims.displayed),
            'extent': np.round(viewer.layers.extent.world, 6).tolist(),
            'status_keys': sorted(viewer._calc_status_from_cursor()[0].keys())
            if viewer._calc_status_from_cursor()
            else None,
        }
    finally:
        viewer.close()
    return summary


def test_same_layers_with_napari_and_napari_lite(qtbot) -> None:
    import napari_lite

    assert _script(napari_lite) == _script(napari)
