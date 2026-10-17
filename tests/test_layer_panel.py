# napari-lite: own code
"""The layer panel: napari's layer list, layer controls and button rows in
the viewer window, built by ``QtCanvas`` on first access."""

from __future__ import annotations

import gc
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
from qtpy.QtCore import QDir, Qt


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


def test_window_shows_the_panel(make_viewer) -> None:
    viewer = make_viewer()
    window = viewer.window._qt_window
    qv = viewer.window._qt_viewer
    left = Qt.DockWidgetArea.LeftDockWidgetArea
    assert window.dockWidgetArea(qv.dockLayerControls) == left
    assert window.dockWidgetArea(qv.dockLayerList) == left
    assert qv.dockLayerControls.isAncestorOf(qv.controls)
    assert qv.dockLayerList.isAncestorOf(qv.layers)
    assert qv.dockLayerList.isAncestorOf(qv.layerButtons)
    assert qv.dockLayerList.isAncestorOf(qv.viewerButtons)
    # napari's console button is there but hidden: no console
    assert qv.viewerButtons.consoleButton.isHidden()
    # napari's stylesheet, with the theme's icons written and registered
    assert 'theme_dark:/' in window.styleSheet()
    icons = Path(QDir.searchPaths('theme_dark')[0])
    assert (icons / 'visibility.svg').exists()
    assert (icons / 'napari-lite.txt').exists()


def test_layer_list_and_controls_follow_the_layers(make_viewer) -> None:
    from napari_lite._qt.layer_controls.qt_image_controls import (
        QtImageControls,
    )
    from napari_lite._qt.layer_controls.qt_labels_controls import (
        QtLabelsControls,
    )

    viewer = make_viewer()
    qv = viewer.window._qt_viewer
    assert qv.layers.model().rowCount() == 0
    image = viewer.add_image(np.zeros((8, 8)))
    labels = viewer.add_labels(np.zeros((8, 8), dtype=np.uint8))
    assert qv.layers.model().rowCount() == 2
    assert isinstance(qv.controls.currentWidget(), QtLabelsControls)
    viewer.layers.selection.active = image
    assert isinstance(qv.controls.currentWidget(), QtImageControls)
    viewer.layers.remove(labels)
    assert qv.layers.model().rowCount() == 1


def test_buttons(make_viewer) -> None:
    viewer = make_viewer()
    qv = viewer.window._qt_viewer
    qv.layerButtons.newLabelsButton.click()
    qv.layerButtons.newPointsButton.click()
    qv.layerButtons.newShapesButton.click()
    assert [type(x).__name__ for x in viewer.layers] == [
        'Labels',
        'Points',
        'Shapes',
    ]
    qv.layerButtons.deleteButton.click()  # the selected (last added) layer
    assert [type(x).__name__ for x in viewer.layers] == ['Labels', 'Points']
    qv.viewerButtons.ndisplayButton.click()
    assert viewer.dims.ndisplay == 3
    qv.viewerButtons.ndisplayButton.click()
    assert viewer.dims.ndisplay == 2
    qv.viewerButtons.gridViewButton.click()
    assert viewer.canvas.grid.enabled
    qv.viewerButtons.gridViewButton.click()
    assert not viewer.canvas.grid.enabled


def _enabled(menu) -> dict[str, bool]:
    return {a.text(): a.isEnabled() for a in menu.actions() if a.text()}


def test_context_menu_follows_the_selection(make_viewer) -> None:
    from napari_lite._qt._qapp_model import build_qmodel_menu

    viewer = make_viewer()
    qv = viewer.window._qt_viewer
    image = viewer.add_image(np.zeros((4, 8, 8)))
    viewer.add_labels(np.zeros((8, 8), dtype=np.uint8))
    menu = build_qmodel_menu('napari/layers/context', parent=qv.layers)

    menu.update_from_context(None)  # the labels layer is active
    state = _enabled(menu)
    assert state['Convert to Image']
    assert not state['Convert to Labels']
    assert not state['Projections']
    assert state['Convert data type']

    viewer.layers.selection.active = image
    menu.update_from_context(None)
    state = _enabled(menu)
    assert state['Convert to Labels']
    assert state['Split Stack']
    assert state['Projections']
    assert not state['Convert to Image']
    assert not state['Split RGB']

    # the entries run napari's layer operations
    duplicate = next(
        a for a in menu.actions() if a.text() == 'Duplicate Layer'
    )
    duplicate.trigger()
    assert len(viewer.layers) == 3

    with pytest.raises(ValueError, match='no menu'):
        build_qmodel_menu('napari/other')


def test_copy_and_paste_scale(make_viewer) -> None:
    from napari_lite._qt._qapp_model.qactions._layerlist_context import (
        copy_to_clipboard,
        is_valid_spatial_in_clipboard,
        paste_from_clipboard,
    )

    viewer = make_viewer()
    source = viewer.add_image(np.zeros((8, 8)), scale=(2, 3), translate=(1, 1))
    target = viewer.add_image(np.zeros((8, 8)))
    viewer.layers.selection.active = source
    copy_to_clipboard(viewer.layers, keys=('scale', 'translate'))
    assert is_valid_spatial_in_clipboard()
    viewer.layers.selection.active = target
    paste_from_clipboard(viewer.layers)
    assert tuple(target.scale) == (2, 3)
    assert tuple(target.translate) == (1, 1)


def test_panel_modules_load_on_demand() -> None:
    """The package, the model and QtCanvas leave the panel modules unloaded."""
    code = textwrap.dedent(
        """
        import json, sys
        import napari_lite
        import napari_lite.components
        from napari_lite.qt import QtCanvas
        prefixes = (
            'napari_lite._qt.containers',
            'napari_lite._qt.layer_controls',
            'napari_lite._qt.widgets.qt_viewer_buttons',
        )
        print(json.dumps([m for m in sys.modules if m.startswith(prefixes)]))
        """
    )
    proc = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


def test_labels_painting_and_undo(make_viewer, qtbot) -> None:
    """The mode buttons of the controls set the mode; Ctrl+Z undoes."""
    viewer = make_viewer()
    qv = viewer.window._qt_viewer
    labels = viewer.add_labels(np.zeros((8, 8), dtype=np.uint8))
    controls = qv.controls.currentWidget()
    controls.paint_button.click()
    assert labels.mode == 'paint'
    labels.paint((2, 2), 5)
    assert labels.data.max() == 5
    qtbot.keyClick(
        qv.canvas.native, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
    )
    assert labels.data.max() == 0
    controls.erase_button.click()
    assert labels.mode == 'erase'


def test_context_menu_respects_locks(make_viewer) -> None:
    from napari_lite._qt._qapp_model import build_qmodel_menu

    viewer = make_viewer()
    image = viewer.add_image(np.zeros((4, 8, 8)))
    menu = build_qmodel_menu(
        'napari/layers/context', parent=viewer.window._qt_viewer.layers
    )
    menu.update_from_context(None)
    assert _enabled(menu)['Split Stack']
    assert _enabled(menu)['Convert to Labels']
    image.locked = True  # deletion locked: nothing that removes the layer
    menu.update_from_context(None)
    assert not _enabled(menu)['Split Stack']
    assert not _enabled(menu)['Convert to Labels']
    assert _enabled(menu)['Duplicate Layer']
