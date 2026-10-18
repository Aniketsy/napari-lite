# napari-lite: own code
"""The built-in reader behind ``viewer.open`` and the built-in samples;
no writers, and clear errors everywhere else."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def viewer():
    from napari_lite.components import ViewerModel

    return ViewerModel()


def test_open_png_npy_npz(viewer, tmp_path) -> None:
    import imageio.v3 as iio

    png = tmp_path / 'photo.png'
    iio.imwrite(png, np.full((48, 64, 3), 7, dtype=np.uint8))
    npy = tmp_path / 'stack.npy'
    np.save(npy, np.zeros((3, 8, 8), dtype=np.uint16))
    npz = tmp_path / 'pair.npz'
    np.savez(npz, a=np.ones((4, 4)), b=np.zeros((2, 5)))

    layers = viewer.open([str(png), str(npy), str(npz)])

    names = [layer.name for layer in layers]
    assert names == ['photo', 'stack', 'pair[a]', 'pair[b]']
    assert layers[0].rgb and layers[0].data.shape == (48, 64, 3)
    assert layers[1].data.shape == (3, 8, 8)
    assert layers[3].data.shape == (2, 5)
    assert layers[0].source.path == str(png)
    assert layers[0].source.reader_plugin == 'napari-lite'


def test_open_tiff(viewer, tmp_path) -> None:
    import imageio.v3 as iio  # writes with tifffile or Pillow

    data = np.arange(64, dtype=np.uint8).reshape(8, 8)
    tif = tmp_path / 'cells.tif'
    iio.imwrite(tif, data)
    (layer,) = viewer.open(str(tif))
    assert layer.name == 'cells'
    np.testing.assert_array_equal(layer.data, data)


def test_open_stack_and_layer_type(viewer, tmp_path) -> None:
    from napari_lite.layers import Labels

    paths = []
    for i in range(3):
        path = tmp_path / f'slice{i}.npy'
        np.save(path, np.full((5, 6), i, dtype=np.int32))
        paths.append(str(path))

    (stacked,) = viewer.open(paths, stack=True)
    assert stacked.data.shape == (3, 5, 6)
    assert stacked.name == 'slice0'
    assert stacked.data[2, 0, 0] == 2

    (labels,) = viewer.open(paths[0], layer_type='labels')
    assert isinstance(labels, Labels)

    other = tmp_path / 'other.npy'
    np.save(other, np.zeros((2, 2)))
    with pytest.raises(ValueError, match='different shapes'):
        viewer.open([paths[0], str(other)], stack=True)


def test_open_unsupported_suffix_says_what_is_read(viewer, tmp_path) -> None:
    from napari_lite.errors.reader_errors import NoAvailableReaderError

    path = tmp_path / 'notes.txt'
    path.write_text('hello', encoding='utf-8')
    with pytest.raises(NoAvailableReaderError, match='napari-lite reads png'):
        viewer.open(str(path))
    # the error of before, for code that caught it
    with pytest.raises(NotImplementedError):
        viewer.open(str(path))


def test_open_plugin_names(viewer, tmp_path) -> None:
    npy = tmp_path / 'a.npy'
    np.save(npy, np.zeros((2, 2)))
    with pytest.raises(ValueError, match='no plugins'):
        viewer.open(str(npy), plugin='napari-ome-zarr')
    # napari's built-in reader is called 'napari': accepted, one-line swap
    assert len(viewer.open(str(npy), plugin='napari')) == 1
    assert len(viewer.open(str(npy), plugin='napari-lite')) == 1


def test_sample_blobs_offline(viewer) -> None:
    (layer,) = viewer.open_sample('napari-lite', 'blobs')
    assert layer.name == 'blobs'
    assert layer.data.shape == (32, 128, 128)
    assert layer.data.dtype == np.float32
    assert layer.data.min() >= 0 and layer.data.max() == 1
    assert layer.source.sample == ('napari-lite', 'blobs')


def test_sample_names_and_errors(viewer) -> None:
    from napari_lite.plugins import available_samples

    pairs = available_samples()
    names = {name for _plugin, name in pairs}
    assert all(plugin == 'napari-lite' for plugin, _name in pairs)
    assert {'astronaut', 'camera', 'cat', 'coins', 'stent', 'blobs'} <= names
    with pytest.raises(KeyError, match='Available samples include'):
        viewer.open_sample('napari-lite', 'cells3d')
    with pytest.raises(KeyError, match='some-plugin'):
        viewer.open_sample('some-plugin', 'astronaut')


def test_sample_from_imageio(viewer) -> None:
    """astronaut is one of imageio's standard images, downloaded once;
    skipped without network.  napari's own name for it works too."""
    try:
        (layer,) = viewer.open_sample('napari', 'astronaut')
    except OSError as exc:
        pytest.skip(f'imageio could not fetch the sample: {exc}')
    assert layer.rgb
    assert layer.data.shape == (512, 512, 3)
    assert layer.source.sample == ('napari', 'astronaut')


def test_save_raises(viewer, tmp_path) -> None:
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
