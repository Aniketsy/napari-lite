# napari-lite: own code
"""Themes: the ``Theme`` model and napari's built-in dark and light themes.

Taken from ``napari.utils.theme`` without the parts that belong to the
application: no plugin themes (npe2), no console syntax-style check
(pygments), no icon rebuilding, no settings refresh.  The QSS template
helpers are kept for the opt-in Qt widgets.
"""

from __future__ import annotations

import re
import sys
from ast import literal_eval
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import field_validator

from napari_lite.utils._color import Color
from napari_lite.utils.events import EventedModel
from napari_lite.utils.events.containers._evented_dict import EventedDict

__all__ = [
    'DARK',
    'LIGHT',
    'Theme',
    'available_themes',
    'get_system_theme',
    'get_theme',
    'is_theme_available',
    'register_theme',
    'unregister_theme',
]


class Theme(EventedModel):
    """Theme model (same fields as napari's).

    Attributes
    ----------
    id : str
        id of the theme.
    label : str
        Name of the theme as it should be shown in the ui.
    type: str
        Whether the theme is "dark" or "light" type.
    syntax_style : str
        Name of the console style (a pygments style name).
    canvas : Color
        Background color of the canvas.
    background, foreground, primary, secondary, highlight, text, icon,
    warning, error, current : Color
        Widget colors, see napari's documentation.
    font_size : str
        Font size (in points, pt) used in the application.
    """

    id: str
    label: str
    type: Literal['dark', 'light']
    syntax_style: str
    canvas: Color
    console: Color
    background: Color
    foreground: Color
    primary: Color
    secondary: Color
    highlight: Color
    text: Color
    icon: Color
    warning: Color
    error: Color
    current: Color
    # base font sizes differ between platforms
    # macOS uses 72 dpi while windows and linux use 96
    # which is a factor of 4/3 so 12 and 9 should be similar
    font_size: str = '12pt' if sys.platform == 'darwin' else '9pt'

    @field_validator('font_size', mode='before')
    @classmethod
    def _ensure_font_size(cls, value: str) -> str:
        assert value.endswith('pt'), 'Font size must be in points (pt).'
        assert int(value[:-2]) > 0, 'Font size must be greater than 0.'
        return value

    def to_rgb_dict(self) -> dict[str, Any]:
        """``model_dump()`` with colors converted to ``rgb(...)`` strings."""
        th = super().model_dump()
        return {
            k: v if not isinstance(v, Color) else v.as_rgb()
            for (k, v) in th.items()
        }


# ---------------------------------------------------------------------------
# QSS template helpers (used when stylesheets are built for Qt widgets)
# ---------------------------------------------------------------------------

increase_pattern = re.compile(r'{{\s?increase\((\w+),?\s?([-\d]+)?\)\s?}}')
decrease_pattern = re.compile(r'{{\s?decrease\((\w+),?\s?([-\d]+)?\)\s?}}')
gradient_pattern = re.compile(r'([vh])gradient\((.+)\)')
darken_pattern = re.compile(r'{{\s?darken\((\w+),?\s?([-\d]+)?\)\s?}}')
lighten_pattern = re.compile(r'{{\s?lighten\((\w+),?\s?([-\d]+)?\)\s?}}')
opacity_pattern = re.compile(r'{{\s?opacity\((\w+),?\s?([-\d]+)?\)\s?}}')


def _platform_aware_font_size_adjustment(pt: str) -> float:
    """Rescale font size adjustments to 72 dpi (macOS)."""
    if sys.platform == 'darwin':
        return float(pt) * 96 / 72
    return float(pt)


def decrease(font_size: str, pt: str) -> str:
    """Decrease fontsize."""
    _pt = _platform_aware_font_size_adjustment(pt)
    return f'{int(font_size[:-2]) - _pt}pt'


def increase(font_size: str, pt: str) -> str:
    """Increase fontsize."""
    _pt = _platform_aware_font_size_adjustment(pt)
    return f'{int(font_size[:-2]) + _pt}pt'


def _parse_color_as_rgb(color: str | Color) -> tuple[int, int, int]:
    if isinstance(color, str):
        if color.startswith('rgb('):
            return literal_eval(color.lstrip('rgb(').rstrip(')'))
        return Color(color).as_rgb_tuple()[:3]
    return color.as_rgb_tuple()[:3]


def _shift_luminance(
    color: tuple[float, float, float], percentage: float
) -> tuple[int, int, int]:
    """Darken or lighten a color preserving hue and perceived saturation."""
    r, g, b = color

    percentage /= 100
    # use perceived luminance for darken/lighten
    lum = 0.299 * r + 0.587 * g + 0.114 * b

    if percentage >= 0:
        target = lum + (255.0 - lum) * percentage
    else:
        target = lum * (1.0 + percentage)

    target = max(0.0, min(255.0, target))

    if lum < 1.0:
        v = max(0, min(255, int(target)))
        return (v, v, v)

    scale = target / lum

    r *= scale
    g *= scale
    b *= scale

    # desaturate colors that were lightened a lot; the coefficients are
    # tunable (same values as napari)
    if scale > 1.0:
        sat = 1.0 / (1.0 + (scale - 1.0) * 0.5)
    else:
        sat = 1.0 + (1.0 - scale) * 0.5

    gray = (r + g + b) / 3.0
    r = gray + (r - gray) * sat
    g = gray + (g - gray) * sat
    b = gray + (b - gray) * sat

    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )


def darken(
    color: str | Color,
    percentage: float = 10,
    theme_type: Literal['dark', 'light'] = 'dark',
) -> str:
    rgb = _parse_color_as_rgb(color)
    percentage *= -1 if theme_type == 'dark' else 1
    r, g, b = _shift_luminance(rgb, percentage)
    return f'rgb({r}, {g}, {b})'


def lighten(
    color: str | Color,
    percentage: float = 10,
    theme_type: Literal['dark', 'light'] = 'dark',
) -> str:
    rgb = _parse_color_as_rgb(color)
    percentage *= -1 if theme_type == 'light' else 1
    r, g, b = _shift_luminance(rgb, percentage)
    return f'rgb({r}, {g}, {b})'


def opacity(color: str | Color, value: int = 255) -> str:
    red, green, blue = _parse_color_as_rgb(color)
    return f'rgba({red}, {green}, {blue}, {max(min(int(value), 255), 0)})'


def gradient(stops: Iterable[str], horizontal: bool = True) -> str:
    if horizontal:
        grad = 'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, '
    else:
        grad = 'qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, '

    _stops = [f'stop: {n} {stop}' for n, stop in enumerate(stops)]
    grad += ', '.join(_stops) + ')'

    return grad


def template(css: str, **theme: Any) -> str:
    """Fill a QSS template with theme colors (same syntax as napari)."""

    def _increase_match(matchobj: re.Match[str]) -> str:
        font_size, to_add = matchobj.groups()
        return increase(theme[font_size], to_add)

    def _decrease_match(matchobj: re.Match[str]) -> str:
        font_size, to_subtract = matchobj.groups()
        return decrease(theme[font_size], to_subtract)

    def darken_match(matchobj: re.Match[str]) -> str:
        color, percentage = matchobj.groups()
        return darken(
            theme[color], float(percentage), theme_type=theme['type']
        )

    def lighten_match(matchobj: re.Match[str]) -> str:
        color, percentage = matchobj.groups()
        return lighten(
            theme[color], float(percentage), theme_type=theme['type']
        )

    def opacity_match(matchobj: re.Match[str]) -> str:
        color, value = matchobj.groups()
        return opacity(theme[color], int(value))

    def gradient_match(matchobj: re.Match[str]) -> str:
        horizontal = matchobj.groups()[1] == 'h'
        stops = [i.strip() for i in matchobj.groups()[1].split('-')]
        return gradient(stops, horizontal)

    for k, v in theme.items():
        css = increase_pattern.sub(_increase_match, css)
        css = decrease_pattern.sub(_decrease_match, css)
        css = gradient_pattern.sub(gradient_match, css)
        css = darken_pattern.sub(darken_match, css)
        css = lighten_pattern.sub(lighten_match, css)
        css = opacity_pattern.sub(opacity_match, css)
        if isinstance(v, Color):
            v = v.as_rgb()
        css = css.replace(f'{{{{ {k} }}}}', v)
    return css


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def get_system_theme() -> str:
    """Return the system default theme, 'dark' or 'light'.

    Uses Qt's color scheme hint when a Qt application exists; 'dark'
    otherwise.
    """
    try:
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QGuiApplication
    except (ImportError, RuntimeError):
        return 'dark'

    style_hints = QGuiApplication.styleHints()
    if style_hints is None:
        return 'dark'

    scheme = style_hints.colorScheme()
    match scheme:
        case Qt.ColorScheme.Dark:
            return 'dark'
        case Qt.ColorScheme.Light:
            return 'light'
        case _:
            return 'dark'


def get_theme(theme_id: str) -> Theme:
    """Get a copy of the theme with this id ('system' resolves to the OS one).

    Changes to the copy do not affect the registry; register the changed
    theme again to make them visible.
    """
    if theme_id == 'system':
        theme_id = get_system_theme()

    if theme_id not in _themes:
        raise ValueError(
            f'Unrecognized theme {theme_id}. Available themes are '
            f'{available_themes()}'
        )
    return _themes[theme_id].model_copy()


_themes: EventedDict[str, Theme] = EventedDict(basetype=Theme)


def register_theme(
    theme_id: str, theme: dict[str, Any] | Theme, source: str = 'user'
) -> None:
    """Register a new or updated theme.

    ``source`` names where the theme comes from; napari uses it to pick the
    icon folder, napari-lite only stores the theme.
    """
    if isinstance(theme, dict):
        theme = Theme(**theme)
    assert isinstance(theme, Theme)
    _themes[theme_id] = theme


def unregister_theme(theme_id: str) -> None:
    """Remove a registered theme."""
    _themes.pop(theme_id, None)


def available_themes() -> list[str]:
    """Ids of the registered themes plus 'system'."""
    return [*_themes, 'system']


def is_theme_available(theme_id: str) -> bool:
    """True if ``theme_id`` is registered or is 'system'."""
    return theme_id == 'system' or theme_id in _themes


# Note: these colors are sometimes lightened / darkened in the qss file.
DARK = Theme(
    id='dark',
    type='dark',
    label='Default Dark',
    background='rgb(35, 36, 43)',
    foreground='rgb(46, 51, 62)',
    primary='rgb(66, 74, 84)',
    secondary='rgb(86, 95, 108)',
    highlight='rgb(97, 105, 110)',
    text='rgb(240, 241, 242)',
    icon='rgb(209, 210, 212)',
    warning='rgb(227, 182, 23)',
    error='rgb(153, 18, 31)',
    current='rgb(69, 96, 196)',
    syntax_style='native',
    console='rgb(18, 18, 18)',
    canvas='black',
    font_size='12pt' if sys.platform == 'darwin' else '9pt',
)
LIGHT = Theme(
    id='light',
    type='light',
    label='Default Light',
    background='rgb(235, 231, 230)',
    foreground='rgb(221, 218, 216)',
    primary='rgb(197, 195, 193)',
    secondary='rgb(180, 178, 175)',
    highlight='rgb(175, 172, 170)',
    text='rgb(30, 30, 33)',
    icon='rgb(62, 63, 65)',
    warning='rgb(227, 182, 23)',
    error='rgb(255, 18, 31)',
    current='rgb(160, 184, 255)',
    syntax_style='default',
    console='white',
    canvas='white',
    font_size='12pt' if sys.platform == 'darwin' else '9pt',
)

register_theme('dark', DARK, 'builtin')
register_theme('light', LIGHT, 'builtin')
