# napari-lite: own code
"""utils/_rotation.py returns what scipy's Rotation returns, for the
conversions napari makes: Euler angles to a matrix (both conventions),
a matrix back to Euler angles with scipy's gimbal-lock choice, and a
quaternion to a matrix and back."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from napari_lite.utils import _rotation

transform = pytest.importorskip('scipy.spatial.transform')
Rotation = transform.Rotation

RNG = np.random.default_rng(0)
RANDOM_ANGLES = [RNG.uniform(-180, 180, 3) for _ in range(60)]
# gimbal lock and other special orientations, including napari's defaults
SPECIAL_ANGLES = [
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 90.0),
    (90.0, 0.0, 0.0),
    (0.0, 90.0, 0.0),
    (0.0, -90.0, 0.0),
    (30.0, 90.0, 45.0),
    (30.0, -90.0, 45.0),
    (180.0, 0.0, 0.0),
    (0.0, 180.0, 0.0),
    (0.0, 0.0, 180.0),
    (45.0, 45.0, 45.0),
    (-120.0, 60.0, 170.0),
]
ANGLES = SPECIAL_ANGLES + RANDOM_ANGLES


@pytest.mark.parametrize('seq', ['xyz', 'XYZ', 'zyx', 'ZXY', 'xz', 'Y'])
@pytest.mark.parametrize('angles', ANGLES)
def test_matrix_from_euler(seq, angles) -> None:
    angles = np.asarray(angles)[: len(seq)]
    expected = Rotation.from_euler(seq, angles, degrees=True).as_matrix()
    np.testing.assert_allclose(
        _rotation.matrix_from_euler(seq, angles, degrees=True),
        expected,
        atol=1e-14,
    )
    # radians too, through the same path
    np.testing.assert_allclose(
        _rotation.matrix_from_euler(seq, np.radians(angles)),
        expected,
        atol=1e-14,
    )


@pytest.mark.parametrize('seq', ['XYZ', 'xyz', 'ZYX', 'zxz', 'XZX'])
@pytest.mark.parametrize('angles', ANGLES)
def test_euler_from_matrix(seq, angles) -> None:
    matrix = Rotation.from_euler('xyz', angles, degrees=True).as_matrix()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)  # scipy's gimbal lock
        expected = Rotation.from_matrix(matrix).as_euler(seq, degrees=True)
    result = _rotation.euler_from_matrix(seq, matrix, degrees=True)
    # angles may wrap around +-180 degrees: compare the rotations too
    np.testing.assert_allclose(
        np.mod(result - expected + 180, 360) - 180, 0, atol=1e-7
    )
    np.testing.assert_allclose(
        _rotation.matrix_from_euler(seq, result, degrees=True),
        matrix,
        atol=1e-12,
    )


def test_gimbal_lock_choice_is_scipys() -> None:
    """Second angle at +-90 degrees: third angle zero, first takes the rest."""
    for angles in [(30.0, 90.0, 45.0), (10.0, -90.0, 20.0)]:
        matrix = Rotation.from_euler('XYZ', angles, degrees=True).as_matrix()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            expected = Rotation.from_matrix(matrix).as_euler(
                'XYZ', degrees=True
            )
        result = _rotation.euler_from_matrix('XYZ', matrix, degrees=True)
        assert result[2] == 0.0
        np.testing.assert_allclose(result, expected, atol=1e-7)


@pytest.mark.parametrize('seed', range(40))
def test_quaternion_matrix_round_trip(seed) -> None:
    rng = np.random.default_rng(seed)
    quat = rng.normal(size=4) * rng.uniform(0.5, 3)  # not unit on purpose
    expected_matrix = Rotation.from_quat(quat).as_matrix()
    matrix = _rotation.matrix_from_quat(quat)
    np.testing.assert_allclose(matrix, expected_matrix, atol=1e-14)
    expected_quat = Rotation.from_matrix(expected_matrix).as_quat()
    np.testing.assert_allclose(
        _rotation.quat_from_matrix(matrix), expected_quat, atol=1e-14
    )


def test_quat_from_matrix_takes_every_branch() -> None:
    """The four cases of scipy's algorithm, chosen by the largest term."""
    for axis, angle in [('x', 170.0), ('y', 170.0), ('z', 170.0), ('x', 10.0)]:
        matrix = Rotation.from_euler(axis, angle, degrees=True).as_matrix()
        np.testing.assert_allclose(
            _rotation.quat_from_matrix(matrix),
            Rotation.from_matrix(matrix).as_quat(),
            atol=1e-14,
        )


def test_nearly_orthogonal_matrix_is_projected_like_scipy() -> None:
    matrix = Rotation.from_euler('xyz', [20, 30, 40], degrees=True).as_matrix()
    matrix = matrix + 1e-9 * np.random.default_rng(3).normal(size=(3, 3))
    np.testing.assert_allclose(
        _rotation.quat_from_matrix(matrix),
        Rotation.from_matrix(matrix).as_quat(),
        atol=1e-12,
    )


def test_bad_inputs() -> None:
    with pytest.raises(ValueError, match='determinant'):
        _rotation.quat_from_matrix(-np.eye(3))
    with pytest.raises(ValueError, match='consecutive'):
        _rotation.matrix_from_euler('xxy', [1, 2, 3])
    with pytest.raises(ValueError, match='mixed'):
        _rotation.matrix_from_euler('xYz', [1, 2, 3])
    with pytest.raises(ValueError, match='zero quaternion'):
        _rotation.matrix_from_quat([0, 0, 0, 0])


def test_napari_camera_conventions() -> None:
    """The exact calls napari makes, against scipy."""
    angles = np.array([15.0, -40.0, 75.0])
    np.testing.assert_allclose(
        _rotation.matrix_from_euler('XYZ', -angles, degrees=True),
        Rotation.from_euler('XYZ', -angles, degrees=True).as_matrix(),
        atol=1e-14,
    )
    quat = [
        0.1,
        0.7,
        -0.2,
        0.6,
    ]  # vispy's (x, z, y, w) order, as napari passes
    np.testing.assert_allclose(
        _rotation.matrix_from_quat(quat).T,
        Rotation.from_quat(quat).as_matrix().T,
        atol=1e-14,
    )
