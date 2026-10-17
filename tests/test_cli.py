# napari-lite: own code
"""The napari-lite command opens a viewer with the files given."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest


@pytest.fixture
def viewers():
    opened = []
    yield opened
    for viewer in opened:
        viewer.close()


def test_help() -> None:
    proc = subprocess.run(
        [sys.executable, '-m', 'napari_lite', '--help'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert 'napari-lite' in proc.stdout
    assert '--labels' in proc.stdout


def test_opens_files(qtbot, tmp_path, viewers) -> None:
    import imageio.v3 as iio

    from napari_lite.__main__ import main

    png = tmp_path / 'photo.png'
    # large enough for napari's RGB guess (sides of at least 30 pixels)
    iio.imwrite(png, np.zeros((48, 64, 3), dtype=np.uint8))
    npy = tmp_path / 'stack.npy'
    np.save(npy, np.zeros((3, 8, 8), dtype=np.uint16))

    viewer = main([str(png), str(npy)], run=False)
    viewers.append(viewer)
    assert [layer.name for layer in viewer.layers] == ['photo', 'stack']
    assert viewer.layers['photo'].rgb
    assert viewer.layers['stack'].data.shape == (3, 8, 8)
    assert viewer.window._qt_window.windowTitle() == 'napari-lite'


def test_labels_and_options(qtbot, tmp_path, viewers) -> None:
    from napari_lite.__main__ import main
    from napari_lite.layers import Labels

    npy = tmp_path / 'cells.npy'
    np.save(npy, np.zeros((8, 8), dtype=np.uint8))
    viewer = main(
        [str(npy), '--labels', '--ndisplay', '3', '--title', 'cells'],
        run=False,
    )
    viewers.append(viewer)
    assert isinstance(viewer.layers[0], Labels)
    assert viewer.dims.ndisplay == 3
    assert viewer.title == 'cells'


def test_missing_file(qtbot) -> None:
    from napari_lite.__main__ import main

    with pytest.raises(FileNotFoundError):
        main(['no-such-file.png'], run=False)
