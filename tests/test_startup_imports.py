# napari-lite: own code
"""What the first image and the first paint must not import.

Three imports used to arrive uninvited with the first image (see
docs/benchmarks.md): xarray, and pandas with it, from the check for xarray
data that every layer runs, whenever xarray is installed; scipy.ndimage,
for the thumbnail; and scipy.spatial, from ``canvas_to_world``, which runs
on every draw, 2D included.  ``literal_rewrites`` in tools/vendor.toml
keep them out; these tests notice when a resync lets one back in.

Each case runs in a fresh interpreter and reports the loaded modules.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

REPORT = textwrap.dedent(
    """
    import json, sys
    # a None entry marks an import that failed, not a loaded module
    loaded = sorted(
        m for m, mod in sys.modules.items() if mod is not None and m.count('.') <= 1
    )
    print('MODULES ' + json.dumps(loaded))
    """
)

FIRST_IMAGE = textwrap.dedent(
    """
    import numpy as np
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    viewer.add_image(np.zeros((4, 64, 64), dtype=np.uint8))
    viewer.dims.set_current_step(0, 2)
    """
)

FIRST_LABELS = textwrap.dedent(
    """
    import numpy as np
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    viewer.add_image(np.zeros((4, 64, 64), dtype=np.uint8))
    labels = viewer.add_labels(np.zeros((4, 64, 64), dtype=np.int32))
    viewer.dims.set_current_step(0, 2)
    # the fill tool, the label colours and the shapes masks used
    # scikit-image; they are own code now
    labels.selected_label = 3
    labels.fill((2, 10, 10), 3)
    shapes = viewer.add_shapes(
        [np.array([[2, 5, 5], [2, 5, 40], [2, 40, 40]])],
        shape_type='polygon',
    )
    shapes.add_paths([np.array([[2, 1, 1], [2, 20, 30], [2, 50, 10]])])
    shapes.to_labels((4, 64, 64))
    shapes.to_masks((4, 64, 64))
    """
)

FIRST_PAINT = textwrap.dedent(
    """
    import numpy as np
    import napari_lite
    from qtpy.QtWidgets import QApplication

    viewer = napari_lite.Viewer(show=True)
    viewer.add_image(np.zeros((64, 64), dtype=np.uint8))
    app = QApplication.instance()
    for _ in range(20):
        app.processEvents()
    viewer.screenshot(canvas_only=True)
    viewer.close()
    """
)

# the 3D camera, a rotated layer and a tracks layer used scipy; own numpy
# code now (utils/_rotation.py, _linalg.py, _tracks_index.py)
THREE_D = textwrap.dedent(
    """
    import numpy as np
    import napari_lite
    from qtpy.QtWidgets import QApplication

    viewer = napari_lite.Viewer(show=True)
    layer = viewer.add_image(np.zeros((8, 32, 32), dtype=np.uint8))
    layer.affine = np.array(
        [[1, 0, 0, 0], [0, 0.8, -0.6, 1], [0, 0.6, 0.8, 0], [0, 0, 0, 1]]
    )
    layer.rotate  # reads the decomposition of the affine
    try:
        import pandas
    except ImportError:  # a plain install: Tracks needs the features extra
        pass
    else:
        viewer.add_tracks(np.array([[0, 0, 1.0, 2.0, 3.0], [0, 1, 1.5, 2.5, 3.5]]))
    viewer.dims.ndisplay = 3
    app = QApplication.instance()
    for _ in range(20):
        app.processEvents()
    viewer.scene.camera.angles = (10, 20, 30)
    viewer.scene.camera.set_view_direction((0, 0, 1))
    viewer.canvas_to_world((5, 5))
    for _ in range(20):
        app.processEvents()
    viewer.screenshot(canvas_only=True)
    viewer.close()
    """
)

SCIPY_MODULES = {
    'scipy.spatial',
    'scipy.linalg',
    'scipy.ndimage',
    'scipy.stats',
    'scipy.sparse',
    'scipy.interpolate',
    'scipy.special',
}


def loaded_modules(code: str) -> set[str]:
    env = dict(os.environ)
    # the Qt "offscreen" platform has no OpenGL on Windows and macOS
    if sys.platform.startswith('linux') and not env.get('DISPLAY'):
        env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    proc = subprocess.run(
        [sys.executable, '-c', code + REPORT],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    line = next(
        line
        for line in proc.stdout.splitlines()
        if line.startswith('MODULES ')
    )
    return set(json.loads(line[len('MODULES ') :]))


def test_first_image_imports_no_xarray_pandas_or_ndimage() -> None:
    pytest.importorskip('xarray')  # the check only bites when it is installed
    loaded = loaded_modules(FIRST_IMAGE)
    assert 'napari_lite.layers' in loaded
    uninvited = {
        'xarray',
        'pandas',
        'scipy.ndimage',
        'scipy.special',
        # vispy's scene graph belongs to the canvas, not to the layers
        'vispy.visuals',
        'vispy.scene',
        # progress bars, and tqdm with them, on first use
        'tqdm',
    } & loaded
    assert not uninvited, f'the first image imported {sorted(uninvited)}'


def test_labels_and_shapes_import_no_ndimage_or_scikit_image() -> None:
    loaded = loaded_modules(FIRST_LABELS)
    assert 'napari_lite.layers' in loaded
    uninvited = {
        'scipy.ndimage',
        'skimage',
        'networkx',
        'tifffile',
        # a layer without features needs no feature table in pandas
        'pandas',
    } & loaded
    assert not uninvited, f'labels and shapes imported {sorted(uninvited)}'


def test_first_paint_in_2d_imports_no_scipy_spatial() -> None:
    loaded = loaded_modules(FIRST_PAINT)
    assert 'napari_lite._vispy' in loaded
    uninvited = {'scipy.spatial', 'xarray', 'tqdm', 'wrapt', 'pandas'} & loaded
    assert not uninvited, f'the first 2D paint imported {sorted(uninvited)}'


def test_3d_view_rotated_layer_and_tracks_import_no_scipy() -> None:
    # pint imports the top-level scipy package when it is installed; the
    # submodules are what napari-lite used, and must not be needed
    loaded = loaded_modules(THREE_D)
    assert 'napari_lite._vispy' in loaded
    uninvited = SCIPY_MODULES & loaded
    assert not uninvited, f'the 3D view imported {sorted(uninvited)}'
