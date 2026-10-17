# napari-lite: own code
"""utils/_color.py is pydantic-extra-types' ``Color``, copied: every form a
colour can take parses the same way and formats the same way."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from napari_lite.utils._color import Color

original = pytest.importorskip('pydantic_extra_types.color')

INPUTS = [
    'white',
    'Black',
    'aqua',
    '#fff',
    '#FF0000',
    'ff0000',
    '#ff000080',
    '#abcd',
    'rgb(10, 20, 30)',
    'rgba(10, 20, 30, 0.5)',
    'hsl(120, 100%, 50%)',
    'hsla(0.5turn, 50%, 50%, 0.25)',
    'hsl(90deg, 40%, 60%)',
    (0, 127, 127),
    (0, 255, 255, 0.5),
    [50, 200, 200],
    [140, 140, 140, 0.7],
    (1, 2, 3, 1.0),
]


@pytest.mark.parametrize('value', INPUTS)
def test_parsing_and_formatting(value) -> None:
    ours = Color(value)
    theirs = original.Color(value)
    assert ours.as_rgb() == theirs.as_rgb()
    assert ours.as_rgb_tuple() == theirs.as_rgb_tuple()
    assert ours.as_rgb_tuple(alpha=True) == theirs.as_rgb_tuple(alpha=True)
    assert ours.as_rgb_tuple(alpha=False) == theirs.as_rgb_tuple(alpha=False)
    assert ours.as_hex() == theirs.as_hex()
    assert ours.as_hex('long') == theirs.as_hex('long')
    assert ours.as_hsl() == theirs.as_hsl()
    assert ours.as_named(fallback=True) == theirs.as_named(fallback=True)
    assert str(ours) == str(theirs)
    assert ours.original() == theirs.original()
    assert hash(ours) == hash(theirs)
    assert ours == Color(theirs.as_rgb_tuple(alpha=True))


@pytest.mark.parametrize(
    'value',
    [
        'nope',
        '#ggg',
        'rgb(300, 0, 0)',
        'rgb(10%, 20%, 30%)',  # percentages are not accepted
        'rebeccapurple',  # not in the CSS3 table the package uses
        (1, 2),
        (0, 0, 0, 2.0),
        42,
    ],
)
def test_errors_match(value) -> None:
    with pytest.raises(Exception) as ours:
        Color(value)
    with pytest.raises(Exception) as theirs:
        original.Color(value)
    assert type(ours.value) is type(theirs.value)
    assert str(ours.value) == str(theirs.value)


def test_as_a_pydantic_field() -> None:
    class Ours(BaseModel):
        color: Color

    class Theirs(BaseModel):
        color: original.Color

    for value in ['#102030', 'rgba(1, 2, 3, 0.5)', 'white', (4, 5, 6)]:
        assert (
            Ours(color=value).model_dump_json()
            == Theirs(color=value).model_dump_json()
        )
        assert (
            Ours.model_json_schema()['properties']
            == Theirs.model_json_schema()['properties']
        )
    with pytest.raises(ValidationError):
        Ours(color='not a colour')


def test_theme_uses_it() -> None:
    from napari_lite.utils.theme import Theme, get_theme

    theme = get_theme('dark')
    assert isinstance(theme.canvas, Color)
    assert theme.canvas.as_hex() == original.Color('#000000').as_hex()
    theme.background = 'rgb(1, 2, 3)'
    assert theme.background.as_rgb_tuple() == (1, 2, 3)
    assert Theme.model_fields['canvas'].annotation is Color
