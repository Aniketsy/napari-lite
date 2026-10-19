# napari-lite: own code
"""Dump napari's default settings to ``tests/data/napari_defaults.json``.

Needs napari installed (run it in a napari environment, once).  The output
is the reference for napari-lite's in-memory settings shim: the shim must
expose the same field names with the same defaults, and
``tests/test_settings_defaults.py`` compares against this file.

    python tools/make_settings_defaults.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = (
    Path(__file__).resolve().parent.parent
    / 'tests'
    / 'data'
    / 'napari_defaults.json'
)


def main() -> int:
    import napari
    from napari.settings import NapariSettings

    # ``config_path=None`` means: never read or write a settings file.
    settings = NapariSettings(config_path=None)
    sections: dict[str, dict] = {}
    for name in settings.model_fields:
        value = getattr(settings, name)
        if hasattr(value, 'model_dump'):
            sections[name] = value.model_dump(mode='json')
        else:
            sections[name] = value
    data = {
        'napari_version': napari.__version__,
        'sections': sections,
    }
    OUT.write_text(json.dumps(data, indent=2, default=str) + '\n')
    print(f'wrote {OUT} ({len(sections)} sections)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
