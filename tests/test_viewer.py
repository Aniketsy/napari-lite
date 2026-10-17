# napari-lite: own code
"""Viewer: a window around a QtCanvas; imshow; current_viewer."""

from __future__ import annotations

import gc

import numpy as np
import pytest
from qtpy.QtWidgets import QLabel


@pytest.fixture
def make_viewer(qtbot):
    from napari_lite import Viewer

    viewers = []

    def _make(**kwargs):
        kwargs.setdefault('show', False)
        viewer = Viewer(**kwargs)
        viewers.append(viewer)
        return viewer

    yield _make
    for viewer in viewers:
        viewer.close()
    gc.collect()


def test_viewer_window_and_canvas(make_viewer) -> None:
    viewer = make_viewer(title='test viewer')
    assert viewer.title == 'test viewer'
    assert viewer.window._qt_window.windowTitle() == 'test viewer'
    layer = viewer.add_image(np.zeros((4, 8, 8)))
    assert layer in viewer.window.qt_viewer.layer_to_visual
    assert viewer.window.qt_viewer.dims.nsliders == 3
    viewer.title = 'renamed'
    assert viewer.window._qt_window.windowTitle() == 'renamed'


def test_status_bar(make_viewer) -> None:
    viewer = make_viewer()
    bar = viewer.window._status_bar
    assert viewer.window.qt_viewer.status is None  # the line is in the bar
    viewer.status = 'hello'
    assert bar._status.text() == 'hello'
    viewer.help = 'press h'
    assert bar._help.text() == 'press h'
    bar.setStatusText(layer_base='img', coordinates='[1 2]')
    assert bar._status.text() == 'img'
    assert bar._coordinates.text() == '[1 2]'


def test_viewer_arguments(make_viewer) -> None:
    viewer = make_viewer(
        ndisplay=3, axis_labels=('z', 'y', 'x'), show_welcome_screen=True
    )
    assert viewer.dims.ndisplay == 3
    assert viewer.dims.axis_labels == ('z', 'y', 'x')


def test_screenshot(make_viewer, qtbot) -> None:
    viewer = make_viewer()
    viewer.add_image(np.random.random((16, 16)))
    viewer.show()
    qtbot.waitExposed(viewer.window._qt_window)
    img = viewer.screenshot()
    assert img.shape[-1] == 4
    full = viewer.screenshot(canvas_only=False)
    assert full.shape[0] >= img.shape[0]
    with pytest.raises(ValueError, match='canvas_only'):
        viewer.screenshot(size=(10, 10), canvas_only=False)


def test_current_viewer_and_close(make_viewer) -> None:
    from napari_lite import current_viewer

    first = make_viewer()
    second = make_viewer()
    assert current_viewer() is second
    second.close()
    assert current_viewer() is first
    first.close()
    assert current_viewer() is None


def test_close_all(make_viewer) -> None:
    from napari_lite import Viewer

    make_viewer()
    make_viewer()
    assert Viewer.close_all() >= 2
    assert Viewer.close_all() == 0


def test_dock_widget(make_viewer) -> None:
    viewer = make_viewer()
    label = QLabel('hello')
    dock = viewer.window.add_dock_widget(label, name='greeting', area='left')
    assert dock.windowTitle() == 'greeting'
    assert viewer.window.dock_widgets['greeting'] is label
    viewer.window.remove_dock_widget(label)
    assert 'greeting' not in viewer.window.dock_widgets
    with pytest.raises(TypeError, match='QWidget'):
        viewer.window.add_dock_widget(object())


def test_theme_changes_stylesheet(make_viewer) -> None:
    viewer = make_viewer()
    viewer.theme = 'light'
    assert 'rgb(235, 231, 230)' in viewer.window._qt_window.styleSheet()
    viewer.theme = 'dark'
    assert 'rgb(35, 36, 43)' in viewer.window._qt_window.styleSheet()


def test_imshow(qtbot) -> None:
    from napari_lite import Viewer, imshow

    data = np.zeros((2, 8, 8))
    viewer, layer = imshow(data, name='img', colormap='magma', show=False)
    try:
        assert isinstance(viewer, Viewer)
        assert layer.name == 'img'
        assert layer.colormap.name == 'magma'
        viewer2, layers = imshow(
            data, channel_axis=0, viewer=viewer, show=False
        )
        assert viewer2 is viewer
        assert isinstance(layers, tuple)
        assert len(layers) == 2
        assert len(viewer.layers) == 3
    finally:
        viewer.close()


def test_closed_viewer_cannot_show(make_viewer) -> None:
    viewer = make_viewer()
    viewer.close()
    with pytest.raises(RuntimeError, match='already been closed'):
        viewer.show()
