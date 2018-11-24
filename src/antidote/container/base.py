import threading
from collections import OrderedDict
from typing import Any, Dict, TYPE_CHECKING, Type

from .stack import InstantiationStack
from .._internal.utils import SlotReprMixin
from ..exceptions import (DependencyCycleError, DependencyInstantiationError,
                          DependencyNotFoundError, DependencyNotProvidableError)

if TYPE_CHECKING:  # pragma: no cover
    from ..providers import Provider

_SENTINEL = object()


class DependencyContainer:
    """
    Container of dependencies which are instantiated lazily by providers.
    Singleton are cached to ensure they're not rebuilt more than once.

    One can specify additional arguments on how to build a dependency, by
    requiring a :py:class:`~Dependency` or using :py:meth:`~provide`.

    Neither :code:`__contains__()` nor :code:`__delitem__()` are implemented as
    they are error-prone, they would only operate on the cache, not the set of
    available dependencies.
    """

    def __init__(self):
        self.providers = OrderedDict()  # type: Dict[Type[Provider], Provider]
        self._singletons = {}
        self._instantiation_lock = threading.RLock()
        self._instantiation_stack = InstantiationStack()

    def __str__(self):
        return "{}(providers=({}))".format(
            type(self).__name__,
            ", ".join("{}={}".format(name, p)
                      for name, p in self.providers.items()),
        )

    def __repr__(self):
        return "{}(providers=({}), singletons={!r})".format(
            type(self).__name__,
            ", ".join("{!r}={!r}".format(name, p)
                      for name, p in self.providers.items()),
            self._singletons
        )

    def __getitem__(self, dependency):
        """
        Get the specified dependency. :code:`item` is either the dependency_id
        or a :py:class:`~Dependency` instance in order to provide additional
        arguments to the providers.
        """
        try:
            return self._singletons[dependency]
        except KeyError:
            pass

        try:
            with self._instantiation_lock, \
                    self._instantiation_stack.instantiating(dependency):
                try:
                    return self._singletons[dependency]
                except KeyError:
                    pass

                for provider in self.providers.values():
                    try:
                        instance = provider.__antidote_provide__(
                            dependency
                            if isinstance(dependency, Dependency) else
                            Dependency(dependency)
                        )  # type: Instance
                    except DependencyNotProvidableError:
                        pass
                    else:
                        if instance.singleton:
                            self._singletons[dependency] = instance.item

                        return instance.item

        except DependencyCycleError:
            raise

        except Exception as e:
            raise DependencyInstantiationError(dependency) from e

        raise DependencyNotFoundError(dependency)

    def __setitem__(self, dependency_id, dependency):
        """
        Set a dependency in the cache.
        """
        with self._instantiation_lock:
            self._singletons[dependency_id] = dependency

    def update(self, *args, **kwargs):
        """
        Update the cached dependencies.
        """
        with self._instantiation_lock:
            self._singletons.update(*args, **kwargs)


class Dependency(SlotReprMixin):
    """
    Simple container which can be used to specify a dependency ID with
    additional arguments, :code:`args` and :code:`kwargs`, for the provider.

    If no additional arguments are provided it is equivalent to the unwrapped
    dependency id.

    >>> from antidote import antidote, Dependency
    >>> antidote.container['name'] = 'Antidote'
    >>> antidote.container[Dependency('name')]
    'Antidote'

    """
    __slots__ = ('id',)

    def __init__(self, id):
        self.id = id  # type: Any
        # Just in case, because it wouldn't make any sense.
        assert not isinstance(self.id, Dependency)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return (self.id == other
                or (isinstance(other, Dependency) and self.id == other.id))


class Instance(SlotReprMixin):
    """
    Simple wrapper which has to be used by providers when returning an
    instance of a dependency.

    This enables the container to know if the returned dependency needs to
    be cached or not (singleton).
    """
    __slots__ = ('item', 'singleton')

    def __init__(self, item, singleton: bool = False):
        self.item = item
        self.singleton = singleton