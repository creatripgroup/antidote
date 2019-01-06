import pytest

from antidote import wire
from antidote.core import DependencyContainer


@pytest.fixture()
def container():
    container = DependencyContainer()
    container.update_singletons(dict(x=object(), y=object()))
    return container


def test_multi_wire(container: DependencyContainer):
    xx = container['x']
    yy = container['y']

    @wire(methods=['f', 'g'],
          dependencies=dict(x='x', y='y'),
          container=container)
    class Dummy:
        def f(self, x):
            return x

        def g(self, x, y):
            return x, y

    d1 = Dummy()
    assert xx == d1.f()
    assert (xx, yy) == d1.g()

    @wire(methods=['f', 'g'],
          use_names=['x', 'y'],
          container=container)
    class Dummy2:
        def f(self, x):
            return x

        def g(self, x, y):
            return x, y

    d2 = Dummy2()
    assert xx == d2.f()
    assert (xx, yy) == d2.g()

    container.update_singletons({Dummy: d1, Dummy2: d2})

    @wire(methods=['f', 'g'],
          use_type_hints=['x', 'y'],
          container=container)
    class Dummy3:
        def f(self, x: Dummy):
            return x

        def g(self, x: Dummy, y: Dummy2):
            return x, y

    assert d1 == Dummy3().f()
    assert (d1, d2) == Dummy3().g()


def test_subclass_classmethod(container: DependencyContainer):
    xx = container['x']

    @wire(methods=['cls_method'], use_names=True, container=container)
    class Dummy:
        @classmethod
        def cls_method(cls, x):
            return cls, x

    assert (Dummy, xx) == Dummy.cls_method()

    class SubDummy(Dummy):
        pass

    assert (SubDummy, xx) == SubDummy.cls_method()


def test_use_mro(container: DependencyContainer):
    xx = container['x']
    sentinel = object()

    class Dummy:
        def method(self, x):
            return self, x

    @wire(use_mro=True, methods=['method'], use_names=True, container=container)
    class SubDummy(Dummy):
        pass

    sub_dummy = SubDummy()

    assert (sub_dummy, xx) == sub_dummy.method()
    assert (sub_dummy, sentinel) == sub_dummy.method(sentinel)

    with pytest.raises(TypeError):  # did not affect base class
        Dummy().method()


def test_do_not_change_for_nothing(container: DependencyContainer):
    def original_method(self, something):
        pass

    @wire(methods=['method'], container=container)
    class Dummy:
        method = original_method

    assert Dummy.__dict__['method'] is original_method

    @wire(use_mro=True, methods=['method'], container=container)
    class SubDummy(Dummy):
        pass

    assert 'method' not in SubDummy.__dict__
    assert SubDummy.method is Dummy.method


@pytest.mark.parametrize('obj', [object(), lambda: None])
def test_invalid_class(obj):
    with pytest.raises(TypeError):
        wire(obj, methods=['__init__'])


@pytest.mark.parametrize(
    'kwargs',
    [
        dict(methods=['__init__', '__call__'], dependencies=(None, None)),
        dict(methods=['__init__'], use_mro=['__call__']),
    ]
)
def test_invalid_params(kwargs):
    with pytest.raises(ValueError):
        @wire(**kwargs)
        class Dummy:
            pass


@pytest.mark.parametrize(
    'kwargs',
    [
        dict(methods=object()),
        dict(methods=['method'], use_mro=object()),
        dict(methods=['method'], ignore_missing_methods=object()),
    ]
)
def test_invalid_type(kwargs):
    with pytest.raises(TypeError):
        @wire(**kwargs)
        class Dummy:
            pass


def test_ignore_missing_methods(container: DependencyContainer):
    with pytest.raises(TypeError):
        @wire(methods=['method'], container=container,
              ignore_missing_methods=False)
        class Dummy:
            pass

    @wire(methods=['method'], container=container, ignore_missing_methods=True)
    class Dummy2:
        pass