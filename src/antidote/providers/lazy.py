from typing import Callable, Dict, Optional, Tuple, Union

from .._internal.utils import SlotsReprMixin
from ..core import DependencyInstance, DependencyProvider


class LazyCall(SlotsReprMixin):
    __slots__ = ('_func', '_args', '_kwargs', '_singleton')

    def __init__(self, func: Callable, singleton: bool = True):
        self._singleton = singleton
        self._func = func
        self._args = ()  # type: Tuple
        self._kwargs = {}  # type: Dict

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        return self


class LazyMethodCall(SlotsReprMixin):
    __slots__ = ('_method_name', '_args', '_kwargs', '_singleton', '_key')

    def __init__(self, method: Union[Callable, str], singleton: bool = True):
        self._singleton = singleton
        # Retrieve the name of the method, as injection can be done after the class
        # creation which is typically the case with @register.
        self._method_name = method if isinstance(method, str) else method.__name__
        self._args = ()  # type: Tuple
        self._kwargs = {}  # type: Dict
        self._key = None

    def __call__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        return self

    def __get__(self, instance, owner):
        if instance is None:
            if self._singleton:
                if self._key is None:
                    self._key = "{}_dependency".format(self._get_attribute_name(owner))
                    setattr(owner, self._key, LazyMethodCallDependency(self, owner))
                return getattr(owner, self._key)
            return LazyMethodCallDependency(self, owner)
        return getattr(instance, self._method_name)(*self._args, **self._kwargs)

    # The attribute is expected to be found in owner, as one should not call
    # directly __get__.
    def _get_attribute_name(self, owner):
        for k, v in owner.__dict__.items():  # pragma: no cover
            if v is self:
                return k


class LazyMethodCallDependency(SlotsReprMixin):
    __slots__ = ('lazy_method_call', 'owner')

    def __init__(self, lazy_method_call, owner):
        self.lazy_method_call = lazy_method_call
        self.owner = owner


class LazyCallProvider(DependencyProvider):
    bound_dependency_types = (LazyMethodCallDependency, LazyCall)

    def provide(self,
                dependency: Union[LazyMethodCallDependency, LazyCall]
                ) -> Optional[DependencyInstance]:
        if isinstance(dependency, LazyMethodCallDependency):
            return DependencyInstance(
                dependency.lazy_method_call.__get__(
                    self._container.provide(dependency.owner),
                    dependency.owner
                ),
                singleton=dependency.lazy_method_call._singleton
            )
        elif isinstance(dependency, LazyCall):
            return DependencyInstance(
                dependency._func(*dependency._args, **dependency._kwargs),
                singleton=dependency._singleton
            )
