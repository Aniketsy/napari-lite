# napari-lite: own code
"""QtCanvas: layers become visuals, sliders follow dims, keys and status work."""

from __future__ import annotations

import numpy as np
import pytest
from qtpy.QtCore import Qt


@pytest.fixture
def canvas(qtbot):
    from napari_lite.components import ViewerModel
    from napari_lite.qt import QtCanvas

    widget = QtCanvas(ViewerModel())
    qtbot.addWidget(widget)
    return widget


def test_layers_get_visuals_and_sliders(canvas) -> None:
    viewer = canvas.viewer
    layer = viewer.add_image(np.zeros((4, 8, 8)))
    assert layer in canvas.layer_to_visual
    assert canvas.dims.nsliders == 3
    points = viewer.add_points(np.zeros((2, 3)))
    assert set(canvas.layer_to_visual) == {layer, points}
    viewer.layers.remove(layer)
    assert layer not in canvas.layer_to_visual
    assert points in canvas.layer_to_visual


def test_existing_layers_are_shown(qtbot) -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.qt import QtCanvas

    viewer = ViewerModel()
    layer = viewer.add_image(np.zeros((8, 8)))
    widget = QtCanvas(viewer)
    qtbot.addWidget(widget)
    assert layer in widget.layer_to_visual


def test_status_line_follows_viewer(canvas) -> None:
    canvas.viewer.status = 'hello'
    assert canvas.status._status.text() == 'hello'
    canvas.viewer.help = 'press h'
    assert canvas.status._help.text() == 'press h'
    canvas.viewer.status = {
        'layer_base': 'noise',
        'source_type': '',
        'plugin': '',
        'coordinates': '[1 2]: 0.5',
    }
    assert canvas.status._status.text() == 'noise'
    assert canvas.status._coordinates.text() == '[1 2]: 0.5'


def test_no_status_line(qtbot) -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.qt import QtCanvas

    widget = QtCanvas(ViewerModel(), show_status=False)
    qtbot.addWidget(widget)
    assert widget.status is None


def test_hint_until_a_layer_is_added(qtbot) -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.qt import QtCanvas

    viewer = ViewerModel()
    widget = QtCanvas(viewer, hint='add a layer')
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.hint == 'add a layer'
    assert widget._hint.isVisible()
    # it lies over the canvas and leaves the mouse to it
    assert widget._hint.geometry() == widget.canvas.native.geometry()
    assert widget._hint.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )
    layer = viewer.add_image(np.zeros((8, 8)))
    assert not widget._hint.isVisible()
    viewer.layers.remove(layer)
    assert widget._hint.isVisible()
    widget.hint = ''
    assert not widget._hint.isVisible()


def test_no_hint_by_default(canvas) -> None:
    assert canvas.hint == ''
    assert canvas._hint.isHidden()
    canvas.viewer.add_image(np.zeros((8, 8)))
    canvas.viewer.layers.clear()
    assert canvas._hint.isHidden()


def test_keys_reach_viewer_and_layer(canvas, qtbot) -> None:
    viewer = canvas.viewer
    labels = viewer.add_labels(np.zeros((4, 8, 8), dtype=np.uint8))
    canvas.show()
    qtbot.waitExposed(canvas)
    native = canvas.canvas.native
    assert viewer.dims.ndisplay == 2
    qtbot.keyClick(native, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert viewer.dims.ndisplay == 3
    qtbot.keyClick(native, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert viewer.dims.ndisplay == 2
    # the active layer's keys come first: P is the Labels paint mode
    qtbot.keyClick(native, Qt.Key.Key_P)
    assert labels.mode == 'paint'
    # arrow keys step through the first non-displayed dimension
    step = viewer.dims.current_step[0]
    qtbot.keyClick(native, Qt.Key.Key_Right)
    assert viewer.dims.current_step[0] == step + 1


def test_actions_without_app_parts(canvas, qtbot) -> None:
    """The console toggle and the shortcuts list have napari-lite versions."""
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog
    from napari_lite.utils.action_manager import action_manager

    viewer = canvas.viewer
    action_manager.trigger('napari:toggle_console_visibility', viewer)
    assert 'no console' in viewer.status
    dialog = action_manager.trigger('napari:show_shortcuts', viewer)
    assert isinstance(dialog, QtShortcutsDialog)
    text = dialog.browser.toPlainText()
    assert 'Toggle 2D/3D view' in text
    # rendered as the platform shows it (Ctrl+Y here, ⌘Y on macOS)
    from napari_lite.utils._keys import KeyCode, KeyMod
    from napari_lite.utils.interactions import Shortcut

    assert str(Shortcut(KeyMod.CtrlCmd | KeyCode.KeyY)) in text
    # not qtbot.addWidget: the dialog is deleted on close (WA_DeleteOnClose)
    # and qtbot would close it a second time at teardown
    dialog.close()


def test_mouse_enter_sets_status(canvas) -> None:
    canvas._enter_canvas()
    assert canvas.viewer.mouse_over_canvas
    assert canvas.viewer.status == 'Ready'
    canvas._leave_canvas()
    assert not canvas.viewer.mouse_over_canvas


def test_screenshot(canvas, qtbot) -> None:
    canvas.viewer.add_image(np.random.random((16, 16)))
    canvas.show()
    qtbot.waitExposed(canvas)
    img = canvas.screenshot()
    assert img.ndim == 3
    assert img.shape[-1] == 4
    assert img.shape[0] > 0
    sized = canvas.screenshot(size=(40, 60))
    assert sized.shape[:2] == (40, 60)
