# napari-lite: own code
"""Application settings: the fields the copied napari core reads.

Mirrors ``napari.settings._application`` (names, types, defaults and
constraints) for those fields only.  Nothing is read from or written to
disk; a value set here lives for the session.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from napari_lite.settings._constants import (
    BrushSizeOnMouseModifiers,
    LabelDTypes,
    LoopMode,
)
from napari_lite.utils.camera_orientations import (
    DEFAULT_ORIENTATION_TYPED,
    DepthAxisOrientation,
    HorizontalAxisOrientation,
    VerticalAxisOrientation,
)
from napari_lite.utils.events import Event
from napari_lite.utils.events.custom_types import NotEqual
from napari_lite.utils.events.evented_model import EventedModel
from napari_lite.utils.notifications import NotificationSeverity

# same limits as napari: a 2x2 grid breaks above ~1300 px of spacing
MAX_GRID_SPACING = 1500

GridStride = Annotated[int, NotEqual(0)]
GridWidth = Annotated[int, Field(ge=-1), NotEqual(0)]
GridHeight = Annotated[int, Field(ge=-1), NotEqual(0)]
GridSpacing = Annotated[float, Field(ge=0, le=MAX_GRID_SPACING)]


class ApplicationSettings(EventedModel):
    ipy_interactive: bool = True
    gui_notification_level: NotificationSeverity = NotificationSeverity.INFO
    console_notification_level: NotificationSeverity = (
        NotificationSeverity.NONE
    )
    playback_fps: int = 10
    playback_mode: LoopMode = LoopMode.LOOP
    depth_axis_orientation: DepthAxisOrientation = DEFAULT_ORIENTATION_TYPED[0]
    vertical_axis_orientation: VerticalAxisOrientation = (
        DEFAULT_ORIENTATION_TYPED[1]
    )
    horizontal_axis_orientation: HorizontalAxisOrientation = (
        DEFAULT_ORIENTATION_TYPED[2]
    )
    synced_camera: bool = True
    grid_stride: GridStride = 1
    grid_width: GridWidth = -1
    grid_height: GridHeight = -1
    grid_spacing: GridSpacing = 0.0
    float_display_precision: int = Field(3, ge=1, le=10)
    hold_button_delay: float = 0.5
    brush_size_on_mouse_move_modifiers: BrushSizeOnMouseModifiers = (
        BrushSizeOnMouseModifiers.ALT
    )
    new_labels_dtype: LabelDTypes = LabelDTypes.uint8
    plugin_widget_positions: dict[str, str] = Field(default_factory=dict)

    def _connect_events(self) -> None:
        """Push the two settings that live in module globals (same as napari)."""
        self.events.brush_size_on_mouse_move_modifiers.connect(
            brush_size_on_mouse_move_modifiers_callback
        )
        self.events.brush_size_on_mouse_move_modifiers(
            value=self.brush_size_on_mouse_move_modifiers
        )
        self.events.float_display_precision.connect(
            float_display_precision_callback
        )
        self.events.float_display_precision(value=self.float_display_precision)


def brush_size_on_mouse_move_modifiers_callback(event: Event) -> None:
    from napari_lite.layers.labels._labels_mouse_bindings import (
        change_brush_size_on_mouse_move_modifiers,
    )

    change_brush_size_on_mouse_move_modifiers(event.value.split('+'))


def float_display_precision_callback(event: Event) -> None:
    from napari_lite.utils import status_messages

    status_messages.DEFAULT_PRECISION = event.value
