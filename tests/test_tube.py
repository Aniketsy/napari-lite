# napari-lite: own code
"""The copied ``_frenet_frames`` (utils/_tube.py) returns what vispy's
returns, so 3D paths of the Shapes layer are unchanged; and the layers do
not import vispy's scene graph any more."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils._tube import _frenet_frames


@pytest.mark.parametrize('closed', [False, True])
@pytest.mark.parametrize('n_points', [2, 3, 10, 50])
def test_matches_vispy(n_points, closed) -> None:
    if closed and n_points < 3:
        pytest.skip('a closed path needs at least three points')
    vispy_tube = pytest.importorskip('vispy.visuals.tube')
    rng = np.random.default_rng(n_points)
    points = np.cumsum(rng.normal(size=(n_points, 3)), axis=0)
    if closed:
        points = np.concatenate([points, [points[0]]], axis=0)
    expected = vispy_tube._frenet_frames(points.copy(), closed)
    result = _frenet_frames(points.copy(), closed)
    for ours, theirs in zip(result, expected, strict=True):
        np.testing.assert_allclose(ours, theirs, rtol=1e-12, atol=1e-12)


def test_straight_line_frames() -> None:
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    tangents, normals, binormals = _frenet_frames(points, closed=False)
    np.testing.assert_allclose(tangents, [[1, 0, 0]] * 3)
    # normals and binormals are unit vectors orthogonal to the tangent
    assert np.allclose(np.linalg.norm(normals, axis=1), 1)
    assert np.allclose(np.linalg.norm(binormals, axis=1), 1)
    assert np.allclose((tangents * normals).sum(axis=1), 0)
    assert np.allclose((tangents * binormals).sum(axis=1), 0)
