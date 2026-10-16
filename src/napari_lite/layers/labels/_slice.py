import numpy.typing as npt

from napari_lite.layers._scalar_field._slice import _ScalarFieldSliceRequest
from napari_lite.layers.base._base_constants import BaseProjectionMode
from napari_lite.types import ArrayLike


class _LabelsSliceRequest(_ScalarFieldSliceRequest):
    @staticmethod
    def _project_slice(
        data: ArrayLike, axis: tuple[int, ...], mode: BaseProjectionMode
    ) -> npt.NDArray:
        """Project a thick slice along axis based on mode."""
        raise NotImplementedError
