# napari-lite: own code
"""The vispy renderer's canvas in a notebook (issue 5, docs/backends.md).

``VispyFrameWidget`` is a jupyter_rfb widget: it streams the frames of
the renderer's off-screen canvas to the browser and hands the browser's
pointer, wheel and key events back to that canvas, so napari's mouse and
key bindings work as in a window.

vispy has a jupyter_rfb backend of its own, but it needs a GL context
from glfw or from a hidden Qt canvas, which a server often cannot give
and a Qt canvas that was never shown does not have.  This widget draws
with the same off-screen canvas as the headless viewer instead: vispy's
egl or osmesa application on Linux, a Qt widget kept off the screen
elsewhere.  Frames are drawn at the widget's CSS size.

Everything the canvas does happens on the thread that made it: JupyterLab
hands widget messages to a kernel subshell, a thread of its own, and a GL
context used from another thread fails (Qt ends the process).  Events
and draws that arrive elsewhere are handed to that thread's loop
(``utils/_owner_thread.py``).  jupyter_rfb schedules its draws on
asyncio, which waits while IPython runs Qt's event loop (``%gui qt``);
then a draw is scheduled through Qt as well.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jupyter_rfb import RemoteFrameBuffer
from vispy.util import keys

from napari_lite.utils._owner_thread import OwnerThread, ipython_runs_qt

if TYPE_CHECKING:
    import numpy as np

    from napari_lite._vispy.backend import VispyBackend

__all__ = ['CSS_CURSORS', 'VispyFrameWidget']

# browser key names (``KeyboardEvent.key``) that vispy names differently
_KEY_NAMES = {
    'ArrowUp': 'Up',
    'ArrowDown': 'Down',
    'ArrowLeft': 'Left',
    'ArrowRight': 'Right',
    ' ': 'Space',
    'Esc': 'Escape',
    'Del': 'Delete',
    'Return': 'Enter',
}

# napari's cursor styles as CSS cursors; the brush circle of 'circle' is
# drawn by napari itself, so the browser shows no cursor over it
CSS_CURSORS = {
    'standard': 'default',
    'cross': 'crosshair',
    'crosshair': 'crosshair',
    'forbidden': 'not-allowed',
    'pointing': 'pointer',
    'square': 'crosshair',
    'circle': 'none',
    'circle_frozen': 'default',
}


class _BrowserEvent:
    """What napari's handlers ask of the toolkit event behind a vispy
    event (``event.native``): whether a key repeats (jupyter_rfb drops
    held-down repeats in the browser) and whether the wheel is inverted
    (browsers report the scroll as the user sees it)."""

    __slots__ = ('event',)

    def __init__(self, event: dict[str, Any]) -> None:
        self.event = event

    def isAutoRepeat(self) -> bool:  # Qt's name for it
        return False

    def inverted(self) -> bool:
        return False


def _key(name: str) -> keys.Key:
    """vispy's key for a browser key name: its constant for the named keys
    ('Shift', 'ArrowUp', 'Enter', 'F5', ...), else a key with that text."""
    name = _KEY_NAMES.get(name, name)
    if len(name) > 1:
        constant = getattr(keys, name.upper(), None)
        if isinstance(constant, keys.Key):
            return constant
    return keys.Key(name)


def _modifiers(event: dict[str, Any]) -> tuple[keys.Key, ...]:
    return tuple(
        getattr(keys, name.upper())
        for name in event.get('modifiers', ())
        if isinstance(getattr(keys, name.upper(), None), keys.Key)
    )


class VispyFrameWidget(RemoteFrameBuffer):
    """jupyter_rfb's widget for a ``VispyBackend`` made for the notebook.

    Parameters
    ----------
    backend : VispyBackend
        The renderer whose off-screen canvas this widget shows.
    """

    def __init__(self, backend: VispyBackend) -> None:
        super().__init__()
        self._backend = backend
        self._owner = OwnerThread()
        self._buttons: list[int] = []
        self._drawing = False
        self._qt_draw_pending = False
        width, height = backend.canvas._scene_canvas.size
        self.css_width = f'{width}px'
        self.css_height = f'{height}px'

    # frames

    def scene_changed(self) -> None:
        """The canvas has something new to show: ask the browser for a
        frame.  Changes made while a frame is drawn are in that frame."""
        if not self._drawing:
            self.request_draw()

    def request_draw(self) -> None:
        """jupyter_rfb's request for a draw; on the canvas's thread while
        IPython runs Qt's loop, also scheduled through Qt (asyncio, where
        jupyter_rfb schedules it, waits for the next kernel message)."""
        super().request_draw()
        if (
            not self._qt_draw_pending
            and self._owner.is_current
            and ipython_runs_qt()
        ):
            from qtpy.QtCore import QTimer

            self._qt_draw_pending = True
            QTimer.singleShot(0, self._qt_draw)

    def _qt_draw(self) -> None:
        self._qt_draw_pending = False
        # jupyter_rfb's own step: draws if one was asked for, the browser
        # shows the widget and not too many frames are on their way
        maybe_draw = getattr(self, '_rfb_maybe_draw', None)
        if maybe_draw is not None:
            maybe_draw()
        else:
            self._draw_and_send()

    def get_frame(self) -> np.ndarray | None:
        """The canvas drawn now, called by jupyter_rfb when the browser is
        ready for the next frame.  Asked on another thread, the canvas's
        own thread draws it and sends it a moment later."""
        if not self._owner.is_current:
            self._owner.call(self._draw_and_send)
            return None
        return self._draw()

    def _draw(self) -> np.ndarray | None:
        width, height = self._backend.canvas._scene_canvas.size
        if width <= 1 or height <= 1:
            return None
        self._drawing = True
        try:
            return self._backend.capture()
        finally:
            self._drawing = False

    def _draw_and_send(self) -> None:
        with self._output_context:  # errors show in the notebook
            array = self._draw()
            if array is not None:
                self.send_frame(array)

    # events

    def handle_event(self, event: dict[str, Any]) -> None:
        """A browser event, as jupyter_rfb delivers it, into the canvas,
        on the canvas's own thread."""
        if self._owner.is_current:
            self._handle(event)
        else:
            self._owner.call(self._handle_with_output, event)

    def _handle_with_output(self, event: dict[str, Any]) -> None:
        with self._output_context:  # errors show in the notebook
            self._handle(event)

    def _handle(self, event: dict[str, Any]) -> None:
        kind = event.get('type') or event.get('event_type')
        scene_canvas = self._backend.canvas._scene_canvas
        viewer = self._backend.viewer
        if kind == 'resize':
            width, height = int(event['width']), int(event['height'])
            if width > 1 and height > 1:
                # jupyter_rfb asks for a frame at the new size by itself
                scene_canvas.size = (width, height)
        elif kind == 'pointer_enter':
            # what the Qt canvas does when the mouse enters and leaves
            viewer.status = 'Ready'
            viewer.mouse_over_canvas = True
        elif kind == 'pointer_leave':
            viewer.status = ''
            viewer.mouse_over_canvas = False
        elif kind in ('pointer_down', 'pointer_up', 'pointer_move'):
            self._pointer(kind, event)
        elif kind == 'double_click':
            backend = scene_canvas._backend
            # a vispy backend without double clicks of its own finds them
            # in the presses; this one would count them twice
            if getattr(backend, '_double_click_supported', False):
                backend._vispy_mouse_double_click(**self._mouse(event))
        elif kind == 'wheel':
            # about 100 browser pixels per wheel notch; vispy counts notches
            scene_canvas.events.mouse_wheel(
                delta=(event['dx'] / 100, -event['dy'] / 100),
                **self._mouse(event, with_button=False),
            )
        elif kind in ('key_down', 'key_up'):
            emitter = (
                scene_canvas.events.key_press
                if kind == 'key_down'
                else scene_canvas.events.key_release
            )
            name = event['key']
            emitter(
                native=_BrowserEvent(event),
                key=_key(name),
                text=name if len(name) == 1 else '',
                modifiers=_modifiers(event),
            )

    def _mouse(
        self, event: dict[str, Any], *, with_button: bool = True
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            'native': _BrowserEvent(event),
            'pos': (event['x'], event['y']),
            'buttons': list(self._buttons),
            'modifiers': _modifiers(event),
        }
        if with_button:
            fields['button'] = event.get('button', 0)
        return fields

    def _pointer(self, kind: str, event: dict[str, Any]) -> None:
        backend = self._backend.canvas._scene_canvas._backend
        button = event.get('button', 0)
        if kind == 'pointer_down':
            if button not in self._buttons:
                self._buttons.append(button)
            backend._vispy_mouse_press(**self._mouse(event))
        elif kind == 'pointer_up':
            if button in self._buttons:
                self._buttons.remove(button)
            backend._vispy_mouse_release(**self._mouse(event))
        else:
            backend._vispy_mouse_move(**self._mouse(event))
