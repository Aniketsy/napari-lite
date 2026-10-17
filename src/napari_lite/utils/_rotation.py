# napari-lite: own code
"""3D rotations in numpy, with scipy's conventions and arithmetic.

napari uses ``scipy.spatial.transform.Rotation`` in four places: the 3D
branch of ``canvas_to_world`` (Euler angles to a matrix), the camera's view
and up directions (Euler angles to a matrix and back) and the vispy camera
(quaternion to matrix and back).  ``scipy.spatial`` is about 100 modules
and, on a slow machine, close to a second the first time; scipy itself is
134 MB of the install.  The functions here follow scipy's own
implementation (``scipy/spatial/transform/_rotation_xp.py``, BSD-3): the
same quaternion composition for Euler angles, the same choice of the
largest term when reading a quaternion off a matrix, the same treatment of
gimbal lock (second angle within 1e-7 of 0 or pi: the third angle is set
to zero).  ``tests/test_rotation.py`` compares them with scipy.

Quaternions are ``(x, y, z, w)`` as in scipy.  A lower-case sequence such
as ``'xyz'`` means extrinsic rotations, an upper-case one such as ``'XYZ'``
intrinsic rotations, again as in scipy.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

_AXES = {'x': 0, 'y': 1, 'z': 2}
_GIMBAL_EPS = 1e-7


def _sequence(seq: str, length: int | None = None) -> tuple[list[int], bool]:
    """Axis indices of ``seq`` and whether the sequence is intrinsic."""
    if not 1 <= len(seq) <= 3 or (length is not None and len(seq) != length):
        raise ValueError(f'expected a sequence of 1 to 3 axes, got {seq!r}')
    if seq.isupper():
        intrinsic = True
    elif seq.islower():
        intrinsic = False
    else:
        raise ValueError(f'mixed intrinsic and extrinsic axes in {seq!r}')
    if any(a not in _AXES for a in seq.lower()):
        raise ValueError(f'axes must be x, y or z, got {seq!r}')
    if any(seq[i] == seq[i + 1] for i in range(len(seq) - 1)):
        raise ValueError(f'consecutive axes must differ, got {seq!r}')
    return [_AXES[a] for a in seq.lower()], intrinsic


def _compose(p: FloatArray, q: FloatArray) -> FloatArray:
    """Quaternion product p * q, as scipy's ``compose_quat``."""
    cross = np.cross(p[:3], q[:3])
    return np.array(
        [
            p[3] * q[0] + q[3] * p[0] + cross[0],
            p[3] * q[1] + q[3] * p[1] + cross[1],
            p[3] * q[2] + q[3] * p[2] + cross[2],
            p[3] * q[3] - p[0] * q[0] - p[1] * q[1] - p[2] * q[2],
        ]
    )


def _elementary(axis: int, angle: float) -> FloatArray:
    quat = np.zeros(4)
    quat[3] = np.cos(angle / 2.0)
    quat[axis] = np.sin(angle / 2.0)
    return quat


def quat_from_euler(
    seq: str, angles: npt.ArrayLike, degrees: bool = False
) -> FloatArray:
    """The quaternion of the Euler angles ``angles`` about ``seq``."""
    axes, intrinsic = _sequence(seq)
    values = np.atleast_1d(np.asarray(angles, dtype=np.float64))
    if values.shape != (len(axes),):
        raise ValueError(f'expected {len(axes)} angles, got {values.shape}')
    if degrees:
        values = values * (np.pi / 180.0)
    quat = _elementary(axes[0], values[0])
    for axis, angle in zip(axes[1:], values[1:], strict=True):
        step = _elementary(axis, angle)
        quat = _compose(quat, step) if intrinsic else _compose(step, quat)
    return quat


def _matrix(quat: FloatArray) -> FloatArray:
    x, y, z, w = quat
    x2, y2, z2, w2 = x * x, y * y, z * z, w * w
    xy, zw, xz, yw, yz, xw = x * y, z * w, x * z, y * w, y * z, x * w
    return np.array(
        [
            [x2 - y2 - z2 + w2, 2 * (xy - zw), 2 * (xz + yw)],
            [2 * (xy + zw), -x2 + y2 - z2 + w2, 2 * (yz - xw)],
            [2 * (xz - yw), 2 * (yz + xw), -x2 - y2 + z2 + w2],
        ]
    )


def matrix_from_quat(quat: npt.ArrayLike) -> FloatArray:
    """The (3, 3) rotation matrix of a quaternion ``(x, y, z, w)``, which
    is normalized first, as ``Rotation.from_quat(q).as_matrix()``."""
    values = np.asarray(quat, dtype=np.float64)
    norm = np.linalg.norm(values)
    if norm == 0:
        raise ValueError('a zero quaternion has no rotation')
    return _matrix(values / norm)


def matrix_from_euler(
    seq: str, angles: npt.ArrayLike, degrees: bool = False
) -> FloatArray:
    """The (3, 3) rotation matrix of Euler angles about ``seq``, as
    ``Rotation.from_euler(seq, angles, degrees).as_matrix()``."""
    return _matrix(quat_from_euler(seq, angles, degrees))


def quat_from_matrix(matrix: npt.ArrayLike) -> FloatArray:
    """The quaternion ``(x, y, z, w)`` of a (3, 3) rotation matrix, as
    ``Rotation.from_matrix(m).as_quat()``.

    A matrix that is not orthogonal within 1e-12 is replaced by the nearest
    rotation first (through its singular value decomposition), as scipy
    does; a left-handed or singular matrix is an error.
    """
    m = np.array(matrix, dtype=np.float64)
    if m.shape != (3, 3):
        raise ValueError(f'expected a (3, 3) matrix, got {m.shape}')
    if np.linalg.det(m) <= 0:
        raise ValueError(
            'Non-positive determinant (left-handed or null coordinate '
            f'frame) in rotation matrix: {m}.'
        )
    if not np.all(np.isclose(m @ m.T, np.eye(3), rtol=1e-5, atol=1e-12)):
        u, _, vt = np.linalg.svd(m)
        m = u @ vt
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    choice = int(np.argmax([m[0, 0], m[1, 1], m[2, 2], trace]))
    if choice == 0:
        quat = [
            1 - trace + 2 * m[0, 0],
            m[1, 0] + m[0, 1],
            m[2, 0] + m[0, 2],
            m[2, 1] - m[1, 2],
        ]
    elif choice == 1:
        quat = [
            m[1, 0] + m[0, 1],
            1 - trace + 2 * m[1, 1],
            m[2, 1] + m[1, 2],
            m[0, 2] - m[2, 0],
        ]
    elif choice == 2:
        quat = [
            m[2, 0] + m[0, 2],
            m[2, 1] + m[1, 2],
            1 - trace + 2 * m[2, 2],
            m[1, 0] - m[0, 1],
        ]
    else:
        quat = [
            m[2, 1] - m[1, 2],
            m[0, 2] - m[2, 0],
            m[1, 0] - m[0, 1],
            1 + trace,
        ]
    values = np.array(quat)
    return values / np.linalg.norm(values)


def euler_from_quat(
    seq: str, quat: npt.ArrayLike, degrees: bool = False
) -> FloatArray:
    """The Euler angles about ``seq`` of a quaternion ``(x, y, z, w)``, as
    ``Rotation.from_quat(q).as_euler(seq, degrees)``.

    scipy's algorithm (Bernardes and Viollet, 2022).  In gimbal lock, when
    the second angle is within 1e-7 of 0 or pi, the third angle is zero and
    the first carries the whole remaining rotation; scipy warns there, this
    function does not.
    """
    axes, intrinsic = _sequence(seq, length=3)
    q = np.asarray(quat, dtype=np.float64)
    q = q / np.linalg.norm(q)
    if intrinsic:
        axes = axes[::-1]
    i, j, k = axes
    symmetric = i == k
    if symmetric:
        k = 3 - i - j
    sign = (i - j) * (j - k) * (k - i) // 2
    if symmetric:
        a, b, c, d = q[3], q[i], q[j], q[k] * sign
    else:
        a = q[3] - q[j]
        b = q[i] + q[k] * sign
        c = q[j] + q[3]
        d = q[k] * sign - q[i]

    half_sum = np.arctan2(b, a)
    half_diff = np.arctan2(d, c)
    angles = np.zeros(3)
    angles[1] = 2 * np.arctan2(np.hypot(c, d), np.hypot(a, b))
    first, third = (2, 0) if intrinsic else (0, 2)
    near_zero = abs(angles[1]) <= _GIMBAL_EPS
    near_pi = abs(angles[1] - np.pi) <= _GIMBAL_EPS
    if near_zero or near_pi:
        angles[0] = (
            2 * half_sum
            if near_zero
            else 2 * half_diff * (1 if intrinsic else -1)
        )
    else:
        angles[first] = half_sum - half_diff
        angles[third] = half_sum + half_diff
    if not symmetric:
        angles[third] *= sign
        angles[1] -= np.pi / 2
    angles = (angles + np.pi) % (2 * np.pi) - np.pi
    return angles * (180.0 / np.pi) if degrees else angles


def euler_from_matrix(
    seq: str, matrix: npt.ArrayLike, degrees: bool = False
) -> FloatArray:
    """The Euler angles about ``seq`` of a (3, 3) rotation matrix, as
    ``Rotation.from_matrix(m).as_euler(seq, degrees)``."""
    return euler_from_quat(seq, quat_from_matrix(matrix), degrees)
