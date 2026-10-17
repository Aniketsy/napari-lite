# napari-lite: own code
"""A read-only list of the key bindings (napari has a shortcuts editor in
its preferences dialog; napari-lite's shortcuts are configured in code)."""

from __future__ import annotations

import html
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar
from weakref import WeakSet

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QTextBrowser, QVBoxLayout

from napari_lite.utils.action_manager import action_manager
from napari_lite.utils.interactions import Shortcut

if TYPE_CHECKING:
    from napari_lite.components import ViewerModel

__all__ = ['QtShortcutsDialog', 'shortcuts_html']


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


class QtShortcutsDialog(QDialog):
    """Non-modal window with the shortcut table."""

    _instances: ClassVar[WeakSet[QtShortcutsDialog]] = WeakSet()

    def __init__(self, viewer: ViewerModel | None = None, parent=None) -> None:
        super().__init__(parent)
        self._instances.add(self)
        self.viewer = viewer
        self.setWindowTitle('napari-lite key bindings')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(False)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(shortcuts_html())
        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        self.setLayout(layout)
        self.resize(560, 640)
