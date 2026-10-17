# napari-lite: own code
"""The key bindings window (Ctrl+Alt+/) must outlive the key press: the
binding drops the dialog returned by the action, and a parentless Qt
window is deleted with its last Python reference."""

from __future__ import annotations

import gc


def _open_windows():
    from qtpy.QtWidgets import QApplication

    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

    return [
        w
        for w in QApplication.topLevelWidgets()
        if isinstance(w, QtShortcutsDialog) and w.isVisible()
    ]


def test_key_bindings_window_stays_open_after_the_action(qtbot) -> None:
    from napari_lite import Viewer
    from napari_lite.utils.action_manager import action_manager

    viewer = Viewer()
    try:
        action_manager.trigger('napari:show_shortcuts', viewer)
        gc.collect()
        qtbot.wait(50)
        windows = _open_windows()
        assert len(windows) == 1
        assert windows[0].parent() == viewer.window._qt_window
        windows[0].close()
        qtbot.wait(50)
        assert not _open_windows()
    finally:
        viewer.close()
