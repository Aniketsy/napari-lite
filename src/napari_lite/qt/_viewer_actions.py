# napari-lite: own code
"""Viewer actions whose napari version needs the application window.

``components/_viewer_key_bindings.py`` (copied) registers napari's viewer
actions.  Two of them open parts napari-lite does not have: the IPython
console and the preferences dialog with the shortcuts editor.  Importing
this module re-registers those two names with napari-lite behaviour, so the
default shortcuts keep working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from napari_lite.components import ViewerModel
from napari_lite.utils.action_manager import action_manager

if TYPE_CHECKING:
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

__all__ = ['show_shortcuts', 'toggle_console_visibility']


def toggle_console_visibility(viewer: ViewerModel) -> None:
    """napari-lite has no console; say so in the status line."""
    viewer.status = 'napari-lite has no console (use your Python session)'


def show_shortcuts(viewer: ViewerModel) -> QtShortcutsDialog:
    """Open a window listing the current key bindings."""
    from napari_lite.qt.shortcuts_dialog import QtShortcutsDialog

    dialog = QtShortcutsDialog(viewer)
    dialog.show()
    return dialog


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
