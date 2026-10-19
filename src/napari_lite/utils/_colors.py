# napari-lite: own code
"""Colour names and parsing, as the copied napari code expects them from
vispy.

``utils/colormaps/standardize_color.py`` and ``layers/shapes/shapes.py``
take the CSS colour names, hex parsing and ``ColorArray`` from
``vispy.color``; the vendor tool points those imports here
(``tools/vendor.toml``), so the model does not import vispy.  The table
holds the CSS colour names, the one-letter names 'k', 'w', 'r', 'g', 'b',
'y', 'm', 'c' and 'transparent': the same entries as vispy's table, which
is the same standard.  The parsing follows vispy's rules, so the two
agree on every value.
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
    'aliceblue': '#f0f8ff',
    'antiquewhite': '#faebd7',
    'aqua': '#00ffff',
    'aquamarine': '#7fffd4',
    'azure': '#f0ffff',
    'b': '#0000FF',
    'beige': '#f5f5dc',
    'bisque': '#ffe4c4',
    'black': '#000000',
    'blanchedalmond': '#ffebcd',
    'blue': '#0000ff',
    'blueviolet': '#8a2be2',
    'brown': '#a52a2a',
    'burlywood': '#deb887',
    'c': '#00FFFF',
    'cadetblue': '#5f9ea0',
    'chartreuse': '#7fff00',
    'chocolate': '#d2691e',
    'coral': '#ff7f50',
    'cornflowerblue': '#6495ed',
    'cornsilk': '#fff8dc',
    'crimson': '#dc143c',
    'cyan': '#00ffff',
    'darkblue': '#00008b',
    'darkcyan': '#008b8b',
    'darkgoldenrod': '#b8860b',
    'darkgray': '#a9a9a9',
    'darkgreen': '#006400',
    'darkgrey': '#a9a9a9',
    'darkkhaki': '#bdb76b',
    'darkmagenta': '#8b008b',
    'darkolivegreen': '#556b2f',
    'darkorange': '#ff8c00',
    'darkorchid': '#9932cc',
    'darkred': '#8b0000',
    'darksalmon': '#e9967a',
    'darkseagreen': '#8fbc8f',
    'darkslateblue': '#483d8b',
    'darkslategray': '#2f4f4f',
    'darkslategrey': '#2f4f4f',
    'darkturquoise': '#00ced1',
    'darkviolet': '#9400d3',
    'deeppink': '#ff1493',
    'deepskyblue': '#00bfff',
    'dimgray': '#696969',
    'dimgrey': '#696969',
    'dodgerblue': '#1e90ff',
    'firebrick': '#b22222',
    'floralwhite': '#fffaf0',
    'forestgreen': '#228b22',
    'fuchsia': '#ff00ff',
    'g': '#00FF00',
    'gainsboro': '#dcdcdc',
    'ghostwhite': '#f8f8ff',
    'gold': '#ffd700',
    'goldenrod': '#daa520',
    'gray': '#808080',
    'green': '#008000',
    'greenyellow': '#adff2f',
    'grey': '#808080',
    'honeydew': '#f0fff0',
    'hotpink': '#ff69b4',
    'indianred': '#cd5c5c',
    'indigo': '#4b0082',
    'ivory': '#fffff0',
    'k': '#000000',
    'khaki': '#f0e68c',
    'lavender': '#e6e6fa',
    'lavenderblush': '#fff0f5',
    'lawngreen': '#7cfc00',
    'lemonchiffon': '#fffacd',
    'lightblue': '#add8e6',
    'lightcoral': '#f08080',
    'lightcyan': '#e0ffff',
    'lightgoldenrodyellow': '#fafad2',
    'lightgray': '#d3d3d3',
    'lightgreen': '#90ee90',
    'lightgrey': '#d3d3d3',
    'lightpink': '#ffb6c1',
    'lightsalmon': '#ffa07a',
    'lightseagreen': '#20b2aa',
    'lightskyblue': '#87cefa',
    'lightslategray': '#778899',
    'lightslategrey': '#778899',
    'lightsteelblue': '#b0c4de',
    'lightyellow': '#ffffe0',
    'lime': '#00ff00',
    'limegreen': '#32cd32',
    'linen': '#faf0e6',
    'm': '#FF00FF',
    'magenta': '#ff00ff',
    'maroon': '#800000',
    'mediumaquamarine': '#66cdaa',
    'mediumblue': '#0000cd',
    'mediumorchid': '#ba55d3',
    'mediumpurple': '#9370db',
    'mediumseagreen': '#3cb371',
    'mediumslateblue': '#7b68ee',
    'mediumspringgreen': '#00fa9a',
    'mediumturquoise': '#48d1cc',
    'mediumvioletred': '#c71585',
    'midnightblue': '#191970',
    'mintcream': '#f5fffa',
    'mistyrose': '#ffe4e1',
    'moccasin': '#ffe4b5',
    'navajowhite': '#ffdead',
    'navy': '#000080',
    'oldlace': '#fdf5e6',
    'olive': '#808000',
    'olivedrab': '#6b8e23',
    'orange': '#ffa500',
    'orangered': '#ff4500',
    'orchid': '#da70d6',
    'palegoldenrod': '#eee8aa',
    'palegreen': '#98fb98',
    'paleturquoise': '#afeeee',
    'palevioletred': '#db7093',
    'papayawhip': '#ffefd5',
    'peachpuff': '#ffdab9',
    'peru': '#cd853f',
    'pink': '#ffc0cb',
    'plum': '#dda0dd',
    'powderblue': '#b0e0e6',
    'purple': '#800080',
    'r': '#FF0000',
    'red': '#ff0000',
    'rosybrown': '#bc8f8f',
    'royalblue': '#4169e1',
    'saddlebrown': '#8b4513',
    'salmon': '#fa8072',
    'sandybrown': '#f4a460',
    'seagreen': '#2e8b57',
    'seashell': '#fff5ee',
    'sienna': '#a0522d',
    'silver': '#c0c0c0',
    'skyblue': '#87ceeb',
    'slateblue': '#6a5acd',
    'slategray': '#708090',
    'slategrey': '#708090',
    'snow': '#fffafa',
    'springgreen': '#00ff7f',
    'steelblue': '#4682b4',
    'tan': '#d2b48c',
    'teal': '#008080',
    'thistle': '#d8bfd8',
    'tomato': '#ff6347',
    'transparent': '#00000000',
    'turquoise': '#40e0d0',
    'violet': '#ee82ee',
    'w': '#FFFFFF',
    'wheat': '#f5deb3',
    'white': '#ffffff',
    'whitesmoke': '#f5f5f5',
    'y': '#FFFF00',
    'yellow': '#ffff00',
    'yellowgreen': '#9acd32',
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
