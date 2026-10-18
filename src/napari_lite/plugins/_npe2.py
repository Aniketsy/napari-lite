# napari-lite: own code
"""npe2 lookups used by ``ViewerModel.open`` and ``open_sample``, answered
by the built-in reader and the built-in samples."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from napari_lite.plugins import READER, no_readers, readers_for


def get_readers(path: Any) -> dict[str, str]:
    """The readers of ``path``: the built-in one, or an error saying what
    napari-lite reads.  Raising here, rather than returning no readers,
    gives the user the reason and the way out."""
    readers = readers_for(path)
    if not readers:
        raise no_readers(path)
    return readers


def get_sample_data(
    plugin: str, sample: str
) -> tuple[Callable[[], list] | None, list[tuple[str, str]]]:
    """The loader of ``sample`` when ``plugin`` is napari-lite (or 'napari',
    for scripts written for napari's built-in samples), and the available
    ``(plugin, sample)`` pairs, as napari's ``open_sample`` expects."""
    from napari_lite.plugins import available_samples
    from napari_lite.plugins.samples import SAMPLES

    available = list(available_samples())
    if plugin in (READER, 'napari') and sample in SAMPLES:
        return SAMPLES[sample].load, available
    return None, available
