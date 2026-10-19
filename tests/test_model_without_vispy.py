# napari-lite: own code
"""The model (viewer model, layers, dims, camera, events) works without
vispy and without Qt: issue 5, docs/backends.md.

Each check runs in a fresh interpreter with the libraries blocked at
import time, so a leak anywhere in the import chain fails here, with
vispy installed or not.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

BLOCKED = ['vispy', 'qtpy', 'PyQt6', 'PySide6', 'OpenGL']

SCRIPT = textwrap.dedent(
    """
    import importlib.abc
    import json
    import sys

    BLOCKED = set(json.loads(sys.argv[1]))

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split('.')[0] in BLOCKED:
                raise ImportError(f'{name} is blocked in this test')
            return None

    sys.meta_path.insert(0, Block())
    exec(sys.argv[2])
    loaded = sorted({m.split('.')[0] for m in sys.modules})
    print(json.dumps({'loaded': loaded, 'modules': len(sys.modules)}))
    """
)


def run_blocked(code: str, blocked: list[str] = BLOCKED) -> dict:
    proc = subprocess.run(
        [sys.executable, '-c', SCRIPT, json.dumps(blocked), code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


ALL_LAYERS = textwrap.dedent(
    """
    import numpy as np
    from napari_lite.components import ViewerModel
    from napari_lite.utils.colormaps import ensure_colormap
    from napari_lite.utils.key_bindings import KeymapHandler

    v = ViewerModel()
    image = v.add_image(np.zeros((4, 16, 16)), colormap='magma')
    image.colormap = 'green'
    image.contrast_limits = (0.2, 0.8)
    labels = v.add_labels(np.zeros((16, 16), dtype=np.uint8))
    labels.paint((4, 4), 2)
    points = v.add_points(
        np.array([[1.0, 2.0], [3.0, 4.0]]),
        face_color='cyan',
        border_color='#ff8800',
    )
    points.face_color = ['red', 'blue']
    v.add_shapes(
        [np.array([[1, 1], [1, 5], [5, 5], [5, 1]])],
        shape_type='polygon',
        edge_color='yellow',
        face_color='transparent',
    )
    v.add_surface(
        (
            np.array([[0, 0], [0, 10], [10, 0]], float),
            np.array([[0, 1, 2]]),
            np.array([0.0, 0.5, 1.0]),
        )
    )
    v.add_tracks(np.array([[0, 0, 1.0, 1.0], [0, 1, 2.0, 2.0], [1, 0, 3.0, 3.0]]))
    v.add_vectors(np.zeros((3, 2, 2)))
    v.dims.current_step = (2, 0, 0)
    v.dims.ndisplay = 3
    v.dims.ndisplay = 2
    ensure_colormap('gray')
    handler = KeymapHandler()
    handler.keymap_providers = [v]
    assert len(v.layers) == 7
    """
)


def test_model_with_every_layer_type_and_no_vispy_or_qt() -> None:
    info = run_blocked(ALL_LAYERS)
    assert 'vispy' not in info['loaded']
    assert not {'qtpy', 'PyQt6', 'PySide6', 'OpenGL'} & set(info['loaded'])


def test_importing_the_model_does_not_load_vispy_even_when_installed() -> None:
    """Nothing blocked: the model must still not pull vispy in."""
    info = run_blocked(
        'import napari_lite.components, napari_lite.layers', blocked=[]
    )
    assert 'vispy' not in info['loaded']
    assert 'qtpy' not in info['loaded']


def test_vispy_only_colormaps_need_vispy() -> None:
    """A colormap that only vispy has ('GrBu') is listed, resolves when
    vispy is there (importing it then), and says so when it is not."""
    pytest.importorskip('vispy')
    info = run_blocked(
        'from napari_lite.utils.colormaps import ensure_colormap\n'
        "ensure_colormap('GrBu')",
        blocked=[],
    )
    assert 'vispy' in info['loaded']  # imported for that name, then
    proc = subprocess.run(
        [
            sys.executable,
            '-c',
            SCRIPT,
            json.dumps(BLOCKED),
            'from napari_lite.utils.colormaps import ensure_colormap\n'
            "ensure_colormap('GrBu')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert 'vispy' in proc.stderr


def test_own_replacements_match_vispy() -> None:
    """The colour table, parsing, key names and rotation agree with
    vispy's, which they stand in for."""
    vispy_color = pytest.importorskip('vispy.color')
    import numpy as np
    from vispy.util import keys as vispy_keys
    from vispy.util.transforms import rotate as vispy_rotate

    from napari_lite.utils import _colors, _key_names, _vispy_optional

    assert _colors.get_color_names() == vispy_color.get_color_names()
    # same entries in the same order: napari names a colour by reversing
    # the table, and the order decides between 'k' and 'black'
    assert list(_colors.get_color_dict().items()) == list(
        vispy_color.get_color_dict().items()
    )
    for name in ('red', 'aliceblue', 'transparent', '#abc', '#aabbccdd'):
        assert np.allclose(
            _colors._string_to_rgb(name),
            vispy_color.color_array._string_to_rgb(name),
        )
    for spec in ('red', ['red', 'blue'], [[0.1, 0.2, 0.3], [0.5, 0.6, 0.7]]):
        assert np.allclose(
            _colors.ColorArray(spec).rgba, vispy_color.ColorArray(spec).rgba
        )
    for angle, axis in ((30, (0, 0, 1)), (-17.5, (1, 2, 3))):
        assert np.allclose(
            _vispy_optional.rotate(angle, axis), vispy_rotate(angle, axis)
        )
    # keys mix with vispy's in both directions, in dicts and sequences
    assert _key_names.SHIFT == vispy_keys.SHIFT
    assert vispy_keys.SHIFT == _key_names.SHIFT
    assert _key_names.SHIFT != vispy_keys.CONTROL
    assert {_key_names.CONTROL: 1}[vispy_keys.CONTROL] == 1
    assert vispy_keys.META in [_key_names.ALT, _key_names.META]
    assert _key_names.ENTER == '\n'
    assert isinstance(
        vispy_color.Colormap([[0, 0, 0, 1], [1, 1, 1, 1]]),
        _vispy_optional.Colormap,
    )
