# napari-lite: own code
"""Experimental settings read by the copied layers and overlays."""

from __future__ import annotations

from pydantic import Field

from napari_lite.utils.colormap_backend import (
    ColormapBackend,
    set_backend as set_colormap_backend,
)
from napari_lite.utils.events import Event
from napari_lite.utils.events.evented_model import EventedModel
from napari_lite.utils.triangulation_backend import (
    TriangulationBackend,
    set_backend as set_triangulation_backend,
)


class ExperimentalSettings(EventedModel):
    async_: bool = False
    rdp_epsilon: float = Field(0.5, ge=0)
    lasso_vertex_distance: int = Field(10, ge=1, le=50)
    completion_radius: int = -1
    triangulation_backend: TriangulationBackend = (
        TriangulationBackend.fastest_available
    )
    colormap_backend: ColormapBackend = ColormapBackend.fastest_available

    def _connect_events(self) -> None:
        """Keep the backend modules in sync with the two backend fields."""
        self.events.triangulation_backend.connect(
            _update_triangulation_backend
        )
        self.events.triangulation_backend(value=self.triangulation_backend)
        self.events.colormap_backend.connect(_update_colormap_backend)
        self.events.colormap_backend(value=self.colormap_backend)


def _update_triangulation_backend(event: Event) -> None:
    set_triangulation_backend(event.source.triangulation_backend)


def _update_colormap_backend(event: Event) -> None:
    set_colormap_backend(event.source.colormap_backend)
