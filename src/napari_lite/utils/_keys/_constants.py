# napari-lite: copied from app-model 0.5.1 (app_model/types/_constants.py), BSD 3-Clause
# License, Copyright (c) 2022 Talley Lambert.  Only the imports were changed;
# run tools/copy_app_model_keys.py to refresh.  Do not edit by hand.
# app-model's licence, which goes with this copy:
#
# Copyright (c) 2022, Talley Lambert
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
