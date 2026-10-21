# napari-lite: own code
"""Viewer actions that need a front end, written for every front end
(issue 5).

napari registers these names with its application window in mind:
``napari:show_shortcuts`` opens the preferences dialog and
``napari:toggle_console_visibility`` the console, neither of which
napari-lite has; ``napari-lite:open_files`` (Ctrl+O) is napari-lite's own.
Importing this module registers the three with the action manager, with
behaviour that asks the viewer's window for its own version
(``show_shortcuts()`` and ``open_files()``, the optional methods of
``napari_lite.backends.Window``): the Qt window opens dialogs
(``napari_lite.qt._viewer_actions``), the notebook window docks widgets.
A bare model shown through a ``QtCanvas`` gets the Qt dialogs in the
active window.

``open_paths`` and ``open_sample`` are what a drop on the canvas, an
upload and the links in the empty-canvas hint call: a failure becomes a
message, not a traceback.  ``shortcuts_html`` is the key bindings as a
table, for the dialog and the notebook alike.  Nothing here imports Qt.
"""

from __future__ import annotations

import html
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from napari_lite.components import ViewerModel
from napari_lite.utils.action_manager import action_manager
from napari_lite.utils.interactions import Shortcut

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from napari_lite.layers import Layer

__all__ = [
    'open_files',
    'open_paths',
    'open_sample',
    'shortcuts_html',
    'show_shortcuts',
    'toggle_console_visibility',
]


def shortcuts_html() -> str:
    """The bound shortcuts as an HTML table, grouped by keymap provider."""
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for name, shortcuts in action_manager._shortcuts.items():
        action = action_manager._actions.get(name)
        if action is None or not shortcuts:
            continue
        provider = action.keymapprovider
        group = provider.__name__ if provider is not None else 'Other'
        if group == 'ViewerModel':
            group = 'Viewer'
        keys = ', '.join(str(Shortcut(s)) for s in shortcuts)
        groups[group].append((keys, action.description))

    order = ['Viewer', 'Image', 'Labels', 'Points', 'Shapes', 'Vectors']
    parts = [
        '<p>Shortcuts are set in code: '
        '<code>get_settings().shortcuts.shortcuts</code>, then '
        '<code>bind_shortcuts_from_settings()</code>.</p>'
    ]
    for group in [*order, *sorted(set(groups) - set(order))]:
        rows = groups.get(group)
        if not rows:
            continue
        parts.append(f'<h3>{html.escape(group)}</h3><table>')
        for keys, description in rows:
            parts.append(
                f'<tr><td><b>{html.escape(keys)}</b>&nbsp;&nbsp;</td>'
                f'<td>{html.escape(description)}</td></tr>'
            )
        parts.append('</table>')
    return '\n'.join(parts)


def _window_method(viewer: ViewerModel, name: str) -> Callable[[], Any] | None:
    """The window's own version of an action, if the viewer has a window
    whose front end gives one (a headless viewer has no window)."""
    window = getattr(viewer, 'window', None)
    return getattr(window, name, None) if window is not None else None


def _qt_application() -> bool:
    """Whether a Qt application exists in this process, without importing
    Qt to find out."""
    if 'qtpy' not in sys.modules:
        return False
    from qtpy.QtWidgets import QApplication

    return QApplication.instance() is not None


def toggle_console_visibility(viewer: ViewerModel) -> None:
    """napari-lite has no console; say so in the status line."""
    viewer.status = 'napari-lite has no console (use your Python session)'


def show_shortcuts(viewer: ViewerModel) -> Any:
    """Ctrl+Alt+/: the key bindings, shown the way the viewer's front end
    shows them (the Qt window: a dialog; the notebook: a docked table)."""
    method = _window_method(viewer, 'show_shortcuts')
    if method is not None:
        return method()
    if _qt_application():  # a bare model shown through a QtCanvas
        from napari_lite.qt._viewer_actions import show_shortcuts_dialog

        return show_shortcuts_dialog(viewer)
    viewer.status = (
        'no window to list the key bindings in: see docs/shortcuts.md'
    )
    return None


def open_files(viewer: ViewerModel) -> list[Layer]:
    """Ctrl+O: files chosen the way the viewer's front end offers (the Qt
    window: a file dialog; the notebook: an upload box), opened with the
    built-in reader."""
    method = _window_method(viewer, 'open_files')
    if method is not None:
        return method() or []
    if _qt_application():  # a bare model shown through a QtCanvas
        from napari_lite.qt._viewer_actions import open_files_dialog

        return open_files_dialog(viewer)
    viewer.status = 'no window to choose files from: viewer.open(path)'
    return []


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
    """``viewer.open`` for files dropped on the canvas, uploaded or picked
    in the dialog: a file the built-in reader cannot open is reported, not
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


def open_sample(viewer: ViewerModel, name: str) -> list[Layer]:
    """A built-in sample from a link in the empty-canvas hint; a failed
    download (imageio fetches most samples once) is reported, not
    raised."""
    from napari_lite.plugins import READER

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
