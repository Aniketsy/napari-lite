# napari-lite: own code
"""utils/_colorconv.py gives the colours scikit-image gives, over the
ranges label_colormap draws from."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from napari_lite.utils import _colorconv
from napari_lite.utils.colormaps.colormap_utils import (
    LABMIN,
    LABRNG,
    LUVMIN,
    LUVRNG,
)

skimage_color = pytest.importorskip('skimage.color')


def test_luv2rgb_matches_scikit_image() -> None:
    luv = np.random.default_rng(0).random((5000, 3)) * LUVRNG + LUVMIN
    expected = skimage_color.luv2rgb(luv)
    result = _colorconv.luv2rgb(luv)
    assert result.shape == expected.shape and result.dtype == np.float64
    np.testing.assert_allclose(result, expected, rtol=1e-10, atol=1e-12)
    assert result.min() >= 0 and result.max() <= 1


def test_lab2rgb_matches_scikit_image() -> None:
    lab = np.random.default_rng(1).random((5000, 3)) * LABRNG + LABMIN
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # scikit-image warns on clipped Z
        expected = skimage_color.lab2rgb(lab)
    np.testing.assert_allclose(
        _colorconv.lab2rgb(lab), expected, rtol=1e-10, atol=1e-12
    )


def test_label_colormap_colors_are_unchanged() -> None:
    """The default Labels colours come from these conversions."""
    from napari_lite.utils.colormaps.colormap_utils import _color_random

    rgb = _color_random(50, seed=0.5)
    luv = np.random.default_rng(0).random((1, 3)) * LUVRNG + LUVMIN
    assert rgb.shape == (50, 3)
    # exactly what scikit-image produces for the same quasirandom input
    np.testing.assert_allclose(
        _colorconv.luv2rgb(luv), skimage_color.luv2rgb(luv), rtol=1e-10
    )


def test_shapes_are_checked() -> None:
    with pytest.raises(ValueError, match='3 color channels'):
        _colorconv.luv2rgb(np.zeros((4, 2)))
