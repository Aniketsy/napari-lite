# napari-lite: own code
"""Reader preferences: there are no readers, so there is no preference."""

from __future__ import annotations

from typing import Any


def get_preferred_reader(path: Any) -> None:
    return None


def get_potential_readers(path: Any) -> dict[str, str]:
    return {}
