# napari-lite: copied from app-model 0.5.1 (app_model/types/_constants.py), BSD 3-Clause
# License, Copyright (c) 2022 Talley Lambert.  Only the imports were changed;
# run tools/copy_app_model_keys.py to refresh.  Do not edit by hand.
import os
import sys
from enum import Enum, IntEnum


class KeyBindingSource(IntEnum):
    """Keybinding source enum."""

    APP = 0
    PLUGIN = 1
    USER = 2


class OperatingSystem(Enum):
    """Operating system enum."""

    UNKNOWN = 0
    WINDOWS = 1
    MACOS = 2
    LINUX = 3

    @staticmethod
    def current() -> "OperatingSystem":
        """Return the current operating system as enum."""
        return _CURRENT

    @property
    def is_windows(self) -> bool:
        """Returns True if the current operating system is Windows."""
        return _CURRENT == OperatingSystem.WINDOWS

    @property
    def is_linux(self) -> bool:
        """Returns True if the current operating system is Linux."""
        return _CURRENT == OperatingSystem.LINUX

    @property
    def is_mac(self) -> bool:
        """Returns True if the current operating system is MacOS."""
        return _CURRENT == OperatingSystem.MACOS


_CURRENT = OperatingSystem.UNKNOWN
if os.name == "nt":
    _CURRENT = OperatingSystem.WINDOWS
if sys.platform.startswith("linux"):
    _CURRENT = OperatingSystem.LINUX
elif sys.platform == "darwin":
    _CURRENT = OperatingSystem.MACOS
