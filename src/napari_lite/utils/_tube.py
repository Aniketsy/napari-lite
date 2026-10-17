# napari-lite: own code
"""Frenet frames along a path, for the 3D paths of the Shapes layer.

A copy of ``_frenet_frames`` from vispy's ``vispy/visuals/tube.py``.
napari imports it from there, and importing ``vispy.visuals.tube`` loads
every vispy visual and ``vispy.gloo`` with the layers, long before a
canvas exists.  Copying the function keeps ``napari_lite.layers`` free of
vispy's scene graph; ``vispy.util.transforms`` is already loaded by the
events package.

Copyright (c) 2013-2026, Vispy Development Team. All rights reserved.
Distributed under the (new) BSD License.  See vispy's LICENSE.txt for the
full terms.
"""

from __future__ import annotations

import numpy as np
from numpy.linalg import norm
from vispy.util.transforms import rotate


def _frenet_frames(
    points: np.ndarray, closed: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculates and returns the tangents, normals and binormals for
    the tube.
    """
    tangents = np.zeros((len(points), 3))
    normals = np.zeros((len(points), 3))

    epsilon = 0.0001

    # Compute tangent vectors for each segment
    tangents = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
    if not closed:
        tangents[0] = points[1] - points[0]
        tangents[-1] = points[-1] - points[-2]
    mags = np.sqrt(np.sum(tangents * tangents, axis=1))
    tangents /= mags[:, np.newaxis]

    # Get initial normal and binormal
    t = np.abs(tangents[0])

    smallest = np.argmin(t)
    normal = np.zeros(3)
    normal[smallest] = 1.0

    vec = np.cross(tangents[0], normal)

    normals[0] = np.cross(tangents[0], vec)

    # Compute normal and binormal vectors along the path
    for i in range(1, len(points)):
        normals[i] = normals[i - 1]

        vec = np.cross(tangents[i - 1], tangents[i])
        if norm(vec) > epsilon:
            vec /= norm(vec)
            theta = np.arccos(np.clip(tangents[i - 1].dot(tangents[i]), -1, 1))
            normals[i] = rotate(-np.degrees(theta), vec)[:3, :3].dot(
                normals[i]
            )

    if closed:
        theta = np.arccos(np.clip(normals[0].dot(normals[-1]), -1, 1))
        theta /= len(points) - 1

        if tangents[0].dot(np.cross(normals[0], normals[-1])) > 0:
            theta *= -1.0

        for i in range(1, len(points)):
            normals[i] = rotate(-np.degrees(theta * i), tangents[i])[
                :3, :3
            ].dot(normals[i])

    binormals = np.cross(tangents, normals)

    return tangents, normals, binormals
