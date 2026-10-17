# napari-lite: own code
"""QR and RQ decompositions and the geometric mean from numpy, where napari
calls scipy.

``decompose_linear_matrix`` (utils/transforms/transform_utils.py) splits an
affine's linear part into rotation, scale and shear with ``scipy.linalg.qr``
or ``scipy.linalg.rq``, then makes the diagonal positive itself, so any
QR or RQ with orthogonal ``Q`` gives the same answer.  numpy has QR; RQ
follows from it by reversing rows and columns.  ``Points.to_mask`` takes
the geometric mean of a scale with ``scipy.stats.gmean``.
``tests/test_linalg.py`` compares all three with scipy.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def qr(a: npt.ArrayLike) -> tuple[FloatArray, FloatArray]:
    """``a = q @ r`` with ``q`` square orthogonal and ``r`` upper
    triangular, like ``scipy.linalg.qr(a)`` in its default full mode."""
    q, r = np.linalg.qr(np.asarray(a, dtype=np.float64), mode='complete')
    return q, r


def rq(a: npt.ArrayLike) -> tuple[FloatArray, FloatArray]:
    """``a = r @ q`` with ``r`` upper triangular and ``q`` square
    orthogonal, like ``scipy.linalg.rq(a)``.

    From the QR decomposition of ``a`` reversed and transposed: if
    ``flipud(a).T = q0 @ r0`` then ``a = flipud(fliplr(r0.T)) @ flipud(q0.T)``,
    and reversing rows and columns of the lower triangular ``r0.T`` gives
    an upper triangular factor.
    """
    a = np.asarray(a, dtype=np.float64)
    q0, r0 = np.linalg.qr(np.flipud(a).T, mode='complete')
    return np.flipud(np.fliplr(r0.T)), np.flipud(q0.T)


def gmean(a: npt.ArrayLike, axis: int | None = 0) -> np.floating | FloatArray:
    """The geometric mean along ``axis``, as ``scipy.stats.gmean``: the
    exponential of the mean logarithm."""
    return np.exp(np.mean(np.log(np.asarray(a)), axis=axis))
