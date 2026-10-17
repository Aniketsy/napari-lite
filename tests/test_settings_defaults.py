# napari-lite: own code
"""The settings shim exposes napari's field names with napari's defaults.

``spikes/defaults.json`` is a dump of napari's settings (made with
``spikes/make_defaults.py`` in a napari environment).  Every field the
shim defines must exist there with the same default.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DEFAULTS = json.loads(
    (
        Path(__file__).resolve().parents[1] / 'spikes' / 'defaults.json'
    ).read_text()
)['sections']

# napari's default font size depends on the platform the dump was made on;
# so does the text of key bindings (Ctrl on Windows and Linux, Cmd on macOS)
PLATFORM_DEPENDENT = {('appearance', 'font_size'), ('shortcuts', 'shortcuts')}


def _fields():
    from napari_lite.settings import NapariSettings

    for section_name, info in NapariSettings.model_fields.items():
        for field_name in info.annotation.model_fields:
            yield section_name, field_name


@pytest.fixture
def settings():
    from napari_lite.settings import get_settings

    s = get_settings()
    yield s
    s.reset()


@pytest.mark.parametrize(('section', 'field'), list(_fields()))
def test_default_matches_napari(settings, section: str, field: str) -> None:
    assert section in DEFAULTS, f'napari has no settings section {section}'
    assert field in DEFAULTS[section], f'napari has no field {section}.{field}'
    if (section, field) in PLATFORM_DEPENDENT:
        pytest.skip('platform dependent default')
    ours = getattr(settings, section).model_dump(mode='json')[field]
    assert ours == DEFAULTS[section][field]


def test_default_shortcuts_match_napari(settings) -> None:
    """Same action names and the same number of bindings per action; the
    key text itself depends on the platform (Ctrl or Cmd)."""
    ours = settings.shortcuts.model_dump(mode='json')['shortcuts']
    theirs = DEFAULTS['shortcuts']['shortcuts']
    assert set(ours) == set(theirs)
    assert {k: len(v) for k, v in ours.items()} == {
        k: len(v) for k, v in theirs.items()
    }
    if sys.platform != 'darwin':
        assert ours == theirs


def test_font_size_default(settings) -> None:
    assert settings.appearance.font_size == (
        12 if sys.platform == 'darwin' else 9
    )


def test_singleton_and_events(settings) -> None:
    from napari_lite.settings import get_settings

    assert get_settings() is settings
    seen = []
    settings.application.events.grid_stride.connect(
        lambda e: seen.append(e.value)
    )
    settings.application.grid_stride = 2
    assert seen == [2]
    with pytest.raises(ValueError, match='0'):
        settings.application.grid_stride = 0


def test_values_are_coerced(settings) -> None:
    from napari_lite.settings._constants import LabelDTypes

    settings.application.new_labels_dtype = 'uint16'
    assert settings.application.new_labels_dtype is LabelDTypes.uint16
    with pytest.raises(ValueError, match='not found'):
        settings.appearance.theme = 'no-such-theme'


def test_backends_follow_settings(settings) -> None:
    from napari_lite.utils import triangulation_backend as tb

    settings.experimental.triangulation_backend = 'pure python'
    assert tb.get_backend() is tb.TriangulationBackend.pure_python
