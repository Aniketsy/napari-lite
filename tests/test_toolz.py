# napari-lite: own code
"""utils/_toolz.py behaves as toolz's ``identity`` and ``pipe``, which the
transforms use."""

from __future__ import annotations

import numpy as np
import pytest

from napari_lite.utils import _toolz


def test_identity_and_pipe() -> None:
    assert _toolz.identity(5) == 5
    sentinel = object()
    assert _toolz.identity(sentinel) is sentinel
    assert _toolz.pipe(3) == 3
    assert _toolz.pipe(3, lambda x: x + 1, lambda x: x * 10) == 40
    assert _toolz.pipe('a', str.upper, lambda s: s + '!') == 'A!'


def test_matches_toolz() -> None:
    toolz = pytest.importorskip('toolz')
    funcs = [np.sqrt, lambda x: x + 1, np.square]
    data = np.arange(5.0)
    np.testing.assert_array_equal(
        _toolz.pipe(data, *funcs), toolz.pipe(data, *funcs)
    )
    assert _toolz.identity(data) is toolz.identity(data)


def test_transform_chains_still_compose() -> None:
    """The transforms module builds chains with pipe and uses identity as
    the default; a chain of affines must apply in order."""
    from napari_lite.utils.transforms import Affine, Transform, TransformChain

    default = Transform()
    np.testing.assert_array_equal(default([[1.0, 2.0]]), [[1.0, 2.0]])
    chain = TransformChain(
        [
            Affine(scale=[2, 2], name='scale'),
            Affine(translate=[1, -1], name='shift'),
        ]
    )
    np.testing.assert_array_equal(chain([[1.0, 2.0]]), [[3.0, 3.0]])
    np.testing.assert_array_equal(
        chain.simplified([[1.0, 2.0]]), chain([[1.0, 2.0]])
    )
