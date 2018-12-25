import threading
from collections import deque
from typing import (Any, Callable, Deque, Dict, Generic, Iterable, Iterator, List,
                    Optional, TypeVar, Union)

from .dependency import Tag, Tagged
from ...core import DependencyContainer, DependencyInstance, DependencyProvider
from ...exceptions import DuplicateTagError, DependencyNotFoundError

T = TypeVar('T')


class TaggedDependency:
    def __init__(self, dependency: Any, tag: Tag):
        self.dependency = dependency
        self.tag = tag


class TaggedDependencies(Generic[T]):
    """
    Collection containing dependencies and their tags. Dependencies are lazily
    instantiated. This is thread-safe.

    Used by :py:class:`~.TagProvider` to return the dependencies matching a tag.
    """

    def __init__(self,
                 container: DependencyContainer,
                 tagged_dependencies: Iterable[TaggedDependency]):
        self._container = container
        self._lock = threading.Lock()
        self._dependencies = []  # type: List[Any]
        self._tags = []  # type: List[Tag]
        self._instances = []  # type: List[T]

        for tagged_dependency in tagged_dependencies:
            self._dependencies.append(tagged_dependency.dependency)
            self._tags.append(tagged_dependency.tag)

    def __len__(self):
        return len(self._tags)

    def dependencies(self) -> Iterable[Any]:
        """
        Returns all the dependencies retrieved. This does not instantiate them.
        """
        return iter(self._dependencies)

    def tags(self) -> Iterable[Tag]:
        """
        Returns all the tags retrieved. This does not instantiate the
        dependencies.
        """
        return iter(self._tags)

    def instances(self) -> Iterator[T]:
        """
        Returns the dependencies, in a stable order for multi-threaded
        environments.
        """
        i = -1
        for i, instance in enumerate(self._instances):
            yield instance

        i += 1
        while i < len(self):
            try:
                yield self._instances[i]
            except IndexError:
                with self._lock:
                    # If not other thread has already added the instance.
                    if i == len(self._instances):
                        instance = self._container.provide(self._dependencies[i])
                        if instance is self._container.SENTINEL:
                            raise DependencyNotFoundError(self._dependencies[i])

                        self._instances.append(instance)
                yield self._instances[i]
            i += 1


class TagProvider(DependencyProvider):
    """
    Provider managing string tag. Tags allows one to retrieve a collection of
    dependencies marked by their creator.
    """
    bound_types = (Tagged,)

    def __init__(self, container: DependencyContainer):
        self._dependency_to_tag_by_tag_name = {}  # type: Dict[str, Dict[Any, Tag]]
        self._container = container

    def __repr__(self):
        return "{}(tagged_dependencies={!r})".format(
            type(self).__name__,
            self._dependency_to_tag_by_tag_name
        )

    def provide(self, dependency) -> Optional[DependencyInstance]:
        """
        Returns all dependencies matching the tag name specified with a
        :py:class:`~.dependency.Tagged`. For every other case, :obj:`None` is
        returned.

        Args:
            dependency: Only :py:class:`~.dependency.Tagged` is supported, all
                others are ignored.

        Returns:
            :py:class:`~.TaggedDependencies` wrapped in a
            :py:class:`~..core.Instance`.
        """
        if isinstance(dependency, Tagged):
            dependency_to_tag = self._dependency_to_tag_by_tag_name.get(dependency.name,
                                                                        {})
            return DependencyInstance(
                TaggedDependencies(
                    container=self._container,
                    tagged_dependencies=(
                        TaggedDependency(dependency=dependency_, tag=tag)
                        for dependency_, tag
                        in dependency_to_tag.items()
                    )
                ),
                # Whether the returned dependencies are singletons or not is
                # their decision to take.
                singleton=False
            )

        return None

    def register(self, dependency, tags: Iterable[Union[str, Tag]]):
        """
        Mark a dependency with all the supplied tags. Raises
        :py:exc:`~.exceptions.DuplicateTagError` if the tag has already been
        used for this dependency.

        Args:
            dependency: dependency to register.
            tags: Iterable of tags which should be associated with the
                dependency
        """
        for tag in tags:
            if isinstance(tag, str):
                tag = Tag(tag)

            if not isinstance(tag, Tag):
                raise ValueError("Expecting tag of type Tag, not {}".format(type(tag)))

            if tag.name not in self._dependency_to_tag_by_tag_name:
                self._dependency_to_tag_by_tag_name[tag.name] = {dependency: tag}
            elif dependency not in self._dependency_to_tag_by_tag_name[tag.name]:
                self._dependency_to_tag_by_tag_name[tag.name][dependency] = tag
            else:
                raise DuplicateTagError(tag.name)