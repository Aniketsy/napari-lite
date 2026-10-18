# napari-lite: own code
"""Layers without features need no pandas.

``layers/utils/_lite_features.py`` stands in for the zero-column feature
table in a process that has not imported pandas; ``layer.features`` still
hands out a real DataFrame when pandas can be imported, and layers created
once pandas is in the process use DataFrames throughout, as napari does.
The checks that depend on pandas being absent from ``sys.modules`` run in
fresh interpreters."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from napari_lite.layers.utils._lite_features import LiteFeatures


def run(code: str) -> dict:
    script = (
        textwrap.dedent(code)
        + '\nimport json, sys\nprint("RESULT " + json.dumps(result))\n'
    )
    proc = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    line = next(
        ln for ln in proc.stdout.splitlines() if ln.startswith('RESULT ')
    )
    return json.loads(line[len('RESULT ') :])


# -- the stand-in against a zero-column DataFrame ---------------------------


@pytest.mark.parametrize('rows', [0, 1, 7])
def test_stand_in_answers_like_a_zero_column_frame(rows) -> None:
    pd = pytest.importorskip('pandas')
    lite = LiteFeatures(rows)
    frame = pd.DataFrame(index=range(rows))
    assert lite.shape == frame.shape
    assert len(lite) == len(frame)
    assert list(lite.columns) == list(frame.columns) == []
    assert lite.columns.to_list() == frame.columns.to_list()
    assert list(lite.index) == list(frame.index)
    assert lite.empty is frame.empty
    assert list(lite) == list(frame)
    assert list(lite.items()) == list(frame.items())
    assert ('x' in lite) is ('x' in frame)
    assert lite.to_dict() == frame.to_dict()
    assert list(lite.itertuples(index=True, name=None)) == list(
        frame.itertuples(index=True, name=None)
    )
    assert repr(lite) == repr(frame)
    with pytest.raises(KeyError):
        lite['x']
    with pytest.raises(ValueError, match='ambiguous'):
        bool(lite)
    if rows:
        assert lite.iloc[0].to_dict() == frame.iloc[0].to_dict()
        assert lite.iloc[-1].to_dict() == frame.iloc[-1].to_dict()
        assert lite.iloc[1:3].shape == frame.iloc[1:3].shape
        assert lite.iloc[np.zeros(4, dtype=int)].shape == (4, 0)
        assert (
            lite.drop(labels=[0], axis=0).shape
            == frame.drop(labels=[0], axis=0).shape
        )
        assert lite.drop(labels=range(1, rows)).reset_index(
            drop=True
        ).shape == (1, 0)
        with pytest.raises(KeyError):
            lite.drop(labels=[rows + 5])
    with pytest.raises(IndexError):
        lite.iloc[rows]


def test_stand_in_becomes_a_frame_when_it_must() -> None:
    pd = pytest.importorskip('pandas')
    lite = LiteFeatures(3)
    lite['x'] = [1, 2, 3]  # a column: pandas from here on
    assert isinstance(lite._df, pd.DataFrame)
    assert lite.shape == (3, 1) and list(lite.columns) == ['x']
    assert lite['x'].to_list() == [1, 2, 3]
    assert lite.to_csv() == pd.DataFrame({'x': [1, 2, 3]}).to_csv()
    other = LiteFeatures(2)
    assert other.sum().empty  # a DataFrame-only method upgrades too


# -- the feature table of the layers, in a process without pandas --------

NO_PANDAS_LAYERS = """
import sys
import numpy as np
from napari_lite.components import ViewerModel
from napari_lite.layers.utils.layer_utils import _FeatureTable

table = _FeatureTable.from_layer(num_data=5)
table.resize(8)
table.remove([0, 1])
table.reorder([5, 4, 3, 2, 1, 0])
table.set_currents({})
assert table.values.shape == (6, 0) and table.defaults.shape == (1, 0)
assert table.properties() == {} and table.choices() == {} and table.currents() == {}

viewer = ViewerModel()
rng = np.random.default_rng(0)
points = viewer.add_points(
    rng.random((20, 3)) * 10, text={'string': {'constant': 'hello'}}, size=3
)
points.add([1.0, 2.0, 3.0])
points.selected_data = {0, 1}
points.remove_selected()
points.get_status((1.0, 2.0, 3.0))
shapes = viewer.add_shapes([np.array([[0, 0], [0, 5], [5, 5]])], shape_type='polygon')
shapes.get_status((1.0, 1.0))
labels = viewer.add_labels(rng.integers(0, 4, (4, 16, 16)).astype(np.int32))
labels.get_status((1.0, 2.0, 3.0))
vectors = viewer.add_vectors(rng.random((10, 2, 3)))
surface = viewer.add_surface((rng.random((4, 3)), np.array([[0, 1, 2], [1, 2, 3]])))
viewer.dims.set_current_step(0, 2)
indexed = viewer.add_points(rng.random((5, 2)), text='{index}')
loaded_before = 'pandas' in sys.modules
assert indexed.text.values.tolist() == ['0', '1', '2', '3', '4']
assert points.properties == {} and points.current_properties == {}
assert len(points._feature_table.values) == len(points.data) == 19

# handing the table out materializes a real DataFrame
features = points.features
import pandas as pd
assert isinstance(features, pd.DataFrame)
assert features.shape == (19, 0)
assert points.features is features
features['x'] = np.arange(19)
assert list(points.features.columns) == ['x']
assert isinstance(points.feature_defaults, pd.DataFrame)
assert points.feature_defaults.shape == (1, 0)  # as napari: in-place edits
points.features = {'x': np.arange(19)}
assert points.feature_defaults.shape == (1, 1)
assert isinstance(points.as_layer_data_tuple()[1]['features'], pd.DataFrame)
points.add([5.0, 5.0, 5.0])
assert points.features.shape == (20, 1)
assert isinstance(shapes.features, pd.DataFrame) and shapes.features.shape == (1, 0)
assert isinstance(labels.features, pd.DataFrame)
result = {'loaded_before': loaded_before}
"""


def test_layers_without_features_do_not_import_pandas() -> None:
    pytest.importorskip('pandas')
    assert run(NO_PANDAS_LAYERS) == {'loaded_before': False}


WITH_PANDAS_FIRST = """
import pandas as pd
import numpy as np
from napari_lite.layers import Points
from napari_lite.layers.utils.layer_utils import _FeatureTable

points = Points(np.zeros((3, 2)))
result = {
    'values': type(points._feature_table.values).__name__,
    'defaults': type(points._feature_table.defaults).__name__,
    'table': type(_FeatureTable.from_layer(num_data=2).values).__name__,
}
"""


def test_with_pandas_in_the_process_the_tables_are_frames() -> None:
    """Exactly napari's behaviour whenever pandas has been imported."""
    pytest.importorskip('pandas')
    assert run(WITH_PANDAS_FIRST) == {
        'values': 'DataFrame',
        'defaults': 'DataFrame',
        'table': 'DataFrame',
    }


NO_PANDAS_INSTALLED = """
import sys
sys.modules['pandas'] = None  # a plain install: pandas is not there
import numpy as np
from napari_lite.layers import Points, Labels, Tracks
from napari_lite.layers.utils._lite_features import LiteFeatures

points = Points(np.zeros((4, 2)), text={'string': {'constant': 'hello'}})
points.add([1.0, 1.0])
labels = Labels(np.zeros((8, 8), dtype=np.int32))
labels.fill((2, 2), 3)
assert isinstance(points.features, LiteFeatures)
assert points.features.shape == (5, 0)
errors = {}
try:
    points.features['x'] = np.arange(5)
except ImportError as error:
    errors['assign'] = str(error)
try:
    Points(np.zeros((2, 2)), features={'x': [1, 2]})
except ImportError as error:
    errors['create'] = str(error)
try:
    Tracks(np.array([[0, 0, 1.0, 2.0], [0, 1, 1.5, 2.5]]))
except ImportError as error:
    errors['tracks'] = str(error)
result = errors
"""


def test_plain_install_without_pandas() -> None:
    errors = run(NO_PANDAS_INSTALLED)
    assert set(errors) == {'assign', 'create', 'tracks'}
    for message in errors.values():
        assert 'napari-lite[features]' in message
