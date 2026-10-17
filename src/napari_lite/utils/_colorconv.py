# napari-lite: own code
"""CIE-Luv and CIE-Lab to sRGB, as scikit-image converts them.

``label_colormap`` draws its colours uniformly from the Luv space (or the
Lab space) and converts them with ``skimage.color.luv2rgb`` and
``lab2rgb``.  For the D65 illuminant and the 2° observer that scikit-image
defaults to, those are a few array operations, copied here so that
scikit-image is not a dependency; the one deviation is that an out-of-gamut
Lab colour is clipped silently where scikit-image also warns.
``tests/test_colorconv.py`` checks the values against scikit-image.

Copyright: the scikit-image team (BSD-3-Clause), from
``skimage/color/colorconv.py``.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

# sRGB (linear) <-> CIE XYZ, and the D65 white point for the 2° observer
XYZ_FROM_RGB = np.array(
    [
        [0.412453, 0.357580, 0.180423],
        [0.212671, 0.715160, 0.072169],
        [0.019334, 0.119193, 0.950227],
    ]
)
RGB_FROM_XYZ = np.linalg.inv(XYZ_FROM_RGB)
XYZ_REF_WHITE = np.array([0.95047, 1.0, 1.08883])


def _colors(arr: npt.ArrayLike) -> FloatArray:
    out = np.array(arr, dtype=np.float64)
    if out.ndim == 0 or out.shape[-1] != 3:
        raise ValueError('the last axis must hold the 3 color channels')
    return out


def xyz2rgb(xyz: npt.ArrayLike) -> FloatArray:
    """CIE XYZ to sRGB, companded and clipped to [0, 1]."""
    arr = _colors(xyz) @ RGB_FROM_XYZ.T
    mask = arr > 0.0031308
    arr[mask] = 1.055 * np.power(arr[mask], 1 / 2.4) - 0.055
    arr[~mask] *= 12.92
    np.clip(arr, 0, 1, out=arr)
    return arr


def luv2xyz(luv: npt.ArrayLike) -> FloatArray:
    """CIE-Luv to CIE XYZ (D65, 2° observer)."""
    arr = _colors(luv)
    L, u, v = arr[..., 0], arr[..., 1], arr[..., 2]
    eps = np.finfo(np.float64).eps
    y = L.copy()
    mask = y > 7.999625
    y[mask] = np.power((y[mask] + 16.0) / 116.0, 3.0)
    y[~mask] = y[~mask] / 903.3
    y *= XYZ_REF_WHITE[1]
    uv_weights = np.array([1, 15, 3], dtype=np.float64)
    u0 = 4 * XYZ_REF_WHITE[0] / (uv_weights @ XYZ_REF_WHITE)
    v0 = 9 * XYZ_REF_WHITE[1] / (uv_weights @ XYZ_REF_WHITE)
    a = u0 + u / (13.0 * L + eps)
    b = v0 + v / (13.0 * L + eps)
    c = 3 * y * (5 * b - 3)
    z = ((a - 4) * c - 15 * a * b * y) / (12 * b)
    x = -(c / b + 3.0 * z)
    return np.concatenate([q[..., np.newaxis] for q in (x, y, z)], axis=-1)


def lab2xyz(lab: npt.ArrayLike) -> FloatArray:
    """CIE-Lab to CIE XYZ (D65, 2° observer); a negative Z is clipped to 0."""
    arr = _colors(lab)
    L, a, b = arr[..., 0], arr[..., 1], arr[..., 2]
    y = (L + 16.0) / 116.0
    x = (a / 500.0) + y
    z = y - (b / 200.0)
    z[z < 0] = 0
    out = np.stack([x, y, z], axis=-1)
    mask = out > 0.2068966
    out[mask] = np.power(out[mask], 3.0)
    out[~mask] = (out[~mask] - 16.0 / 116.0) / 7.787
    out *= XYZ_REF_WHITE
    return out


def luv2rgb(luv: npt.ArrayLike) -> FloatArray:
    """CIE-Luv to sRGB in [0, 1], as ``skimage.color.luv2rgb``."""
    return xyz2rgb(luv2xyz(luv))


def lab2rgb(lab: npt.ArrayLike) -> FloatArray:
    """CIE-Lab to sRGB in [0, 1], as ``skimage.color.lab2rgb``."""
    return xyz2rgb(lab2xyz(lab))
