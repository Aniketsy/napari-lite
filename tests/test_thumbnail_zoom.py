# napari-lite: own code
"""The numpy thumbnail zoom returns what ``scipy.ndimage.zoom(order=0)``
returns, for the zoom factors the Image and Labels thumbnails use."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils._zoom import zoom

THUMBNAIL = np.array([32, 32])

SHAPES = [
    (64, 64),
    (191, 254),
    (111, 138),
    (2026, 78),
    (1, 500),
    (500, 1),
    (3, 3),
    (40, 2048),
    (7, 1000),
]
DTYPES = [np.uint8, np.uint16, np.int32, np.float32, np.float64, np.bool_]


def thumbnail_factor(shape: tuple[int, ...]) -> tuple[float, ...]:
    """The zoom factor as ``Image._update_thumbnail`` computes it."""
    raw = np.divide(THUMBNAIL, shape[:2]).min()
    new_shape = np.clip(raw * np.array(shape[:2]), 1, THUMBNAIL)
    return tuple(new_shape / shape[:2])


def scipy_zoom():
    return pytest.importorskip('scipy.ndimage')


@pytest.mark.parametrize('dtype', DTYPES)
@pytest.mark.parametrize('shape', SHAPES)
def test_matches_scipy(shape, dtype) -> None:
    # mode='nearest': scipy's default constant mode zeroes the last row or
    # column when float error puts its coordinate past the edge; the numpy
    # zoom keeps the edge pixel instead (module docstring)
    ndi = scipy_zoom()
    image = (np.random.default_rng(0).random(shape) * 200).astype(dtype)
    factor = thumbnail_factor(shape)
    expected = ndi.zoom(
        image, factor, prefilter=False, order=0, mode='nearest'
    )
    result = zoom(image, factor, prefilter=False, order=0)
    assert result.dtype == expected.dtype
    np.testing.assert_array_equal(result, expected)


def test_rgb_keeps_the_color_axis() -> None:
    ndi = scipy_zoom()
    image = np.random.default_rng(1).integers(0, 255, (300, 200, 3), np.uint8)
    factor = (*thumbnail_factor(image.shape), 1)
    expected = ndi.zoom(
        image, factor, prefilter=False, order=0, mode='nearest'
    )
    np.testing.assert_array_equal(zoom(image, factor, order=0), expected)


@pytest.mark.parametrize(
    ('n_in', 'n_out'),
    [
        (3, 2),
        (4, 3),
        (6, 5),
        (2, 7),
        (1, 5),
        (5, 1),
        (10, 32),
        (33, 32),
        (2048, 32),
    ],
)
def test_index_mapping(n_in, n_out) -> None:
    """Up- and downsampling, single pixels, exact halves."""
    ndi = scipy_zoom()
    column = np.arange(n_in, dtype=np.int32)[:, None]
    factor = (n_out / n_in, 1)
    expected = ndi.zoom(
        column, factor, prefilter=False, order=0, mode='nearest'
    )
    np.testing.assert_array_equal(zoom(column, factor), expected)


def test_edge_pixel_is_kept() -> None:
    """254 rows into 32: scipy's constant mode blacks out the last row."""
    image = np.ones((254, 10), dtype=np.uint8)
    result = zoom(
        image, thumbnail_factor(image.shape), prefilter=False, order=0
    )
    assert result.shape == (32, 1)
    assert result.all()


def test_only_nearest_neighbour() -> None:
    with pytest.raises(NotImplementedError):
        zoom(np.zeros((4, 4)), 0.5, order=1)
    with pytest.raises(NotImplementedError):
        zoom(np.zeros((4, 4)), 0.5, grid_mode=True)
    with pytest.raises(RuntimeError):
        zoom(np.zeros((4, 4)), (0.5, 0.5, 0.5))
