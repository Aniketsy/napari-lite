# napari-lite: own code
"""napari-lite interprets data as napari does (docs/design.md): RGB is
guessed from the last axis, multiscale from a list of arrays, the channel
axis is never guessed, and a path is not read."""

from __future__ import annotations

import numpy as np
import pytest

RGB_CASES = [
    ((64, 64, 3), True),
    ((64, 64, 4), True),
    ((5, 64, 64, 3), True),
    ((64, 64, 5), False),
    ((64, 3), False),  # 2D data is never RGB
    ((20, 20, 3), False),  # sides of 30 or less: a small 3D stack
]


@pytest.mark.parametrize(('shape', 'rgb'), RGB_CASES)
def test_rgb_is_guessed_from_the_last_axis(shape, rgb) -> None:
    from napari_lite.layers import Image

    assert Image(np.zeros(shape)).rgb is rgb


def test_rgb_guess_can_be_overridden() -> None:
    from napari_lite.layers import Image

    assert Image(np.zeros((64, 64, 3)), rgb=False).rgb is False
    assert Image(np.zeros((64, 64, 3)), rgb=False).ndim == 3


def test_channel_axis_is_never_guessed() -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Image

    viewer = ViewerModel()
    one = viewer.add_image(np.zeros((3, 64, 64)))
    assert isinstance(one, Image)
    assert one.ndim == 3
    three = viewer.add_image(np.zeros((3, 64, 64)), channel_axis=0)
    assert isinstance(three, list)
    assert len(three) == 3
    assert all(layer.ndim == 2 for layer in three)


def test_multiscale_is_guessed_from_a_list() -> None:
    from napari_lite.layers import Image

    pyramid = [np.zeros((64, 64)), np.zeros((32, 32)), np.zeros((16, 16))]
    assert Image(pyramid).multiscale is True
    assert Image(np.zeros((64, 64))).multiscale is False
    assert Image(np.zeros((64, 64)), multiscale=False).multiscale is False


def test_integer_data_stays_an_image() -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Image, Labels

    viewer = ViewerModel()
    layer = viewer.add_image(np.zeros((64, 64), dtype=np.uint8))
    assert isinstance(layer, Image)
    assert isinstance(viewer.add_labels(np.zeros((64, 64), int)), Labels)


def test_a_path_is_not_read(tmp_path) -> None:
    from napari_lite.components import ViewerModel

    path = tmp_path / 'image.tif'
    path.write_bytes(b'')
    with pytest.raises(NotImplementedError, match='no file readers'):
        ViewerModel().open(str(path))


@pytest.mark.parametrize(('shape', 'rgb'), RGB_CASES)
def test_same_rgb_guess_as_napari(shape, rgb) -> None:
    napari = pytest.importorskip('napari')
    from napari_lite.layers import Image

    assert napari.layers.Image(np.zeros(shape)).rgb is rgb
    assert (
        Image(np.zeros(shape)).rgb is napari.layers.Image(np.zeros(shape)).rgb
    )
