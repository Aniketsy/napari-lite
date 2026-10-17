# napari-lite: own code
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
