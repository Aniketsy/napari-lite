# napari-lite: own code
"""The features table of a layer without pandas, until a feature is given.

Points, Shapes, Labels, Vectors, Tracks and Surface keep their per-element
features in a pandas DataFrame (``_FeatureTable`` in ``layer_utils.py``).
Most layers never get a feature, yet the table is made for each of them,
which imported pandas (about 530 modules, 63 MB of the install) on the
first such layer.

In a process that has never imported pandas, :class:`LiteFeatures` stands
in for the table while it has no columns.  It answers what the layer code
asks of a zero-column DataFrame (shape, columns, rows, slices, row drops)
and becomes a real DataFrame the moment one is needed: a column is set, a
DataFrame-only method is called, or the layer hands the table out through
``layer.features`` (``_FeatureTable.dataframe``).  Wherever pandas has
already been imported, by the user or by a feature, real DataFrames are
used throughout and nothing here is involved, so the copied napari code and
its tests run unchanged.

pandas is the ``features`` extra.  Without it the stand-in is all there
is: layers without features work, and the first feature raises an
ImportError that names the extra.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from collections.abc import Iterator
from typing import Any

import numpy as np

EXTRA_HINT = (
    'pandas is needed for layer features: pip install "napari-lite[features]"'
)


def pandas() -> Any:
    """The pandas module, or an ImportError that names the extra."""
    try:
        import pandas
    except ImportError as error:
        raise ImportError(EXTRA_HINT) from error
    return pandas


def available() -> bool:
    """Whether pandas can be imported, without importing it."""
    # a None entry in sys.modules is how a blocked package looks
    return (
        sys.modules.get('pandas') is not None
        or importlib.util.find_spec('pandas') is not None
    )


class _Columns(list):
    """The empty column index: a list with pandas' ``to_list``."""

    def to_list(self) -> list:
        return list(self)

    tolist = to_list


class _Row:
    """One row of a zero-column table, as ``iloc[i]`` returns it."""

    def __init__(self, label: int) -> None:
        self.name = label

    def to_dict(self) -> dict:
        return {}

    def keys(self) -> tuple:
        return ()

    def items(self) -> tuple:
        return ()

    def __iter__(self) -> Iterator:
        return iter(())

    def __len__(self) -> int:
        return 0

    def __getitem__(self, key: Any) -> Any:
        raise KeyError(key)


class _ILoc:
    """Positional indexing of a zero-column table."""

    def __init__(self, table: LiteFeatures) -> None:
        self._table = table

    def __getitem__(self, key: Any) -> Any:
        n = len(self._table)
        if isinstance(key, (int, np.integer)):
            i = int(key) + n if key < 0 else int(key)
            if not 0 <= i < n:
                raise IndexError('single positional indexer is out-of-bounds')
            return _Row(i)
        if isinstance(key, slice):
            return LiteFeatures(len(range(*key.indices(n))))
        index = np.asarray(key)
        if index.dtype == bool:
            return LiteFeatures(int(index.sum()))
        if index.size and (index.max() >= n or index.min() < -n):
            raise IndexError('positional indexers are out-of-bounds')
        return LiteFeatures(int(index.size))


class LiteFeatures:
    """A zero-column DataFrame with ``rows`` rows, until it has to be more.

    Attribute and item access that this class does not provide itself goes
    to a real DataFrame, created on first need; from then on every call is
    forwarded to it, so earlier references stay valid.
    """

    __slots__ = ('_df', '_rows')

    def __init__(self, rows: int = 0) -> None:
        self._rows = int(rows)
        self._df: Any = None

    # -- the upgrade -------------------------------------------------------

    def _upgrade(self) -> Any:
        if self._df is None:
            self._df = pandas().DataFrame(index=range(self._rows))
        return self._df

    def __getattr__(self, name: str) -> Any:
        # only reached for names this class does not define
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        return getattr(self._upgrade(), name)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._upgrade()[key] = value

    def __getitem__(self, key: Any) -> Any:
        if self._df is not None:
            return self._df[key]
        if isinstance(key, str):
            raise KeyError(key)
        return self._upgrade()[key]

    # -- what a zero-column frame answers ----------------------------------

    @property
    def shape(self) -> tuple[int, int]:
        return self._df.shape if self._df is not None else (self._rows, 0)

    @property
    def columns(self) -> Any:
        return self._df.columns if self._df is not None else _Columns()

    @property
    def index(self) -> Any:
        return self._df.index if self._df is not None else range(self._rows)

    @property
    def empty(self) -> bool:
        return self._df.empty if self._df is not None else True

    @property
    def iloc(self) -> Any:
        return self._df.iloc if self._df is not None else _ILoc(self)

    def __len__(self) -> int:
        return len(self._df) if self._df is not None else self._rows

    def __iter__(self) -> Iterator:
        return iter(self._df) if self._df is not None else iter(())

    def __contains__(self, key: Any) -> bool:
        return key in self._df if self._df is not None else False

    def __bool__(self) -> bool:
        raise ValueError(
            'The truth value of a DataFrame is ambiguous. Use a.empty, '
            'a.bool(), a.item(), a.any() or a.all().'
        )

    def keys(self) -> Any:
        return self._df.keys() if self._df is not None else _Columns()

    def items(self) -> Iterator:
        return self._df.items() if self._df is not None else iter(())

    def itertuples(
        self, index: bool = True, name: str | None = 'Pandas'
    ) -> Any:
        if self._df is not None or name is not None:
            return self._upgrade().itertuples(index=index, name=name)
        if index:
            return ((i,) for i in range(self._rows))
        return (() for _ in range(self._rows))

    def to_dict(self, *args: Any, **kwargs: Any) -> Any:
        if self._df is not None or args or kwargs:
            return self._upgrade().to_dict(*args, **kwargs)
        return {}

    def copy(self, deep: bool = True) -> Any:
        if self._df is not None:
            return self._df.copy(deep=deep)
        return LiteFeatures(self._rows)

    def drop(
        self,
        labels: Any = None,
        *,
        axis: Any = 0,
        index: Any = None,
        columns: Any = None,
        inplace: bool = False,
        errors: str = 'raise',
    ) -> Any:
        if (
            self._df is not None
            or columns is not None
            or axis not in (0, 'index')
            or inplace
        ):
            return self._upgrade().drop(
                labels=labels,
                axis=axis,
                index=index,
                columns=columns,
                inplace=inplace,
                errors=errors,
            )
        labels = index if labels is None else labels
        if isinstance(labels, (int, np.integer)):
            labels = [labels]
        wanted = np.asarray(list(labels), dtype=np.intp).ravel()
        if (
            errors == 'raise'
            and wanted.size
            and (wanted.min() < 0 or wanted.max() >= self._rows)
        ):
            missing = wanted[(wanted < 0) | (wanted >= self._rows)]
            raise KeyError(f'{missing.tolist()} not found in axis')
        inside = wanted[(wanted >= 0) & (wanted < self._rows)]
        return LiteFeatures(self._rows - np.unique(inside).size)

    def reset_index(self, drop: bool = False, **kwargs: Any) -> Any:
        if self._df is not None or not drop or kwargs:
            return self._upgrade().reset_index(drop=drop, **kwargs)
        return LiteFeatures(self._rows)

    def __repr__(self) -> str:
        if self._df is not None:
            return repr(self._df)
        return (
            f'Empty DataFrame\nColumns: []\nIndex: {list(range(self._rows))}'
        )

    def __copy__(self) -> LiteFeatures:
        new = LiteFeatures(self._rows)
        new._df = self._df
        return new

    def __deepcopy__(self, memo: dict) -> LiteFeatures:
        new = LiteFeatures(self._rows)
        if self._df is not None:
            new._df = copy.deepcopy(self._df, memo)
        return new


# -- the hooks the copied layer_utils.py calls ---------------------------------


def unwrap(table: Any) -> Any:
    """A stand-in that has become a DataFrame is that DataFrame."""
    if isinstance(table, LiteFeatures) and table._df is not None:
        return table._df
    return table


def use_lite(features: Any) -> bool:
    """Whether ``_validate_features`` should answer with a stand-in: the
    input has no columns and pandas has not been imported by anyone."""
    if isinstance(features, LiteFeatures):
        return True
    if sys.modules.get('pandas') is not None:
        return False
    return features is None or (
        isinstance(features, dict) and len(features) == 0
    )


def lite_values(features: Any, num_data: int | None) -> LiteFeatures:
    """The stand-in ``_validate_features`` returns: ``num_data`` rows, or
    the rows of the given stand-in, or none."""
    if num_data is not None:
        return LiteFeatures(num_data)
    if isinstance(features, LiteFeatures):
        return LiteFeatures(len(features))
    return LiteFeatures(0)


def lite_defaults(defaults: Any) -> LiteFeatures:
    """The one-row stand-in ``_validate_feature_defaults`` returns for a
    zero-column table; defaults for columns that do not exist are an
    error, as in napari."""
    if defaults is None or len(defaults) == 0:
        return LiteFeatures(1)
    raise ValueError(
        'Feature defaults contain some extra columns not in feature values: '
        f'{set(defaults.keys())}'
    )


def concat(values: Any, to_append: Any) -> Any:
    """``pd.concat([values, to_append], ignore_index=True)``, without pandas
    while both are stand-ins."""
    values, to_append = unwrap(values), unwrap(to_append)
    if isinstance(values, LiteFeatures) and isinstance(
        to_append, LiteFeatures
    ):
        return LiteFeatures(len(values) + len(to_append))
    frames = [
        frame._upgrade() if isinstance(frame, LiteFeatures) else frame
        for frame in (values, to_append)
    ]
    return pandas().concat(frames, ignore_index=True)


def materialize(table: Any) -> Any:
    """The values of a ``_FeatureTable`` as a real DataFrame when pandas can
    be imported, kept in the table from then on; the stand-in otherwise."""
    values = table._values
    if isinstance(values, LiteFeatures):
        if values._df is None and not available():
            return values
        table._values = values._upgrade()
    defaults = table._defaults
    if isinstance(defaults, LiteFeatures):
        table._defaults = defaults._upgrade()
    return table._values


def materialize_defaults(table: Any) -> Any:
    """The defaults of a ``_FeatureTable``, see :func:`materialize`."""
    materialize(table)
    return table._defaults


def to_dataframe(features: Any) -> Any:
    """``features_to_pandas_dataframe``: a DataFrame when pandas can be
    imported, the stand-in otherwise."""
    if isinstance(features, LiteFeatures) and (
        features._df is not None or available()
    ):
        return features._upgrade()
    return features


__all__ = [
    'EXTRA_HINT',
    'LiteFeatures',
    'available',
    'concat',
    'lite_defaults',
    'lite_values',
    'materialize',
    'materialize_defaults',
    'pandas',
    'to_dataframe',
    'unwrap',
    'use_lite',
]
