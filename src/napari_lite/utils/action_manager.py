# napari-lite: own code
"""Actions and their shortcuts, without app-model.

napari's ``ActionManager`` connects named actions to shortcuts, buttons,
tooltips and menus, and runs commands through app-model's dependency
injection.  napari-lite has no menus and no app-model, so this is the
same public surface (``register_action``, ``bind_shortcut``,
``unbind_shortcut``, ``bind_button``, ``trigger`` and the private
helpers the copied key-binding code calls) on a plain dict.

A registered command receives the keymap provider it was registered for
(the viewer, or the layer in focus) as its only argument, exactly as a
``@viewer.bind_key`` function does.  ``trigger(name)`` with no argument
looks the provider up through ``napari_lite.viewer.current_viewer()``.
"""

from __future__ import annotations

import inspect
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from napari_lite.utils.events import EmitterGroup
from napari_lite.utils.interactions import Shortcut

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Protocol

    from napari_lite.utils._keys import KeyBinding

    from napari_lite.utils.events import Event
    from napari_lite.utils.key_bindings import KeymapProvider

    class SignalInstance(Protocol):
        def connect(self, callback: Callable, /) -> object: ...

    class Button(Protocol):
        clicked: SignalInstance

        def setToolTip(self, text: str, /) -> None: ...


@dataclass
class Action:
    command: Callable
    description: str
    keymapprovider: type[KeymapProvider] | None  # subclass, or None if unbound
    repeatable: bool = False

    @property
    def injected(self) -> Callable:
        """The command itself: napari-lite has no dependency injection.

        The keymap handler binds this as a method of the provider instance,
        so the command is called as ``command(provider)``.
        """
        return self.command


def _wants_argument(command: Callable) -> bool:
    try:
        params = inspect.signature(command).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(
        p.default is inspect.Parameter.empty
        and p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for p in params
    )


class ActionManager:
    """Registry of actions, shortcuts and buttons (see module docstring)."""

    _actions: dict[str, Action]

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._shortcuts: dict[str, list[KeyBinding | str]] = defaultdict(list)
        self._tooltip_include_action_name = False
        self.events = EmitterGroup(source=self, shortcut_changed=None)

    def _debug(self, val: bool) -> None:
        self._tooltip_include_action_name = val

    def _validate_action_name(self, name: str) -> None:
        if len(name.split(':')) != 2:
            raise ValueError(
                f'Action names need to be in the form `package:name`, '
                f'got {name!r}'
            )

    def register_action(
        self,
        name: str,
        command: Callable,
        description: str,
        keymapprovider: type[KeymapProvider] | None,
        repeatable: bool = False,
    ) -> None:
        """Register ``command`` under ``name`` (``package:name``).

        Shortcuts bound to ``name`` before this call take effect now.
        """
        self._validate_action_name(name)
        self._actions[name] = Action(
            command, description, keymapprovider, repeatable
        )
        if keymapprovider:
            self._update_shortcut_bindings(name)

    def _update_shortcut_bindings(self, name: str) -> None:
        if name not in self._actions or name not in self._shortcuts:
            return
        action = self._actions[name]
        km_provider = action.keymapprovider
        if km_provider is not None:
            for shortcut in self._shortcuts[name]:
                km_provider.bind_key(shortcut, action.injected, overwrite=True)

    def bind_button(
        self,
        name: str,
        button: Button,
        extra_tooltip_text: str = '',
    ) -> None:
        """Make ``button`` trigger action ``name``; keep its tooltip updated."""
        self._validate_action_name(name)

        if (action := self._actions.get(name)) and inspect.isgeneratorfunction(
            getattr(action, 'command', None)
        ):
            raise ValueError(
                '`bind_button` cannot be used with generator functions'
            )

        def _trigger() -> None:
            self.trigger(name)

        button.clicked.connect(_trigger)
        if name in self._actions:
            button.setToolTip(
                f'{self._build_tooltip(name)} {extra_tooltip_text}'
            )

        def _update_tt(event: Event) -> None:
            if event.name == name:
                button.setToolTip(f'{event.tooltip} {extra_tooltip_text}')

        # if it's a QPushbutton, we'll remove it when it gets destroyed
        until = getattr(button, 'destroyed', None)
        self.events.shortcut_changed.connect(_update_tt, until=until)

    def bind_shortcut(self, name: str, shortcut: KeyBinding | str) -> None:
        """Bind ``shortcut`` to action ``name`` (now, or once registered)."""
        self._validate_action_name(name)
        if shortcut in self._shortcuts[name]:
            return
        self._shortcuts[name].append(shortcut)
        self._update_shortcut_bindings(name)
        self._emit_shortcut_change(name, shortcut)

    def unbind_shortcut(self, name: str) -> list[KeyBinding | str] | None:
        """Unbind every shortcut of action ``name``; return them."""
        action = self._actions.get(name, None)
        if action is None:
            warnings.warn(
                f'Attempting to unbind an action which does not exists '
                f'({name}), this may have no effects.',
                UserWarning,
                stacklevel=2,
            )

        shortcuts = self._shortcuts.get(name)
        if shortcuts:
            if action and action.keymapprovider is not None:
                for shortcut in shortcuts:
                    action.keymapprovider.bind_key(shortcut)(None)
            del self._shortcuts[name]

        self._emit_shortcut_change(name)
        return shortcuts

    def _emit_shortcut_change(
        self, name: str, shortcut: KeyBinding | str = ''
    ) -> None:
        tt = self._build_tooltip(name) if name in self._actions else ''
        self.events.shortcut_changed(name=name, shortcut=shortcut, tooltip=tt)

    def _build_tooltip(self, name: str) -> str:
        ttip = self._actions[name].description
        if name in self._shortcuts:
            shorts = ' or '.join(
                f'{Shortcut(s)}' for s in self._shortcuts[name]
            )
            ttip += f' ({shorts})'
        ttip += f'[{name}]' if self._tooltip_include_action_name else ''
        return ttip

    def _get_layer_shortcuts(self, layers: Any) -> dict:
        """{layer class: {shortcut: description}} for the given classes."""
        layer_shortcuts: dict = {}
        for layer in layers:
            layer_shortcuts[layer] = {}
            for name, shortcuts in self._shortcuts.items():
                action = self._actions.get(name, None)
                if action and layer == action.keymapprovider:
                    for shortcut in shortcuts:
                        layer_shortcuts[layer][str(shortcut)] = (
                            action.description
                        )
        return layer_shortcuts

    def _get_provider_actions(self, provider: Any) -> dict[str, Action]:
        return {
            name: action
            for name, action in self._actions.items()
            if action and provider == action.keymapprovider
        }

    def _get_active_shortcuts(self, active_keymap: Any) -> dict[str, str]:
        active_func_names = [i[1].__name__ for i in active_keymap.items()]
        active_shortcuts = {}
        for name, shortcuts in self._shortcuts.items():
            action = self._actions.get(name, None)
            if action and action.command.__name__ in active_func_names:
                for shortcut in shortcuts:
                    active_shortcuts[str(shortcut)] = action.description
        return active_shortcuts

    def _get_repeatable_shortcuts(self, active_keymap: Any) -> list:
        active_func_names = {i[1].__name__ for i in active_keymap.items()}
        active_repeatable_shortcuts = []
        for name, shortcuts in self._shortcuts.items():
            action = self._actions.get(name, None)
            if (
                action
                and action.command.__name__ in active_func_names
                and action.repeatable
            ):
                active_repeatable_shortcuts.extend(shortcuts)
        return active_repeatable_shortcuts

    def trigger(self, name: str, *args: Any) -> Any:
        """Run action ``name``.

        Without arguments the provider is looked up: the current viewer for
        viewer actions, its active layer for layer actions.
        """
        action = self._actions[name]
        if args or not _wants_argument(action.command):
            return action.injected(*args)
        return action.injected(self._find_provider(action))

    @staticmethod
    def _find_provider(action: Action) -> Any:
        from napari_lite.viewer import current_viewer

        viewer = current_viewer()
        provider = action.keymapprovider
        if viewer is None:
            raise RuntimeError(
                f'Cannot trigger {action.command.__name__!r}: no viewer is '
                'open and the action needs one. Call it directly instead.'
            )
        if provider is None or isinstance(viewer, provider):
            return viewer
        layer = viewer.layers.selection.active
        if layer is not None and isinstance(layer, provider):
            return layer
        raise RuntimeError(
            f'Cannot trigger {action.command.__name__!r}: it needs a '
            f'{provider.__name__} and none is selected.'
        )


def bind_shortcuts_from_settings() -> None:
    """Bind the shortcuts in ``get_settings().shortcuts`` to their actions.

    napari does this when its Qt viewer is created; napari-lite's canvas
    and viewer call it, and so can a test.
    """
    from napari_lite.settings import get_settings

    for action, shortcuts in get_settings().shortcuts.shortcuts.items():
        if action in action_manager._actions:
            action_manager.unbind_shortcut(action)
        else:
            # not registered yet (napari-lite's own Qt actions arrive with
            # the first canvas): drop the old entry, bind_shortcut keeps
            # the new one for register_action to pick up
            action_manager._shortcuts.pop(action, None)
        for shortcut in shortcuts:
            action_manager.bind_shortcut(action, shortcut)


action_manager = ActionManager()
