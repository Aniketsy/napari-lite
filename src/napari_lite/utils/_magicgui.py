# napari-lite: own code
"""magicgui return-callbacks and choices: no-ops.

napari registers its layer and data types with magicgui so that a
magicgui widget returning e.g. ``ImageData`` adds a layer to the current
viewer.  napari-lite does not register anything with magicgui (see
``layers/base/base.py`` and ``types.py``); these names exist because the
copied modules import them.
"""

from __future__ import annotations

from typing import Any


def add_layer_to_viewer(*args: Any, **kwargs: Any) -> None:
    return None


def add_layers_to_viewer(*args: Any, **kwargs: Any) -> None:
    return None


def add_layer_data_to_viewer(*args: Any, **kwargs: Any) -> None:
    return None


def add_layer_data_tuples_to_viewer(*args: Any, **kwargs: Any) -> None:
    return None


def add_future_data(*args: Any, **kwargs: Any) -> None:
    return None


def add_worker_data(*args: Any, **kwargs: Any) -> None:
    return None


def get_layers(*args: Any, **kwargs: Any) -> list:
    return []


def get_layers_data(*args: Any, **kwargs: Any) -> list:
    return []
