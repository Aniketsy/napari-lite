# napari-lite: own code
"""Viewer and layer key bindings fire through the action manager shim."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def viewer():
    from napari_lite.components import ViewerModel
    from napari_lite.utils.action_manager import bind_shortcuts_from_settings

    bind_shortcuts_from_settings()
    return ViewerModel()


def _handler(*providers):
    from napari_lite.utils.key_bindings import KeymapHandler

    handler = KeymapHandler()
    handler.keymap_providers = list(providers)
    return handler


def test_viewer_shortcut_toggles_ndisplay(viewer) -> None:
    viewer.add_image(np.zeros((4, 8, 8)))
    assert viewer.dims.ndisplay == 2
    assert _handler(viewer).press_key('Control-Y')
    assert viewer.dims.ndisplay == 3


def test_layer_shortcut_labels_brush(viewer) -> None:
    labels = viewer.add_labels(np.zeros((8, 8), dtype=np.uint8))
    handler = _handler(labels, viewer)
    assert handler.press_key('P')  # activate_labels_paint_mode
    assert labels.mode == 'paint'
    assert handler.press_key('E')  # activate_labels_erase_mode
    assert labels.mode == 'erase'


def test_registered_action_names() -> None:
    from napari_lite.utils.action_manager import action_manager

    names = set(action_manager._actions)
    assert 'napari:toggle_ndisplay' in names
    assert 'napari:activate_labels_paint_mode' in names
    assert action_manager._actions['napari:toggle_ndisplay'].description


def test_trigger_without_viewer_is_explicit() -> None:
    from napari_lite.utils.action_manager import action_manager

    with pytest.raises(RuntimeError, match='no viewer is open'):
        action_manager.trigger('napari:toggle_ndisplay')


def test_bind_and_unbind_shortcut() -> None:
    from napari_lite.components import ViewerModel
    from napari_lite.utils.action_manager import action_manager

    calls = []
    action_manager.register_action(
        'test:ping', lambda v: calls.append(v), 'ping', ViewerModel
    )
    action_manager.bind_shortcut('test:ping', 'Control-Alt-Shift-P')
    viewer = ViewerModel()
    assert _handler(viewer).press_key('Control-Alt-Shift-P')
    assert calls == [viewer]
    action_manager.unbind_shortcut('test:ping')
    assert not _handler(viewer).press_key('Control-Alt-Shift-P')
