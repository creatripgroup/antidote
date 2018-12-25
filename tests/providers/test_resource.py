import pytest

from antidote import DependencyInstance
from antidote.exceptions import GetterPriorityConflict
from antidote.providers import ResourceProvider


def test_repr():
    provider = ResourceProvider()

    def getter(_):
        pass

    provider.register(resource_getter=getter, namespace='a')

    assert str(getter) in repr(provider)


def test_simple_getter():
    provider = ResourceProvider()
    data = dict(y=object(), x=object())

    def getter(key):
        return data[key]

    provider.register(resource_getter=getter, namespace='a')

    assert isinstance(provider.provide('a:y'), DependencyInstance)
    assert data['y'] == provider.provide('a:y').instance
    assert data['x'] == provider.provide('a:x').instance

    assert provider.provide('a:z') is None


def test_namespace():
    provider = ResourceProvider()

    provider.register(resource_getter=lambda _: 1, namespace='g1')
    provider.register(resource_getter=lambda _: 2, namespace='g2')

    assert 1 == provider.provide('g1:test').instance
    assert 2 == provider.provide('g2:test').instance

    assert provider.provide('g3:test') is None


def test_omit_namespace():
    provider = ResourceProvider()
    data = dict(y=object(), x=object())

    def getter(key):
        return data[key]

    provider.register(resource_getter=getter, namespace='conf', omit_namespace=True)

    assert data['y'] == provider.provide('conf:y').instance
    assert data['x'] == provider.provide('conf:x').instance


def test_priority():
    provider = ResourceProvider()

    def high(key):
        return {'test': 'high'}[key]

    def low(_):
        return 'low'

    provider.register(resource_getter=high, namespace='g', priority=2)
    provider.register(resource_getter=low, namespace='g', priority=-1)

    assert 'high' == provider.provide('g:test').instance
    assert 'low' == provider.provide('g:test2').instance


@pytest.mark.parametrize('namespace', ['test:', 'test ', 'Nop!yes', '', object(), 1])
def test_invalid_namespace(namespace):
    provider = ResourceProvider()
    with pytest.raises((TypeError,  # TypeError for Cython
                        ValueError)):  # TypeError for pure Python
        provider.register(resource_getter=lambda _: None, namespace=namespace)


@pytest.mark.parametrize('priority', ['test', 1 + 3j, None])
def test_invalid_priority(priority):
    provider = ResourceProvider()
    with pytest.raises((TypeError,  # TypeError for Cython
                        ValueError)):  # TypeError for pure Python
        provider.register(resource_getter=lambda _: None, namespace='test',
                          priority=priority)


def test_priority_conflict():
    provider = ResourceProvider()
    provider.register(resource_getter=lambda _: None, namespace='g', priority=2)

    with pytest.raises(GetterPriorityConflict):
        provider.register(resource_getter=lambda _: None, namespace='g', priority=2)


def test_singleton():
    provider = ResourceProvider()

    provider.register(lambda _: object(), namespace='default')
    assert True is provider.provide('default:').singleton

    provider.register(lambda _: object(), namespace='singleton', singleton=True)
    assert True is provider.provide('singleton:').singleton

    provider.register(lambda _: object(), namespace='unique', singleton=False)
    assert False is provider.provide('unique:').singleton