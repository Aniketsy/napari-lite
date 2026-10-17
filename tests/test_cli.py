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


def test_missing_file(capsys) -> None:
    from napari_lite.__main__ import main

    with pytest.raises(SystemExit) as info:
        main(['no-such-file.png'], run=False)
    assert info.value.code == 2
    assert 'no such file: no-such-file.png' in capsys.readouterr().err


def test_unreadable_file(tmp_path, capsys) -> None:
    from napari_lite.__main__ import main

    notes = tmp_path / 'notes.txt'
    notes.write_text('not an image', encoding='utf-8')
    with pytest.raises(SystemExit) as info:
        main([str(notes)], run=False)
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f'cannot read {notes}' in err
    assert 'Traceback' not in err


def test_missing_file_from_the_command_line() -> None:
    proc = subprocess.run(
        [sys.executable, '-m', 'napari_lite', 'no-such-file.png'],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert 'no such file: no-such-file.png' in proc.stderr
    assert 'Traceback' not in proc.stderr


def test_cli_returns_none_so_the_command_exits_with_status_0(
    qtbot, tmp_path, monkeypatch
) -> None:
    import napari_lite
    from napari_lite.__main__ import cli

    ran = []
    monkeypatch.setattr(napari_lite, 'run', lambda: ran.append(True))
    npy = tmp_path / 'cells.npy'
    np.save(npy, np.zeros((8, 8), dtype=np.uint8))
    try:
        assert cli([str(npy)]) is None
    finally:
        napari_lite.Viewer.close_all()
    assert ran == [True]
