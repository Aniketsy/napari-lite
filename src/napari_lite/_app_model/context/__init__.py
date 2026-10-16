# napari-lite: own code
"""Context keys for menu enablement: none in napari-lite."""

from __future__ import annotations

from typing import Any


def create_context(obj: Any, *args: Any, **kwargs: Any) -> None:
    """napari-lite has no menus, so no context to drive them."""
    return None


def get_context(obj: Any) -> None:
    return None
