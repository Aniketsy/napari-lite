# napari-lite: own code
"""Visual comparison with napari: the same scene rendered by napari and by
napari-lite gives the same image, for every layer type in 2D and 3D.

Runs only where napari is installed (locally, in a napari environment).
No reference images are stored: both renderings are made in the same
process, with the same vispy and the same GPU, and compared directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

napari = pytest.importorskip('napari')

# mean absolute difference per channel (0-255) allowed between the two
# renderings, and the fraction of pixels that may differ by more than 16
MEAN_TOLERANCE = 1.0
PIXEL_TOLERANCE = 0.005


def _rng() -> np.random.Generator:
    return np.random.default_rng(0)


def add_image(viewer: Any) -> None:
    viewer.add_image(
        _rng().random((6, 32, 32)),
        colormap='magma',
        contrast_limits=(0, 1),
        name='image',
    )


def add_image_rgb(viewer: Any) -> None:
    viewer.add_image(
        (_rng().random((6, 32, 32, 3)) * 255).astype(np.uint8), name='rgb'
    )


def add_image_multiscale(viewer: Any) -> None:
    rng = _rng()
    viewer.add_image(
        [rng.random((64, 64)), rng.random((32, 32)), rng.random((16, 16))],
        multiscale=True,
        colormap='viridis',
        name='multiscale',
    )


def add_labels(viewer: Any) -> None:
    labels = np.zeros((6, 32, 32), dtype=np.uint8)
    labels[:, 2:12, 2:12] = 1
    labels[:, 10:24, 8:20] = 2
    labels[2:5, 20:30, 20:30] = 3
    viewer.add_labels(labels, name='labels')


def add_points(viewer: Any) -> None:
    rng = _rng()
    viewer.add_points(
        rng.random((20, 3)) * (6, 32, 32),
        size=3,
        face_color='cyan',
        border_color='white',
        name='points',
    )


def add_shapes(viewer: Any) -> None:
    viewer.add_shapes(
        [
            np.array([[2, 2], [2, 14], [10, 14], [10, 2]]),
            np.array([[18, 4], [30, 12]]),
            np.array([[14, 16], [16, 30], [26, 28], [28, 18]]),
        ],
        shape_type=['rectangle', 'line', 'polygon'],
        edge_color='yellow',
        face_color='magenta',
        edge_width=1,
        name='shapes',
    )


def add_vectors(viewer: Any) -> None:
    rng = _rng()
    data = np.zeros((20, 2, 3))
    data[:, 0] = rng.random((20, 3)) * (6, 32, 32)
    data[:, 1, 1:] = rng.random((20, 2)) * 8 - 4
    viewer.add_vectors(data, edge_color='orange', name='vectors')


def add_surface(viewer: Any) -> None:
    # all vertices in slice 2, the slice the 2D view shows: in 2D napari
    # draws only the faces whose vertices lie in the current slice
    vertices = np.array(
        [[2, 0, 0], [2, 0, 32], [2, 32, 0], [2, 32, 32], [2, 16, 16]], float
    )
    faces = np.array([[0, 1, 2], [1, 2, 3], [2, 3, 4]])
    values = np.linspace(0, 1, len(vertices))
    viewer.add_surface((vertices, faces, values), name='surface')


def add_tracks(viewer: Any) -> None:
    data = np.array(
        [[0, t, 4 + 3 * t, 4 + 4 * t] for t in range(6)]
        + [[1, t, 28 - 3 * t, 6 + 4 * t] for t in range(6)],
        dtype=float,
    )
    viewer.add_tracks(data, name='tracks')


SCENES = {
    'image': add_image,
    'image_rgb': add_image_rgb,
    'image_multiscale': add_image_multiscale,
    'labels': add_labels,
    'points': add_points,
    'shapes': add_shapes,
    'vectors': add_vectors,
    'surface': add_surface,
    'tracks': add_tracks,
}


def render(module: Any, scene: str, ndisplay: int, qtbot: Any) -> np.ndarray:
    """The scene as napari's export_figure makes it: the full data extent,
    one pixel per data pixel, so both renderings have the same size.

    The window is shown and the canvas's first draw is waited for: a canvas
    that has not painted yet has no GL context and renders black."""
    viewer = module.Viewer(show=True, ndisplay=ndisplay)
    try:
        qtbot.waitExposed(viewer.window._qt_window)
        SCENES[scene](viewer)
        drawn: list[Any] = []
        canvas = viewer.window._qt_viewer.canvas
        canvas._scene_canvas.events.draw.connect(drawn.append)
        canvas.native.update()
        qtbot.waitUntil(lambda: bool(drawn), timeout=10000)
        if ndisplay == 3:
            viewer.dims.ndisplay = 3
            viewer.scene.camera.angles = (10, -20, 30)
        viewer.dims.current_step = (2, *viewer.dims.current_step[1:])
        return viewer.export_figure(scale_factor=4)
    finally:
        viewer.close()


@pytest.mark.parametrize('ndisplay', [2, 3])
@pytest.mark.parametrize('scene', list(SCENES))
def test_same_rendering_as_napari(qtbot, scene: str, ndisplay: int) -> None:
    import napari_lite

    ours = render(napari_lite, scene, ndisplay, qtbot)
    theirs = render(napari, scene, ndisplay, qtbot)
    assert ours.shape == theirs.shape, (ours.shape, theirs.shape)
    assert ours.shape[-1] == 4
    diff = np.abs(ours.astype(np.int16) - theirs.astype(np.int16))
    mean = diff.mean()
    pixels = (diff.max(axis=-1) > 16).mean()
    assert mean <= MEAN_TOLERANCE, f'mean difference {mean:.3f}'
    assert pixels <= PIXEL_TOLERANCE, f'{pixels:.2%} of the pixels differ'
    # neither image is blank: an unexposed canvas renders black, and two
    # black images would compare equal (sparse scenes such as points or
    # vectors cover only a few hundred pixels)
    for image in (ours, theirs):
        assert (image[..., :3].max(axis=-1) > 0).sum() >= 50, 'blank image'
