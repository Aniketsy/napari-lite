# napari-lite: own code
"""Appearance settings: theme, font size, highlight, tooltips."""

from __future__ import annotations

from pydantic import Field, field_validator

from napari_lite.utils.events.evented_model import EventedModel
from napari_lite.utils.theme import available_themes, get_theme


class HighlightSettings(EventedModel):
    highlight_thickness: int = Field(1, ge=1, le=10)
    highlight_color: list[float] = Field([0.0, 0.6, 1.0, 1.0])


class AppearanceSettings(EventedModel):
    theme: str = 'dark'
    font_size: int = Field(int(get_theme('dark').font_size[:-2]), ge=5, le=20)
    highlight: HighlightSettings = Field(default_factory=HighlightSettings)
    layer_tooltip_visibility: bool = False
    update_status_based_on_layer: bool = True

    @field_validator('theme')
    @classmethod
    def _theme_exists(cls, value: str) -> str:
        if value not in available_themes():
            raise ValueError(
                f'Theme {value!r} not found; options are '
                f'{", ".join(available_themes())}.'
            )
        return value
