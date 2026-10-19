# napari-lite: own code
"""The key names napari's key bindings use, spelled as vispy spells them.

napari's ``utils/key_bindings.py`` takes them from ``vispy.util.keys``;
the vendor tool points that import here (``tools/vendor.toml``), so the
model does not import vispy.  A ``Key`` is a ``str`` (its primary name)
that also compares equal to its other names, ignoring case, to another
key object with the same name, vispy's included, and to the ordinal of a
one-character name, as vispy's ``Key`` does.  Being a ``str`` matters when
vispy is present: vispy's keys accept strings on either side of ``==``,
so the two kinds mix in dictionaries and lists.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    'ALT',
    'BACKSPACE',
    'CONTROL',
    'DELETE',
    'DOWN',
    'END',
    'ENTER',
    'ESCAPE',
    'F1',
    'F2',
    'F3',
    'F4',
    'F5',
    'F6',
    'F7',
    'F8',
    'F9',
    'F10',
    'F11',
    'F12',
    'HOME',
    'INSERT',
    'LEFT',
    'META',
    'PAGEDOWN',
    'PAGEUP',
    'RIGHT',
    'SHIFT',
    'SPACE',
    'TAB',
    'UP',
    'Key',
]


class Key(str):
    """The identity of a key, known by one or more names."""

    __slots__ = ('_names', '_names_upper')

    def __new__(cls, *names: str) -> Key:
        key = super().__new__(cls, names[0])
        key._names = names
        key._names_upper = tuple(n.upper() for n in names)
        return key

    @property
    def name(self) -> str:
        """The primary name."""
        return self._names[0]

    def __hash__(self) -> int:
        return hash(self._names[0])

    def __repr__(self) -> str:
        return '<Key ' + ', '.join(repr(n) for n in self._names) + '>'

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Key):
            return self._names[0] == other._names[0]
        if isinstance(other, str):
            return other.upper() in self._names_upper
        names_upper = getattr(other, '_names_upper', None)  # vispy's Key
        if names_upper is not None:
            return self._names_upper[0] in names_upper
        if isinstance(other, int):
            return other in [ord(n) for n in self._names_upper if len(n) == 1]
        return NotImplemented

    def __ne__(self, other: Any) -> bool:
        equal = self.__eq__(other)
        return equal if equal is NotImplemented else not equal


SHIFT = Key('Shift')
CONTROL = Key('Control')
ALT = Key('Alt')
META = Key('Meta')

UP = Key('Up')
DOWN = Key('Down')
LEFT = Key('Left')
RIGHT = Key('Right')
PAGEUP = Key('PageUp')
PAGEDOWN = Key('PageDown')

INSERT = Key('Insert')
DELETE = Key('Delete')
HOME = Key('Home')
END = Key('End')

ESCAPE = Key('Escape')
BACKSPACE = Key('Backspace')

F1 = Key('F1')
F2 = Key('F2')
F3 = Key('F3')
F4 = Key('F4')
F5 = Key('F5')
F6 = Key('F6')
F7 = Key('F7')
F8 = Key('F8')
F9 = Key('F9')
F10 = Key('F10')
F11 = Key('F11')
F12 = Key('F12')

SPACE = Key('Space', ' ')
ENTER = Key('Enter', 'Return', '\n')
TAB = Key('Tab', '\t')
