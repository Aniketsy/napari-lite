# napari-lite: own code
"""The Qt side of the viewer actions: the dialogs.

The actions themselves, and their registration with the action manager,
are in ``napari_lite.backends._actions`` (Qt-free); they ask the viewer's
window for its version first.  The Qt window answers with the two dialogs
here; a bare model shown through a ``QtCanvas`` gets them in the active
window.  The names the canvas and the tests import (``open_files``,
``open_paths``, ``open_sample``, ``show_shortcuts``,
``toggle_console_visibility``) are the same functions as there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napari_lite.backends._actions import (
    open_files,
    open_paths,
    open_sample,
    show_shortcuts,
    toggle_console_visibility,
)

if TYPE_CHECKING:
    from napari_lite.components import ViewerModel
    from napari_lite.layers import Layer
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

__all__ = [
    'OPEN_FILTER',
    'open_files',
    'open_files_dialog',
    'open_paths',
    'open_sample',
    'show_shortcuts',
    'show_shortcuts_dialog',
    'toggle_console_visibility',
]

OPEN_FILTER = (
    'Images and arrays (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff '
    '*.npy *.npz);;All files (*)'
)

_open_dialogs: set[QtShortcutsDialog] = set()


def _active_window() -> Any:
    from qtpy.QtWidgets import QApplication

    return QApplication.activeWindow()


def show_shortcuts_dialog(
    viewer: ViewerModel, parent: Any = None
) -> QtShortcutsDialog:
    """Open a window listing the current key bindings.

    The window belongs to ``parent`` (the viewer's main window; the active
    window for a bare model) and is kept in ``_open_dialogs`` until it is
    closed: a parentless Qt window is deleted with its last Python
    reference, and the key binding that calls this keeps none.
    """
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

    if parent is None:
        parent = _active_window()
    dialog = QtShortcutsDialog(viewer, parent=parent)
    _open_dialogs.add(dialog)
    dialog.destroyed.connect(lambda *_: _open_dialogs.discard(dialog))
    dialog.show()
    return dialog


def open_files_dialog(viewer: ViewerModel, parent: Any = None) -> list[Layer]:
    """Ask for files in a dialog and open them with the built-in reader."""
    from qtpy.QtWidgets import QFileDialog

    if parent is None:
        parent = _active_window()
    paths, _selected_filter = QFileDialog.getOpenFileNames(
        parent, 'Open files', '', OPEN_FILTER
    )
    return open_paths(viewer, paths) if paths else []
