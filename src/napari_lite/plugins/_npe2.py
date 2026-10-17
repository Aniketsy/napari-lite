# napari-lite: own code
"""npe2 lookups used by ``ViewerModel.open`` and ``open_sample``.

Both raise: napari-lite has no plugins.  Raising here (rather than
returning "no readers found") gives the user the reason and the way out.
"""

from __future__ import annotations

from typing import Any

from napari_lite.plugins import NO_SAMPLES, no_plugins, no_readers


def get_readers(path: Any) -> dict[str, str]:
    raise no_readers(path)


def get_sample_data(plugin: str, sample: str) -> tuple[None, list]:
    raise no_plugins(NO_SAMPLES, f'{plugin}:{sample}')
