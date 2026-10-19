# napari-lite: own code
"""Colour names and parsing, as the copied napari code expects them from
vispy.

``utils/colormaps/standardize_color.py`` and ``layers/shapes/shapes.py``
take the CSS colour names, hex parsing and ``ColorArray`` from
``vispy.color``; the vendor tool points those imports here
(``tools/vendor.toml``), so the model does not import vispy.  The table
holds the CSS colour names, the one-letter names 'k', 'w', 'r', 'g', 'b',
'y', 'm', 'c' and 'transparent': the same entries as vispy's table, in
vispy's order, which matters when the table is reversed to name a value
(the last entry wins: black, not 'k').  The parsing follows vispy's
rules, so the two agree on every value.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = [
    'Color',
    'ColorArray',
    '_string_to_rgb',
    'get_color_dict',
    'get_color_names',
]

_COLORS: dict[str, str] = {
    'k': '#000000',
    'w': '#FFFFFF',
    'r': '#FF0000',
    'g': '#00FF00',
    'b': '#0000FF',
    'y': '#FFFF00',
    'm': '#FF00FF',
    'c': '#00FFFF',
    'aqua': '#00ffff',
    'aliceblue': '#f0f8ff',
    'antiquewhite': '#faebd7',
    'black': '#000000',
    'blue': '#0000ff',
    'cyan': '#00ffff',
    'darkblue': '#00008b',
    'darkcyan': '#008b8b',
    'darkgreen': '#006400',
    'darkturquoise': '#00ced1',
    'deepskyblue': '#00bfff',
    'green': '#008000',
    'lime': '#00ff00',
    'mediumblue': '#0000cd',
    'mediumspringgreen': '#00fa9a',
    'navy': '#000080',
    'springgreen': '#00ff7f',
    'teal': '#008080',
    'midnightblue': '#191970',
    'dodgerblue': '#1e90ff',
    'lightseagreen': '#20b2aa',
    'forestgreen': '#228b22',
    'seagreen': '#2e8b57',
    'darkslategray': '#2f4f4f',
    'darkslategrey': '#2f4f4f',
    'limegreen': '#32cd32',
    'mediumseagreen': '#3cb371',
    'turquoise': '#40e0d0',
    'royalblue': '#4169e1',
    'steelblue': '#4682b4',
    'darkslateblue': '#483d8b',
    'mediumturquoise': '#48d1cc',
    'indigo': '#4b0082',
    'darkolivegreen': '#556b2f',
    'cadetblue': '#5f9ea0',
    'cornflowerblue': '#6495ed',
    'mediumaquamarine': '#66cdaa',
    'dimgray': '#696969',
    'dimgrey': '#696969',
    'slateblue': '#6a5acd',
    'olivedrab': '#6b8e23',
    'slategray': '#708090',
    'slategrey': '#708090',
    'lightslategray': '#778899',
    'lightslategrey': '#778899',
    'mediumslateblue': '#7b68ee',
    'lawngreen': '#7cfc00',
    'aquamarine': '#7fffd4',
    'chartreuse': '#7fff00',
    'gray': '#808080',
    'grey': '#808080',
    'maroon': '#800000',
    'olive': '#808000',
    'purple': '#800080',
    'lightskyblue': '#87cefa',
    'skyblue': '#87ceeb',
    'blueviolet': '#8a2be2',
    'darkmagenta': '#8b008b',
    'darkred': '#8b0000',
    'saddlebrown': '#8b4513',
    'darkseagreen': '#8fbc8f',
    'lightgreen': '#90ee90',
    'mediumpurple': '#9370db',
    'darkviolet': '#9400d3',
    'palegreen': '#98fb98',
    'darkorchid': '#9932cc',
    'yellowgreen': '#9acd32',
    'sienna': '#a0522d',
    'brown': '#a52a2a',
    'darkgray': '#a9a9a9',
    'darkgrey': '#a9a9a9',
    'greenyellow': '#adff2f',
    'lightblue': '#add8e6',
    'paleturquoise': '#afeeee',
    'lightsteelblue': '#b0c4de',
    'powderblue': '#b0e0e6',
    'firebrick': '#b22222',
    'darkgoldenrod': '#b8860b',
    'mediumorchid': '#ba55d3',
    'rosybrown': '#bc8f8f',
    'darkkhaki': '#bdb76b',
    'silver': '#c0c0c0',
    'mediumvioletred': '#c71585',
    'indianred': '#cd5c5c',
    'peru': '#cd853f',
    'chocolate': '#d2691e',
    'tan': '#d2b48c',
    'lightgray': '#d3d3d3',
    'lightgrey': '#d3d3d3',
    'thistle': '#d8bfd8',
    'goldenrod': '#daa520',
    'orchid': '#da70d6',
    'palevioletred': '#db7093',
    'crimson': '#dc143c',
    'gainsboro': '#dcdcdc',
    'plum': '#dda0dd',
    'burlywood': '#deb887',
    'lightcyan': '#e0ffff',
    'lavender': '#e6e6fa',
    'darksalmon': '#e9967a',
    'palegoldenrod': '#eee8aa',
    'violet': '#ee82ee',
    'azure': '#f0ffff',
    'honeydew': '#f0fff0',
    'khaki': '#f0e68c',
    'lightcoral': '#f08080',
    'sandybrown': '#f4a460',
    'beige': '#f5f5dc',
    'mintcream': '#f5fffa',
    'wheat': '#f5deb3',
    'whitesmoke': '#f5f5f5',
    'ghostwhite': '#f8f8ff',
    'lightgoldenrodyellow': '#fafad2',
    'linen': '#faf0e6',
    'salmon': '#fa8072',
    'oldlace': '#fdf5e6',
    'bisque': '#ffe4c4',
    'blanchedalmond': '#ffebcd',
    'coral': '#ff7f50',
    'cornsilk': '#fff8dc',
    'darkorange': '#ff8c00',
    'deeppink': '#ff1493',
    'floralwhite': '#fffaf0',
    'fuchsia': '#ff00ff',
    'gold': '#ffd700',
    'hotpink': '#ff69b4',
    'ivory': '#fffff0',
    'lavenderblush': '#fff0f5',
    'lemonchiffon': '#fffacd',
    'lightpink': '#ffb6c1',
    'lightsalmon': '#ffa07a',
    'lightyellow': '#ffffe0',
    'magenta': '#ff00ff',
    'mistyrose': '#ffe4e1',
    'moccasin': '#ffe4b5',
    'navajowhite': '#ffdead',
    'orange': '#ffa500',
    'orangered': '#ff4500',
    'papayawhip': '#ffefd5',
    'peachpuff': '#ffdab9',
    'pink': '#ffc0cb',
    'red': '#ff0000',
    'seashell': '#fff5ee',
    'snow': '#fffafa',
    'tomato': '#ff6347',
    'white': '#ffffff',
    'yellow': '#ffff00',
    'transparent': '#00000000',
}


def get_color_names() -> list[str]:
    """The known colour names, sorted."""
    return sorted(_COLORS)


def get_color_dict() -> dict[str, str]:
    """Colour name to hex value."""
    return dict(_COLORS)


def _string_to_rgb(color: str) -> np.ndarray:
    """A colour name or a hex string ('#rgb', '#rgba', '#rrggbb',
    '#rrggbbaa') as an array of 3 or 4 floats in 0..1."""
    if not color.startswith('#'):
        if color.lower() not in _COLORS:
            raise ValueError(f'Color "{color}" unknown')
        color = _COLORS[color.lower()]
    digits = color[1:]
    if len(digits) in (3, 4):
        digits = ''.join(c + c for c in digits)
    if len(digits) not in (6, 8):
        raise ValueError(
            'Hex color must have exactly six or eight elements following '
            'the # sign'
        )
    return np.array(
        [int(digits[i : i + 2], 16) / 255.0 for i in range(0, len(digits), 2)]
    )


def _user_to_rgba(color: Any, expand: bool = True, clip: bool = False) -> Any:
    """Colours in any form (names, hex, tuples, arrays, a ColorArray, a
    sequence of those) as an (N, 4) float32 array in 0..1."""
    if color is None:
        return None
    if isinstance(color, str):
        color = _string_to_rgb(color)
    elif isinstance(color, ColorArray):
        color = color.rgba
    elif isinstance(color, list | tuple) and any(
        isinstance(c, str) for c in color
    ):
        parsed = [_user_to_rgba(c, expand=expand, clip=clip) for c in color]
        if any(len(c) > 1 for c in parsed):
            raise RuntimeError('could not parse colors, are they nested?')
        color = [c[0] for c in parsed]
    color = np.atleast_2d(color).astype(np.float32)
    if color.shape[1] not in (3, 4):
        raise ValueError('color must have three or four elements')
    if expand and color.shape[1] == 3:
        alpha = np.ones((color.shape[0], 1), dtype=np.float32)
        color = np.concatenate((color, alpha), axis=1)
    if color.size and (color.min() < 0 or color.max() > 1):
        if clip:
            color = np.clip(color, 0, 1)
        else:
            raise ValueError(
                'Color values must be between 0 and 1 (or use clip=True '
                'to automatically clip the values).'
            )
    return color


class ColorArray:
    """Colours as an ``(N, 4)`` RGBA float32 array in 0..1."""

    def __init__(
        self,
        color: Any = (0.0, 0.0, 0.0),
        alpha: Any = None,
        clip: bool = False,
    ) -> None:
        rgba = _user_to_rgba(color, clip=clip)
        if alpha is not None:
            rgba[:, 3] = alpha
        self._rgba = rgba

    @property
    def rgba(self) -> np.ndarray:
        return self._rgba.copy()

    @rgba.setter
    def rgba(self, value: Any) -> None:
        self._rgba = _user_to_rgba(value)

    @property
    def rgb(self) -> np.ndarray:
        return self._rgba[:, :3].copy()

    @property
    def alpha(self) -> np.ndarray:
        return self._rgba[:, 3].copy()

    def __len__(self) -> int:
        return len(self._rgba)

    def __getitem__(self, item: Any) -> ColorArray:
        return ColorArray(self._rgba[item])

    def __repr__(self) -> str:
        return f'<ColorArray: {len(self)} colors>'


class Color(ColorArray):
    """One colour; ``rgba`` is a flat array of four floats."""

    def __init__(
        self, color: Any = 'black', alpha: Any = None, clip: bool = False
    ) -> None:
        super().__init__(color, alpha, clip)
        if len(self._rgba) != 1:
            raise ValueError('Color must be a single color, not an array')

    @property
    def rgba(self) -> np.ndarray:
        return self._rgba[0].copy()

    @rgba.setter
    def rgba(self, value: Any) -> None:
        self._rgba = _user_to_rgba(value)

    @property
    def rgb(self) -> np.ndarray:
        return self._rgba[0, :3].copy()

    @property
    def hex(self) -> str:
        r, g, b = (round(v * 255) for v in self._rgba[0, :3])
        return f'#{r:02x}{g:02x}{b:02x}'

    def __repr__(self) -> str:
        return f'<Color: {self.hex}>'
