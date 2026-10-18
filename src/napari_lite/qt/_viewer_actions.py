# napari-lite: own code
"""Viewer actions whose napari version needs the application window, and
napari-lite's own.

``components/_viewer_key_bindings.py`` (copied) registers napari's viewer
actions.  Two of them open parts napari-lite does not have: the IPython
console and the preferences dialog with the shortcuts editor.  Importing
this module re-registers those two names with napari-lite behaviour, so
the default shortcuts keep working, and adds ``napari-lite:open_files``
(Ctrl+O), a file dialog in front of the built-in reader.  ``open_paths``
and ``open_sample`` are what a drop on the canvas and the links in the
empty-canvas hint call: a failure becomes a message, not a traceback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from napari_lite.components import ViewerModel
from napari_lite.plugins import READER
from napari_lite.utils.action_manager import action_manager

if TYPE_CHECKING:
    from collections.abc import Sequence

    from napari_lite.layers import Layer
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

__all__ = [
    'open_files',
    'open_paths',
    'open_sample',
    'show_shortcuts',
    'toggle_console_visibility',
]

OPEN_FILTER = (
    'Images and arrays (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff '
    '*.npy *.npz);;All files (*)'
)


def _parent_window(viewer: ViewerModel) -> Any:
    """The viewer's main window, or the active window for a bare
    ``ViewerModel`` shown through a ``QtCanvas``."""
    from qtpy.QtWidgets import QApplication

    window = getattr(viewer, 'window', None)
    if window is not None:
        return window._qt_window
    return QApplication.activeWindow()


def toggle_console_visibility(viewer: ViewerModel) -> None:
    """napari-lite has no console; say so in the status line."""
    viewer.status = 'napari-lite has no console (use your Python session)'


_open_dialogs: set[QtShortcutsDialog] = set()


def show_shortcuts(viewer: ViewerModel) -> QtShortcutsDialog:
    """Open a window listing the current key bindings.

    The window belongs to the viewer's main window when there is one (the
    active window otherwise) and is kept in ``_open_dialogs`` until it is
    closed: a parentless Qt window is deleted with its last Python
    reference, and the key binding that calls this keeps none.
    """
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

    dialog = QtShortcutsDialog(viewer, parent=_parent_window(viewer))
    _open_dialogs.add(dialog)
    dialog.destroyed.connect(lambda *_: _open_dialogs.discard(dialog))
    dialog.show()
    return dialog


def _report(viewer: ViewerModel, exc: BaseException) -> None:
    """A failed open from the GUI: the message in the status bar and as an
    error notification, no traceback."""
    from napari_lite.utils.notifications import show_error

    cause = getattr(exc, 'original_error', None) or exc.__cause__
    message = f'{exc} {cause}' if cause else str(exc)
    viewer.status = message.splitlines()[0]
    show_error(message)


def open_paths(
    viewer: ViewerModel, paths: Sequence[str], *, stack: bool = False
) -> list[Layer]:
    """``viewer.open`` for files dropped on the canvas or picked in the
    dialog: a file the built-in reader cannot open is reported, not
    raised."""
    from napari_lite.errors.reader_errors import (
        NoAvailableReaderError,
        ReaderPluginError,
    )

    try:
        return viewer.open(list(paths), stack=stack)
    except (NoAvailableReaderError, ReaderPluginError) as exc:
        _report(viewer, exc)
        return []


def open_files(viewer: ViewerModel) -> list[Layer]:
    """Ctrl+O: ask for files and open them with the built-in reader."""
    from qtpy.QtWidgets import QFileDialog

    paths, _selected_filter = QFileDialog.getOpenFileNames(
        _parent_window(viewer), 'Open files', '', OPEN_FILTER
    )
    return open_paths(viewer, paths) if paths else []


def open_sample(viewer: ViewerModel, name: str) -> list[Layer]:
    """A built-in sample from a link in the empty-canvas hint; a failed
    download (imageio fetches most samples once) is reported, not
    raised."""
    try:
        return viewer.open_sample(READER, name)
    # a download fails in many ways; the user needs the message, no more
    except Exception as exc:
        _report(viewer, exc)
        return []


action_manager.register_action(
    name='napari:toggle_console_visibility',
    command=toggle_console_visibility,
    description='Show/Hide IPython console (napari-lite has none)',
    keymapprovider=ViewerModel,
)
action_manager.register_action(
    name='napari:show_shortcuts',
    command=show_shortcuts,
    description='Show all key bindings',
    keymapprovider=ViewerModel,
)
action_manager.register_action(
    name='napari-lite:open_files',
    command=open_files,
    description='Open files (png, jpg, tif, npy, npz)',
    keymapprovider=ViewerModel,
)
