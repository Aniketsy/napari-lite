# napari-lite: own code
"""Copy a layer's scale and transforms to the clipboard as JSON and apply
them to the selected layers: the layer list's copy/paste shortcuts and
the "Copy scale and transforms" entries of its context menu.

The JSON format and the rules that cut or pad values to a layer's number
of dimensions are napari's (``_qt/_qapp_model/qactions/
_layerlist_context.py``), without the app-model Action wrappers.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
from qtpy.QtCore import QMimeData
from qtpy.QtWidgets import QApplication

from napari_lite.utils.notifications import show_warning

if TYPE_CHECKING:
    from napari_lite.components import LayerList
    from napari_lite.layers import Layer

__all__ = [
    'SPATIAL_KEYS',
    'copy_to_clipboard',
    'is_valid_spatial_in_clipboard',
    'paste_from_clipboard',
]

SPATIAL_KEYS = ('affine', 'rotate', 'scale', 'shear', 'translate', 'units')
_DEFAULT_1D = {'scale': 1.0, 'translate': 0.0, 'units': 'px'}


def _to_json(value: Any) -> Any:
    """Arrays become lists, units (and anything else) strings."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _to_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_json(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _value(layer: Layer, key: str) -> Any:
    if key == 'affine':
        return layer.affine.affine_matrix
    return getattr(layer, key)


def copy_to_clipboard(
    ll: LayerList, keys: tuple[str, ...] = SPATIAL_KEYS
) -> None:
    """Put ``keys`` of the active layer in the clipboard as JSON."""
    layer = ll.selection.active
    if layer is None:
        return
    clip = QApplication.clipboard()
    if clip is None:
        show_warning('Cannot access clipboard')
        return
    mime = QMimeData()
    mime.setText(json.dumps({k: _to_json(_value(layer, k)) for k in keys}))
    clip.setMimeData(mime)


def _from_clipboard() -> dict | None:
    clip = QApplication.clipboard()
    mime = clip.mimeData() if clip is not None else None
    if mime is None:
        return None
    loaded = json.loads(mime.text())
    return loaded if isinstance(loaded, dict) else None


def is_valid_spatial_in_clipboard() -> bool:
    """Whether the clipboard holds JSON with spatial keys only."""
    try:
        loaded = _from_clipboard()
    except json.JSONDecodeError:
        return False
    return loaded is not None and set(loaded).issubset(SPATIAL_KEYS)


def _fit(key: str, value: Any, ndim: int) -> Any:
    """Cut or pad a clipboard value to ``ndim`` dimensions."""
    if key == 'units':
        return ((_DEFAULT_1D['units'],) * ndim + tuple(value))[-ndim:]
    if isinstance(value, list):
        value = np.array(value)
    if key == 'shear':
        n = ndim * (ndim - 1) // 2
        out = np.zeros(n)
        out[-value.size :] = value[-n:]
        return out
    if key == 'affine':
        if value.shape[0] >= ndim + 1:
            return value[-(ndim + 1) :, -(ndim + 1) :]
        out = np.eye(ndim + 1)
        out[-value.shape[0] :, -value.shape[1] :] = value
        return out
    if isinstance(value, np.ndarray):
        if value.ndim == 1:
            if len(value) >= ndim:
                return value[-ndim:]
            padding = (_DEFAULT_1D[key],) * (ndim - len(value))
            return np.array(padding + tuple(value))
        if value.ndim == 2:
            if value.shape[0] >= ndim:
                return value[-ndim:, -ndim:]
            out = np.eye(ndim)
            out[-value.shape[1] :, -value.shape[0] :] = value
            return out
    return value


def paste_from_clipboard(ll: LayerList) -> None:
    """Apply the spatial values in the clipboard to the selected layers."""
    try:
        loaded = _from_clipboard()
    except json.JSONDecodeError:
        show_warning('Cannot parse clipboard data')
        return
    if loaded is None:
        show_warning('Cannot access clipboard')
        return
    for layer in ll.selection:
        with layer._block_refresh():
            for key, value in loaded.items():
                setattr(layer, key, _fit(key, value, layer.ndim))
    for layer in ll.selection:
        layer.refresh(data_displayed=False)
