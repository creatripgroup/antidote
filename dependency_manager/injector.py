import functools
import inspect
from itertools import islice

import wrapt

from ._compat import PY3
from .exceptions import *

_EMPTY_DEPENDENCY = object()


class DependencyInjector(object):
    """
    Injects the dependencies from a container before building an object or
    calling a function.
    """

    def __init__(self, container):
        """Initialize the DependencyInjector.

        Args:
            container: Object with :code:`__getitem__()` defined to retrieve
                the dependencies. :py:exc:`.DependencyNotFoundError` should
                be raised whenever a dependency could not be found.

        """
        self._container = container

    def inject(self, mapping=None, use_arg_name=False):
        """Inject the dependency into the function.

        Args:
            mapping (dict, optional): Custom mapping of the arguments name
                to their respective dependency id. Overrides annotations.
                Defaults to None.
            use_arg_name (bool, optional): Whether the arguments name
                should be used to search for a dependency when no mapping,
                nor annotation is found. Defaults to False.

        Returns:6
            callable: The injected function.

        """
        generate_args_kwargs = self._generate_args_kwargs
        # Using nonlocal would be ideal.
        non_local_container = [None]

        @wrapt.decorator
        def fast_inject(wrapped, _, args, kwargs):
            if non_local_container[0] is None:
                non_local_container[0] = self._generate_injection_blueprint(
                    func=wrapped,
                    use_arg_name=use_arg_name,
                    mapping=mapping or dict()
                )

            args, kwargs = generate_args_kwargs(
                args=args,
                kwargs=kwargs,
                injection_blueprint=non_local_container[0]
            )
            return wrapped(*args, **kwargs)

        return fast_inject

    def prepare(self, func, use_arg_name=False, mapping=None, args=None,
                kwargs=None):
        """
        Creates a partial function with the injected arguments.

        It should be used whenever a function is called repeatedly.

        Args:
            func (callable): Callable for which the argument should be
                injected.
            use_arg_name (bool, optional): Whether the arguments name
                should be used to search for a dependency when no mapping,
                nor annotation is found. Defaults to False.
            mapping (dict, optional): Custom mapping of the arguments name
                to their respective dependency id. Overrides annotations.
                Defaults to None.
            args (iterable, optional): Positional arguments which override any
                injection. Defaults to None.
            kwargs (dict, optional): Keyword arguments which override any
                injection. Defaults to None.

        Returns:
            callable: Partial function with its dependencies injected.

        """

        new_args, new_kwargs = self._generate_args_kwargs(
            args=args or tuple(),
            kwargs=kwargs or dict(),
            injection_blueprint=self._generate_injection_blueprint(
                func=func,
                mapping=mapping or dict(),
                use_arg_name=use_arg_name
            )
        )

        return functools.partial(func, *new_args, **new_kwargs)

    def _generate_args_kwargs(self, args, kwargs, injection_blueprint):
        kwargs = kwargs.copy()
        container = self._container

        for arg_name, dependency_id, has_default \
                in islice(injection_blueprint, len(args), None):
            if dependency_id is not _EMPTY_DEPENDENCY \
                    and arg_name not in kwargs:
                try:
                    kwargs[arg_name] = container[dependency_id]
                except DependencyNotFoundError:
                    if has_default is False:
                        raise

        return args, kwargs

    @classmethod
    def _generate_injection_blueprint(cls, func, use_arg_name, mapping):
        argument_mapping = getattr(func, '__annotations__', {}).copy()
        try:
            del argument_mapping['return']
        except KeyError:
            pass
        argument_mapping.update(mapping)

        return tuple(
            (
                name,
                argument_mapping.get(
                    name,
                    name if use_arg_name else _EMPTY_DEPENDENCY
                ),
                has_default,
            )
            for name, has_default in cls._get_arguments_specification(func)
        )

    if PY3:
        @classmethod
        def _get_arguments_specification(cls, func):
            arguments = []
            for name, parameter in inspect.signature(func).parameters.items():
                arguments.append((name,
                                  parameter.default is not parameter.empty))

            return arguments
    else:
        @classmethod
        def _get_arguments_specification(cls, func):
            try:
                argspec = inspect.getargspec(func)
            except TypeError:  # builtin methods or object.__init__
                return tuple()
            else:
                arguments = []
                first_default = len(argspec.args) - len(argspec.defaults or [])

                if inspect.ismethod(func):
                    args = argspec.args[1:]
                    first_default -= 1
                else:
                    args = argspec.args

                for i, name in enumerate(args):
                    arguments.append((name, first_default <= i))

                return arguments