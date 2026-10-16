# napari-lite: own code
"""Themes: dark and light, and the canvas follows the viewer theme."""

from __future__ import annotations

import numpy as np
import pytest


def test_builtin_themes() -> None:
    from napari_lite.utils.theme import (
        available_themes,
        get_theme,
        is_theme_available,
    )

    assert set(available_themes()) == {'dark', 'light', 'system'}
    assert is_theme_available('dark')
    assert not is_theme_available('solarized')
    assert get_theme('dark').canvas.as_rgb_tuple()[:3] == (0, 0, 0)
    assert get_theme('light').canvas.as_rgb_tuple()[:3] == (255, 255, 255)
    assert get_theme('system').type in {'dark', 'light'}
    with pytest.raises(ValueError, match='Unrecognized theme'):
        get_theme('solarized')


def test_register_theme_copies() -> None:
    from napari_lite.utils.theme import (
        get_theme,
        register_theme,
        unregister_theme,
    )

    custom = get_theme('dark')
    custom.id = 'inky'
    custom.canvas = 'rgb(10, 20, 30)'
    register_theme('inky', custom)
    try:
        assert get_theme('inky').canvas.as_rgb_tuple()[:3] == (10, 20, 30)
        # get_theme hands out copies
        get_theme('inky').canvas = 'white'
        assert get_theme('inky').canvas.as_rgb_tuple()[:3] == (10, 20, 30)
    finally:
        unregister_theme('inky')


def test_canvas_background_follows_viewer_theme() -> None:
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    viewer.theme = 'light'
    np.testing.assert_allclose(
        viewer._canvas.background_color, [1.0, 1.0, 1.0, 1.0]
    )
    viewer.theme = 'dark'
    np.testing.assert_allclose(
        viewer._canvas.background_color, [0.0, 0.0, 0.0, 1.0]
    )
    with pytest.raises(ValueError, match='not found'):
        viewer.theme = 'solarized'
