# napari-lite: own code
"""No readers, writers or samples: clear errors instead."""

from __future__ import annotations

import numpy as np
import pytest


def test_open_raises(tmp_path) -> None:
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    path = tmp_path / 'image.tif'
    path.write_bytes(b'')
    with pytest.raises(NotImplementedError, match='no file readers'):
        viewer.open(str(path))


def test_open_sample_raises() -> None:
    from napari_lite.components import ViewerModel

    with pytest.raises(NotImplementedError, match='no sample data'):
        ViewerModel().open_sample('napari', 'astronaut')


def test_save_raises(tmp_path) -> None:
    from napari_lite.components import ViewerModel

    viewer = ViewerModel()
    layer = viewer.add_image(np.zeros((4, 4)))
    with pytest.raises(NotImplementedError, match='no file writers'):
        layer.save(str(tmp_path / 'out.tif'))
    with pytest.raises(NotImplementedError, match='no file writers'):
        viewer.layers.save(str(tmp_path / 'out.tif'))


def test_layer_source_without_plugin_manager() -> None:
    from napari_lite.layers import Points
    from napari_lite.layers._source import layer_source

    with layer_source(path='some_path', reader_plugin='my-reader'):
        points = Points()
    assert points.source.reader_plugin == 'my-reader'
    assert points._get_source_info()['plugin'] == 'my-reader'
