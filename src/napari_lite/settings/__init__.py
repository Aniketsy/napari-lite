# napari-lite: own code
"""In-memory settings with napari's defaults.

napari keeps its settings in a YAML file through pydantic-settings and
exposes them with ``get_settings()``.  The copied core reads a few dozen
of those fields (see VENDORED.json, crossings into ``napari.settings``)
and subscribes to their change events.  napari-lite provides the same
names and defaults as evented models that live only for the session:
no file, no environment variables, no migrations.

    >>> from napari_lite.settings import get_settings
    >>> get_settings().application.new_labels_dtype = 'uint16'

``settings/_constants.py`` is napari's module, copied as is.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from napari_lite.settings._advanced import AdvancedSettings
from napari_lite.settings._appearance import AppearanceSettings
from napari_lite.settings._application import ApplicationSettings
from napari_lite.settings._experimental import ExperimentalSettings
from napari_lite.settings._shortcuts import ShortcutsSettings
from napari_lite.utils.events.evented_model import EventedModel

__all__ = ['NapariSettings', 'get_settings']


class NapariSettings(EventedModel):
    """The settings sections; same attribute names as napari."""

    application: ApplicationSettings = Field(
        default_factory=ApplicationSettings
    )
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    shortcuts: ShortcutsSettings = Field(default_factory=ShortcutsSettings)
    advanced: AdvancedSettings = Field(default_factory=AdvancedSettings)
    experimental: ExperimentalSettings = Field(
        default_factory=ExperimentalSettings
    )

    def _connect_events(self) -> None:
        self.application._connect_events()
        self.experimental._connect_events()

    def reset(self) -> None:
        """Put every field of every section back to its default."""
        for section_name in type(self).model_fields:
            section = getattr(self, section_name)
            defaults = type(section)()
            for field_name in type(section).model_fields:
                setattr(section, field_name, getattr(defaults, field_name))

    def save(self, path: Any = None, **kwargs: Any) -> None:
        """napari-lite settings are not persisted; kept for API compatibility."""

    def _maybe_save(self) -> None:
        """napari saves here when the settings came from a file."""


_SETTINGS: NapariSettings | None = None


def get_settings(path: Any = None) -> NapariSettings:
    """Return the session settings.

    ``path`` is accepted for compatibility with napari's signature and
    ignored: napari-lite never reads or writes a settings file.
    """
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = NapariSettings()
        _SETTINGS._connect_events()
    return _SETTINGS
