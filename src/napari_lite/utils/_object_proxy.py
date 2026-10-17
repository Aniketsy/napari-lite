# napari-lite: own code
"""A transparent object proxy: the part of ``wrapt.ObjectProxy`` that
``utils/_proxies.py`` builds on.

napari derives its ``ReadOnlyWrapper`` and ``PublicOnlyProxy`` from
``wrapt.ObjectProxy``.  wrapt is a dependency for that one base class, and
importing it brings asyncio along: 46 modules in a viewer window that
nothing else needs.  This class keeps wrapt's contract as far as napari
relies on it:

- attribute and item access go to the wrapped object, which the subclasses
  reach through ``super().__getattr__``, ``__setattr__``, ``__getitem__``
  and ``__setitem__``;
- ``__class__`` reports the wrapped object's class, so ``isinstance`` sees
  through the proxy while ``type()`` still tells a proxy apart;
- attributes named ``_self_*`` and ``__wrapped__`` live on the proxy
  itself, everything else is set on the wrapped object;
- equality, hashing, length, iteration, containment, truth value and
  context management are those of the wrapped object.

Copying and pickling a proxy raise ``NotImplementedError``, as in wrapt.
"""

from __future__ import annotations

from typing import Any


def _is_proxy_attr(name: str) -> bool:
    return name == '__wrapped__' or name.startswith('_self_')


class ObjectProxy:
    """Forward everything to ``wrapped``; see the module docstring."""

    def __init__(self, wrapped: Any) -> None:
        object.__setattr__(self, '__wrapped__', wrapped)

    # -- identity -----------------------------------------------------------

    @property  # type: ignore[override]
    def __class__(self) -> type:
        return type(self.__wrapped__)

    @__class__.setter
    def __class__(self, value: type) -> None:
        self.__wrapped__.__class__ = value

    def __repr__(self) -> str:
        wrapped = self.__wrapped__
        return (
            f'<{type(self).__name__} at 0x{id(self):x} for '
            f'{type(wrapped).__name__} at 0x{id(wrapped):x}>'
        )

    def __str__(self) -> str:
        return str(self.__wrapped__)

    def __dir__(self) -> list[str]:
        return dir(self.__wrapped__)

    # -- attributes ---------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        # reached only when normal lookup on the proxy fails
        if name == '__wrapped__':
            raise ValueError('wrapper has not been initialised')
        if name.startswith('_self_'):
            raise AttributeError(name)
        return getattr(self.__wrapped__, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if _is_proxy_attr(name):
            object.__setattr__(self, name, value)
        else:
            setattr(self.__wrapped__, name, value)

    def __delattr__(self, name: str) -> None:
        if _is_proxy_attr(name):
            object.__delattr__(self, name)
        else:
            delattr(self.__wrapped__, name)

    # -- items and protocols ------------------------------------------------

    def __getitem__(self, key: Any) -> Any:
        return self.__wrapped__[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        self.__wrapped__[key] = value

    def __delitem__(self, key: Any) -> None:
        del self.__wrapped__[key]

    def __contains__(self, item: Any) -> bool:
        return item in self.__wrapped__

    def __len__(self) -> int:
        return len(self.__wrapped__)

    def __iter__(self) -> Any:
        return iter(self.__wrapped__)

    def __bool__(self) -> bool:
        return bool(self.__wrapped__)

    def __hash__(self) -> int:
        return hash(self.__wrapped__)

    def __eq__(self, other: object) -> bool:
        return self.__wrapped__ == other

    def __ne__(self, other: object) -> bool:
        return self.__wrapped__ != other

    def __lt__(self, other: Any) -> bool:
        return self.__wrapped__ < other

    def __le__(self, other: Any) -> bool:
        return self.__wrapped__ <= other

    def __gt__(self, other: Any) -> bool:
        return self.__wrapped__ > other

    def __ge__(self, other: Any) -> bool:
        return self.__wrapped__ >= other

    def __enter__(self) -> Any:
        return self.__wrapped__.__enter__()

    def __exit__(self, *args: Any) -> Any:
        return self.__wrapped__.__exit__(*args)

    # -- not supported, as in wrapt -----------------------------------------

    def __copy__(self) -> None:
        raise NotImplementedError('object proxy must define __copy__()')

    def __deepcopy__(self, memo: dict) -> None:
        raise NotImplementedError('object proxy must define __deepcopy__()')

    def __reduce__(self) -> None:
        raise NotImplementedError('object proxy must define __reduce_ex__()')

    def __reduce_ex__(self, protocol: Any) -> None:
        raise NotImplementedError('object proxy must define __reduce_ex__()')
