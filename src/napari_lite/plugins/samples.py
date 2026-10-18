# napari-lite: own code
"""The built-in samples: ``viewer.open_sample('napari-lite', name)``.

Most are imageio's standard images (the scikit-image pictures behind
napari's own samples), which imageio downloads once, under a megabyte
each and 4 MB for the ``stent`` volume, into its cache.  ``blobs`` is
computed, so it works offline.  ``SAMPLES`` maps the names to the samples;
``napari_lite.plugins.available_samples`` lists them as napari does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

LayerData = tuple[Any, dict[str, Any], str]


def blobs(
    shape: tuple[int, ...] = (32, 128, 128), count: int = 24, seed: int = 0
) -> npt.NDArray[np.float32]:
    """A volume of smooth blobs, float32 between 0 and 1, computed."""
    import numpy as np

    rng = np.random.default_rng(seed)
    grid = np.indices(shape, dtype=np.float32)
    size = np.array(shape, dtype=np.float32)
    centres = rng.uniform(0.1, 0.9, (count, len(shape))) * size
    radii = rng.uniform(0.06, 0.16, count) * size.max()
    out = np.zeros(shape, dtype=np.float32)
    for centre, radius in zip(centres, radii, strict=True):
        d2 = sum((axis - c) ** 2 for axis, c in zip(grid, centre, strict=True))
        out += np.exp(-d2 / (2 * radius * radius))
    out /= out.max()
    return out


@dataclass(frozen=True)
class Sample:
    """A built-in sample: an imageio standard image, or computed data."""

    name: str
    description: str
    file: str = ''
    """imageio's file name (``imageio:<file>``); '' for a computed sample."""

    def load(self) -> list[LayerData]:
        """The sample as napari layer data: one image layer."""
        if self.file:
            import imageio.v3 as iio

            data = iio.imread(f'imageio:{self.file}')
        else:
            data = blobs()
        return [(data, {'name': self.name}, 'image')]


_IMAGEIO = [
    ('astronaut', 'astronaut.png', 'the astronaut Eileen Collins, RGB'),
    ('camera', 'camera.png', 'a photographer'),
    ('cat', 'chelsea.png', "Stefan's cat Chelsea, RGB"),
    ('checkerboard', 'checkerboard.png', 'a checkerboard'),
    ('clock', 'clock.png', 'a clock with motion blur'),
    ('coffee', 'coffee.png', 'a cup of coffee, RGB'),
    ('coins', 'coins.png', 'Greek coins from Pompeii'),
    ('horse', 'horse.png', 'the silhouette of a horse'),
    ('hubble_deep_field', 'hubble_deep_field.png', 'the Hubble deep field'),
    ('immunohistochemistry', 'immunohistochemistry.png', 'IHC staining'),
    ('moon', 'moon.png', 'a portion of the surface of the moon'),
    ('page', 'page.png', 'a scanned page of text'),
    ('text', 'text.png', 'handwritten text'),
    ('stent', 'stent.npz', 'a stented abdominal aorta, a CT volume'),
]

SAMPLES: dict[str, Sample] = {
    name: Sample(name, f'{description} (imageio, downloaded once)', file)
    for name, file, description in _IMAGEIO
}
SAMPLES['blobs'] = Sample(
    'blobs', 'smooth blobs, a computed 32x128x128 volume (no download)'
)
