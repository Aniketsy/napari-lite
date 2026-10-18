# napari-lite: own code
"""The empty canvas: what napari's welcome screen does, in napari-lite's terms.

A column centred over the canvas: a headline, a line under it, then rows
with a dim label on the left and the content on the right (text, links,
or commands in a fixed font, one per line), so that nothing wraps in the
middle of a command.  The window fills it with the ways to load data;
``QtCanvas(hint=...)`` with a plain string shows the headline alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QFontDatabase
from qtpy.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from napari_lite.utils.theme import darken, get_theme

_TAG = re.compile(r'<[^>]+>')


@dataclass(frozen=True)
class HintRow:
    """One row of the hint: ``label`` on the left, ``lines`` on the right.

    ``mono`` lines are commands, in a fixed font and never wrapped; ``rich``
    lines are HTML with ``<a href="...">`` links, whose href reaches
    ``QtCanvasHint.link_activated``.
    """

    label: str
    lines: tuple[str, ...]
    mono: bool = False
    rich: bool = False

    def text(self) -> str:
        """The row as plain text."""
        lines = [
            unescape(_TAG.sub('', line)) if self.rich else line
            for line in self.lines
        ]
        return f'{self.label}: ' + ' / '.join(lines)


def _fixed_family() -> str:
    """A monospace family that sits well next to the UI font: the usual
    ones of each platform before the system's fixed font (Courier New on
    Windows, thin and dated)."""
    families = set(QFontDatabase.families())
    for name in (
        'Consolas',
        'Cascadia Mono',
        'Menlo',
        'SF Mono',
        'DejaVu Sans Mono',
        'Liberation Mono',
    ):
        if name in families:
            return name
    return QFontDatabase.systemFont(
        QFontDatabase.SystemFont.FixedFont
    ).family()


class QtCanvasHint(QWidget):
    """The hint widget; ``set_content`` fills it, ``text`` reads it back."""

    link_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = ''
        self._lead = ''
        self._rows: tuple[HintRow, ...] = ()
        self._theme = 'dark'

        self._title_label = QLabel()
        self._title_label.setObjectName('hint_title')
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lead_label = QLabel()
        self._lead_label.setObjectName('hint_lead')
        self._lead_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(18)
        self._grid.setVerticalSpacing(5)
        self._row_widgets: list[QWidget] = []

        rows = QHBoxLayout()
        rows.setContentsMargins(0, 0, 0, 0)
        rows.addStretch(1)
        rows.addLayout(self._grid)
        rows.addStretch(1)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)
        layout.addStretch(5)
        layout.addWidget(self._title_label)
        layout.addSpacing(4)
        layout.addWidget(self._lead_label)
        layout.addSpacing(26)
        layout.addLayout(rows)
        layout.addStretch(6)
        self.setLayout(layout)
        self.apply_theme(self._theme)

    def set_content(
        self,
        title: str,
        rows: tuple[HintRow, ...] | list[HintRow] = (),
        *,
        lead: str = '',
    ) -> None:
        self._title = title
        self._lead = lead
        self._rows = tuple(rows)
        self._rebuild()

    def text(self) -> str:
        """Everything shown, as plain text, one part per line."""
        parts = [self._title, self._lead] + [row.text() for row in self._rows]
        return '\n'.join(part for part in parts if part)

    def apply_theme(self, theme: str) -> None:
        """Colours from the theme (dim text as napari's welcome screen uses)
        and sizes from the application font."""
        self._theme = theme
        colours = get_theme(theme)
        dim = darken(colours.text, 25)
        dimmer = darken(colours.text, 45)
        dark_canvas = sum(colours.canvas.as_rgb_tuple()[:3]) < 384
        self._link = '#8ab4f8' if dark_canvas else '#1a56db'
        base = QApplication.font().pointSize()
        base = base if base > 0 else 9
        fixed = _fixed_family()
        self.setStyleSheet(
            'QtCanvasHint, QtCanvasHint QLabel { background: transparent; }'
            f'QtCanvasHint QLabel {{ color: {dim}; font-size: {base + 2}pt; }}'
            f'QtCanvasHint QLabel#hint_title {{ font-size: {base + 6}pt; }}'
            f'QtCanvasHint QLabel#hint_lead {{ color: {dimmer}; font-size: {base + 1}pt; }}'
            f'QtCanvasHint QLabel#hint_key {{ color: {dimmer}; }}'
            f'QtCanvasHint QLabel#hint_mono {{ font-family: "{fixed}"; font-size: {base + 1}pt; }}'
        )
        self._rebuild()

    # internals
    def _rebuild(self) -> None:
        for widget in self._row_widgets:
            self._grid.removeWidget(widget)
            widget.deleteLater()
        self._row_widgets.clear()
        self._title_label.setText(self._title)
        self._title_label.setVisible(bool(self._title))
        self._lead_label.setText(self._lead)
        self._lead_label.setVisible(bool(self._lead))
        line = 0
        for row in self._rows:
            key = QLabel()
            key.setObjectName('hint_key')
            key.setTextFormat(Qt.TextFormat.PlainText)
            key.setText(row.label)
            key.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            )
            self._grid.addWidget(key, line, 0)
            self._row_widgets.append(key)
            for text in row.lines:
                label = QLabel()
                if row.rich:
                    label.setTextFormat(Qt.TextFormat.RichText)
                    label.setText(
                        re.sub(
                            r'<a\b',
                            f'<a style="color: {self._link}; '
                            'text-decoration: none"',
                            text,
                        )
                    )
                    label.setTextInteractionFlags(
                        Qt.TextInteractionFlag.LinksAccessibleByMouse
                    )
                    label.setOpenExternalLinks(False)
                    label.linkActivated.connect(self.link_activated)
                else:
                    label.setTextFormat(Qt.TextFormat.PlainText)
                    label.setText(text)
                if row.mono:
                    label.setObjectName('hint_mono')
                label.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
                self._grid.addWidget(label, line, 1)
                self._row_widgets.append(label)
                line += 1
        self._grid.setColumnStretch(1, 1)
