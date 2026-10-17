# napari-lite: own code
"""utils/_morphology.py against scipy.ndimage, for the structuring
elements and the dilation and erosion that label contours use."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils import _morphology

ndi = pytest.importorskip('scipy.ndimage')


@pytest.mark.parametrize('rank', [1, 2, 3])
@pytest.mark.parametrize('connectivity', [1, 2, 3])
def test_generate_binary_structure(rank, connectivity) -> None:
    np.testing.assert_array_equal(
        _morphology.generate_binary_structure(rank, connectivity),
        ndi.generate_binary_structure(rank, connectivity),
    )


@pytest.mark.parametrize('rank', [2, 3])
@pytest.mark.parametrize('iterations', [1, 2, 3, 4])
def test_iterate_structure(rank, iterations) -> None:
    cross = ndi.generate_binary_structure(rank, 1)
    np.testing.assert_array_equal(
        _morphology.iterate_structure(cross, iterations),
        ndi.iterate_structure(cross, iterations),
    )


@pytest.mark.parametrize('shape', [(20, 30), (9, 11, 13), (1, 25), (7,)])
@pytest.mark.parametrize('thickness', [1, 2, 3])
@pytest.mark.parametrize('seed', range(3))
def test_dilation_and_erosion_match_scipy(shape, thickness, seed) -> None:
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, 5, shape).astype(np.int32)
    cross = ndi.generate_binary_structure(labels.ndim, 1)
    diamond = ndi.iterate_structure(cross, thickness).astype(bool)
    np.testing.assert_array_equal(
        _morphology.grey_dilation(labels, footprint=cross),
        ndi.grey_dilation(labels, footprint=cross),
    )
    np.testing.assert_array_equal(
        _morphology.grey_erosion(labels, footprint=diamond),
        ndi.grey_erosion(labels, footprint=diamond),
    )


def test_contours_are_unchanged() -> None:
    from napari_lite.layers.labels._labels_utils import get_contours

    labels = np.zeros((40, 40), dtype=np.int32)
    labels[5:20, 5:25] = 1
    labels[15:35, 20:38] = 2
    for thickness in (1, 2, 3):
        contours = get_contours(labels, thickness, 0)
        cross = ndi.generate_binary_structure(2, 1)
        diamond = ndi.iterate_structure(cross, thickness).astype(bool)
        not_boundary = ndi.grey_dilation(
            labels, footprint=cross
        ) == ndi.grey_erosion(labels, footprint=diamond)
        expected = labels.copy()
        expected[not_boundary] = 0
        np.testing.assert_array_equal(contours, expected)


def test_asymmetric_footprint_is_refused() -> None:
    footprint = np.array([[0, 0, 0], [1, 1, 0], [0, 0, 0]], dtype=bool)
    with pytest.raises(ValueError, match='symmetric'):
        _morphology.grey_dilation(np.zeros((4, 4)), footprint=footprint)
