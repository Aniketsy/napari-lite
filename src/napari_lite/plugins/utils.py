# napari-lite: own code
"""Reader lookups: the built-in reader, no preferences."""

from __future__ import annotations

from typing import Any

from napari_lite.plugins import readers_for


def get_preferred_reader(path: Any) -> None:
    return None


def get_potential_readers(path: Any) -> dict[str, str]:
    return readers_for(path)
