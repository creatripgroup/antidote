import pytest

from dependency_manager import ServiceManager


def test_attrs():
    manager = ServiceManager()
    container = manager.container

    try:
        import attr
    except ImportError:
        with pytest.raises(RuntimeError):
            manager.attrib()
        return

    @manager.register
    class Service(object):
        pass

    container['parameter'] = object()

    @attr.s
    class Test(object):
        service = manager.attrib(Service)
        parameter = manager.attrib(inject_by_name=True)

    test = Test()

    assert container[Service] is test.service
    assert container['parameter'] is test.parameter

    @attr.s
    class BrokenTest(object):
        service = manager.attrib()

    with pytest.raises(ValueError):
        _ = BrokenTest()