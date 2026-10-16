"""Vispy zoom box overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from napari_lite._vispy.overlays.base import ViewerOverlayMixin, VispyCanvasOverlay
from napari_lite._vispy.visuals.interaction_box import InteractionBox
from napari_lite.settings import get_settings

if TYPE_CHECKING:
    from napari_lite.components.overlays import ZoomOverlay
    from napari_lite.utils.events import Event


class VispyZoomOverlay(ViewerOverlayMixin, VispyCanvasOverlay):
    """Zoom box overlay.."""

    overlay: ZoomOverlay
    node: InteractionBox

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(node=InteractionBox(), **kwargs)

        self.overlay.events.position.connect(self._on_position_change)

        self.reset()

    def _on_position_change(self, event: Optional[Event] = None) -> None:
        """Change position."""
        settings = get_settings()
        self.node._highlight_width = (
            settings.appearance.highlight.highlight_thickness
        )
        self.node._edge_color = tuple(  # pyrefly: ignore [bad-assignment]
            settings.appearance.highlight.highlight_color
        )

        top_left, bot_right = self.overlay.position
        self.node.set_data(
            # invert axes for vispy
            top_left[::-1],
            bot_right[::-1],
            handles=False,
            selected=None,
        )

    def reset(self) -> None:
        """Reset the overlay."""
        super().reset()
