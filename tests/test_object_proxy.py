# napari-lite: own code
"""The own ``ObjectProxy`` behaves like ``wrapt.ObjectProxy`` where
``utils/_proxies.py`` relies on it (napari's copied tests of
``ReadOnlyWrapper`` and ``PublicOnlyProxy`` cover the rest)."""

from __future__ import annotations

import copy
import pickle

import pytest

from napari_lite.utils._object_proxy import ObjectProxy


class Thing:
    value = 1

    def __init__(self) -> None:
        self.items = {'a': 1}

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key, value):
        self.items[key] = value

    def method(self) -> str:
        return 'called'


def test_attributes_and_items_go_to_the_wrapped_object() -> None:
    thing = Thing()
    proxy = ObjectProxy(thing)
    assert proxy.value == 1
    assert proxy.method() == 'called'
    assert proxy['a'] == 1
    proxy.value = 2
    proxy['b'] = 3
    assert thing.value == 2
    assert thing.items == {'a': 1, 'b': 3}
    del proxy.value
    assert thing.value == 1  # the class attribute shows again
    with pytest.raises(AttributeError):
        _ = proxy.missing


def test_isinstance_sees_through_but_type_does_not() -> None:
    proxy = ObjectProxy(Thing())
    assert isinstance(proxy, Thing)
    assert isinstance(proxy, ObjectProxy)
    assert type(proxy) is ObjectProxy
    assert proxy.__class__ is Thing


def test_self_attributes_live_on_the_proxy() -> None:
    thing = Thing()
    proxy = ObjectProxy(thing)
    proxy._self_note = 'mine'
    assert proxy._self_note == 'mine'
    assert not hasattr(thing, '_self_note')
    with pytest.raises(AttributeError):
        _ = proxy._self_other
    assert proxy.__wrapped__ is thing


def test_subclass_hooks_as_in_wrapt() -> None:
    class ReadOnly(ObjectProxy):
        def __setattr__(self, name, value):
            if name != '__wrapped__' and not name.startswith('_self_'):
                raise TypeError(name)
            super().__setattr__(name, value)

        def __getattr__(self, name):
            return super().__getattr__(name)

    proxy = ReadOnly(Thing())
    assert proxy.value == 1
    with pytest.raises(TypeError):
        proxy.value = 5


def test_protocols() -> None:
    data = [3, 1, 2]
    proxy = ObjectProxy(data)
    assert len(proxy) == 3
    assert list(proxy) == data
    assert 1 in proxy
    assert proxy == [3, 1, 2]
    assert proxy != [1]
    assert bool(ObjectProxy([])) is False
    assert hash(ObjectProxy('text')) == hash('text')
    assert str(ObjectProxy(42)) == '42'
    assert ObjectProxy(1) < 2
    assert 'ObjectProxy' in repr(proxy) and 'list' in repr(proxy)
    assert 'append' in dir(proxy)


def test_copy_and_pickle_are_refused() -> None:
    proxy = ObjectProxy(Thing())
    with pytest.raises(NotImplementedError):
        copy.copy(proxy)
    with pytest.raises(NotImplementedError):
        copy.deepcopy(proxy)
    with pytest.raises(NotImplementedError):
        pickle.dumps(proxy)
