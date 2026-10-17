# napari-lite: own code
"""utils/_linalg.py against scipy: QR, RQ and the geometric mean, and the
affine decomposition that uses them."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils import _linalg

scipy_linalg = pytest.importorskip('scipy.linalg')
scipy_stats = pytest.importorskip('scipy.stats')


@pytest.mark.parametrize('n', [2, 3, 4])
@pytest.mark.parametrize('seed', range(10))
def test_qr(n, seed) -> None:
    a = np.random.default_rng(seed).normal(size=(n, n))
    q, r = _linalg.qr(a)
    np.testing.assert_allclose(q @ r, a, atol=1e-12)
    np.testing.assert_allclose(q @ q.T, np.eye(n), atol=1e-12)
    np.testing.assert_allclose(np.tril(r, -1), 0, atol=1e-15)
    # the same factors as scipy, up to the sign convention of each column
    q_s, r_s = scipy_linalg.qr(a)
    signs = np.sign(np.diag(r_s)) * np.sign(np.diag(r))
    np.testing.assert_allclose(q * signs, q_s, atol=1e-12)


@pytest.mark.parametrize('n', [2, 3, 4])
@pytest.mark.parametrize('seed', range(10))
def test_rq(n, seed) -> None:
    a = np.random.default_rng(seed + 100).normal(size=(n, n))
    r, q = _linalg.rq(a)
    np.testing.assert_allclose(r @ q, a, atol=1e-12)
    np.testing.assert_allclose(q @ q.T, np.eye(n), atol=1e-12)
    np.testing.assert_allclose(np.tril(r, -1), 0, atol=1e-15)
    r_s, q_s = scipy_linalg.rq(a)
    signs = np.sign(np.diag(r_s)) * np.sign(np.diag(r))
    np.testing.assert_allclose(q * signs[:, None], q_s, atol=1e-12)


def test_rq_rectangular() -> None:
    a = np.random.default_rng(7).normal(size=(3, 5))
    r, q = _linalg.rq(a)
    assert r.shape == (3, 5) and q.shape == (5, 5)
    np.testing.assert_allclose(r @ q, a, atol=1e-12)


@pytest.mark.parametrize('upper_triangular', [True, False])
@pytest.mark.parametrize('seed', range(8))
def test_decompose_linear_matrix_is_unchanged(upper_triangular, seed) -> None:
    """napari's decomposition normalizes the signs afterwards, so it must
    give the same rotate, scale and shear as with scipy's factors."""
    from napari_lite.utils.transforms.transform_utils import (
        decompose_linear_matrix,
    )

    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(3, 3)) + 3 * np.eye(3)
    rotate, scale, shear = decompose_linear_matrix(matrix, upper_triangular)
    assert np.all(scale > 0)
    np.testing.assert_allclose(rotate @ rotate.T, np.eye(3), atol=1e-12)
    # rebuilt from the parts
    if upper_triangular:
        tri = np.eye(3)
        tri[np.triu_indices(3, 1)] = shear
        rebuilt = rotate @ (tri * scale)  # scale multiplies columns
    else:
        rebuilt = rotate @ (shear * scale)
    np.testing.assert_allclose(rebuilt, matrix, atol=1e-10)


def test_gmean() -> None:
    values = np.array([1.5, 2.0, 7.25, 0.4])
    np.testing.assert_allclose(
        _linalg.gmean(values), scipy_stats.gmean(values)
    )
    table = np.abs(np.random.default_rng(1).normal(size=(4, 3))) + 0.1
    np.testing.assert_allclose(
        _linalg.gmean(table, axis=0), scipy_stats.gmean(table, axis=0)
    )
    np.testing.assert_allclose(
        _linalg.gmean(table, axis=None), scipy_stats.gmean(table, axis=None)
    )
