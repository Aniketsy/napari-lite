# napari-lite: own code
"""Keyboard shortcuts per action name, seeded with napari's defaults."""

from __future__ import annotations

from pydantic import Field, field_validator

from napari_lite.utils.events.evented_model import EventedModel
from napari_lite.utils.key_bindings import KeyBinding, coerce_keybinding
from napari_lite.utils.shortcuts import default_shortcuts


class ShortcutsSettings(EventedModel):
    shortcuts: dict[str, list[KeyBinding]] = Field(default_shortcuts)

    @field_validator('shortcuts', mode='before')
    @classmethod
    def shortcut_validate(
        cls, v: dict[str, list[KeyBinding | str]]
    ) -> dict[str, list[KeyBinding]]:
        for name, value in default_shortcuts.items():
            if name not in v:
                v[name] = list(value)  # a copy of the default
        return {
            name: [coerce_keybinding(kb) for kb in value]
            for name, value in v.items()
        }
