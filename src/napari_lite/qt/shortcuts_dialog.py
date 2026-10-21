# napari-lite: own code
"""A read-only list of the key bindings (napari has a shortcuts editor in
its preferences dialog; napari-lite's shortcuts are configured in code)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from weakref import WeakSet

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QTextBrowser, QVBoxLayout

from napari_lite.backends._actions import shortcuts_html

if TYPE_CHECKING:
    from napari_lite.components import ViewerModel

__all__ = ['QtShortcutsDialog', 'shortcuts_html']


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
