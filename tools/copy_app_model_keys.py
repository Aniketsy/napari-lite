# napari-lite: own code
"""Copy app-model's key types into ``src/napari_lite/utils/_keys/``.

    python tools/copy_app_model_keys.py

napari uses app-model (BSD-3) for ``KeyCode``, ``KeyMod``, ``KeyCombo``,
``KeyChord`` and ``KeyBinding``; nothing else of app-model is needed in
napari-lite.  This copies the three source files from the installed
app-model into a subpackage, rewrites their imports to be relative, and
adds a header with the origin, the version and app-model's licence (read
from its installed metadata; BSD-3 asks that the notice, conditions and
disclaimer go with every copy).  Run it again to pick up a newer
app-model; ``vendor.toml``'s ``literal_rewrites`` then point the copied
napari code at the subpackage.
"""

from __future__ import annotations

import re
import sys
from importlib.metadata import distribution, version
from pathlib import Path

DEST = (
    Path(__file__).resolve().parent.parent
    / 'src'
    / 'napari_lite'
    / 'utils'
    / '_keys'
)
FILES = {
    '_constants.py': 'app_model/types/_constants.py',
    '_key_codes.py': 'app_model/types/_keys/_key_codes.py',
    '_keybindings.py': 'app_model/types/_keys/_keybindings.py',
}
# Not the own-code marker on purpose: these files keep app-model's
# formatting and are not linted with napari-lite's own code.
HEADER = """# napari-lite: copied from app-model {version} ({path}), BSD 3-Clause
# License, Copyright (c) 2022 Talley Lambert.  Only the imports were changed;
# run tools/copy_app_model_keys.py to refresh.  Do not edit by hand.
# app-model's licence, which goes with this copy:
#
"""
INIT = '''# napari-lite: own code
"""Key codes, modifiers and key bindings, copied from app-model (BSD-3).

Same names as ``app_model.types``: ``KeyCode``, ``KeyMod``, ``KeyCombo``,
``KeyChord``, ``KeyBinding``, ``SimpleKeyBinding``, ``ScanCode``,
``OperatingSystem``.  See tools/copy_app_model_keys.py.
"""

from napari_lite.utils._keys._constants import OperatingSystem
from napari_lite.utils._keys._key_codes import (
    KeyChord,
    KeyCode,
    KeyCombo,
    KeyMod,
    ScanCode,
)
from napari_lite.utils._keys._keybindings import KeyBinding, SimpleKeyBinding

__all__ = [
    'KeyBinding',
    'KeyChord',
    'KeyCode',
    'KeyCombo',
    'KeyMod',
    'OperatingSystem',
    'ScanCode',
    'SimpleKeyBinding',
]
'''


def licence_comment() -> str:
    """app-model's licence text from its installed metadata, as comments."""
    dist = distribution('app-model')
    for name in ('licenses/LICENSE', 'LICENSE'):
        licence = dist.read_text(name)
        if licence:
            break
    else:
        raise SystemExit(
            "app-model's licence is not in its installed metadata"
        )
    lines = licence.strip().splitlines()
    return ''.join(f'# {line}'.rstrip() + '\n' for line in lines) + '\n'


def main() -> int:
    import app_model

    root = Path(app_model.__file__).resolve().parent.parent
    app_model_version = version('app-model')
    DEST.mkdir(parents=True, exist_ok=True)
    for name, rel in FILES.items():
        text = (root / rel).read_text(encoding='utf-8')
        text = re.sub(
            r'^from app_model\.types\._constants import',
            'from napari_lite.utils._keys._constants import',
            text,
            flags=re.MULTILINE,
        )
        text = re.sub(
            r'^from \._key_codes import',
            'from napari_lite.utils._keys._key_codes import',
            text,
            flags=re.MULTILINE,
        )
        header = HEADER.format(version=app_model_version, path=rel)
        header += licence_comment()
        (DEST / name).write_text(header + text, encoding='utf-8', newline='\n')
        print(f'wrote {DEST / name} ({text.count(chr(10))} lines)')
    (DEST / '__init__.py').write_text(INIT, encoding='utf-8', newline='\n')
    print(f'wrote {DEST / "__init__.py"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
