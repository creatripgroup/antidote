# cython: language_level=3, language=c++
# cython: boundscheck=False, wraparound=False
import bisect
import re
from typing import Any, Callable, Dict, List

# @formatter:off
from cpython.dict cimport PyDict_GetItem
from cpython.ref cimport PyObject

from antidote.core.container cimport DependencyInstance, DependencyProvider
from ..exceptions import GetterPriorityConflict
# @formatter:on


cdef class ResourceProvider(DependencyProvider):
    def __init__(self):
        self._priority_sorted_getters_by_namespace = dict()  # type: Dict[str, List[ResourceGetter]]  # noqa

    def __repr__(self):
        return "{}(getters={!r})".format(type(self).__name__,
                                         self._priority_sorted_getters_by_namespace)

    cpdef DependencyInstance provide(self, object dependency):
        cdef:
            ResourceGetter getter
            object instance
            str resource
            str namespace_
            str resource_name
            PyObject*ptr
            ssize_t i

        if isinstance(dependency, str):
            resource = <str> dependency
            i = resource.find(':')
            if i == -1:
                return
            else:
                namespace_ = resource[:i]
                resource_name = resource[i + 1:]
            ptr = PyDict_GetItem(self._priority_sorted_getters_by_namespace, namespace_)
            if ptr != NULL:
                for getter in <list> ptr:
                    try:
                        if getter.omit_namespace:
                            instance = getter.func(resource_name)
                        else:
                            instance = getter.func(resource)
                    except LookupError:
                        pass
                    else:
                        return DependencyInstance.__new__(DependencyInstance,
                                                          instance,
                                                          getter.singleton)

    def register(self,
                 resource_getter: Callable[[str], Any],
                 namespace: str,
                 priority: float = 0,
                 omit_namespace: bool = True,
                 singleton: bool = True):
        if not isinstance(namespace, str):
            raise ValueError(
                "namespace must be a string, not a {!r}".format(type(namespace))
            )
        elif not re.match(r'^\w+$', namespace):
            raise ValueError("namespace can only contain characters in [a-zA-Z0-9_]")

        if not isinstance(priority, (int, float)):
            raise ValueError(
                "priority must be a number, not a {!r}".format(type(priority))
            )

        getters = self._priority_sorted_getters_by_namespace.get(namespace) or []

        for g in getters:
            if g.priority == priority:
                raise GetterPriorityConflict(repr(g), repr(resource_getter))

        # Highest priority should be first
        idx = bisect.bisect([-g.priority for g in getters], -priority)
        getters.insert(idx, ResourceGetter(func=resource_getter,
                                           priority=priority,
                                           omit_namespace=omit_namespace,
                                           singleton=singleton))

        self._priority_sorted_getters_by_namespace[namespace] = getters

cdef class ResourceGetter:
    cdef:
        readonly object func
        readonly bint singleton
        readonly bint omit_namespace
        readonly float priority

    def __init__(self,
                 func: Callable[[str], Any],
                 float priority,
                 bint omit_namespace,
                 bint singleton):
        self.func = func
        self.omit_namespace = omit_namespace
        self.singleton = singleton
        self.priority = priority

    def __repr__(self):
        return "{}(func={!r}, omit_namespace={!r}, priority={!r}, " \
               "singleton={!r})".format(
            type(self).__name__,
            self.func,
            self.omit_namespace,
            self.priority,
            self.singleton
        )