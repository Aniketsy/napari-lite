# napari-lite: own code
"""npe2 lookups used by ``ViewerModel.open`` and ``open_sample``.

Both raise: napari-lite has no plugins.  Raising here (rather than
returning "no readers found") gives the user the reason and the way out.
"""

from __future__ import annotations

from typing import Any

from napari_lite.plugins import NO_READERS, NO_SAMPLES


def get_readers(path: Any) -> dict[str, str]:
    raise NotImplementedError(NO_READERS)


def get_sample_data(plugin: str, sample: str) -> tuple[None, list]:
    raise NotImplementedError(NO_SAMPLES)
