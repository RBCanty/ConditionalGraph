from enum import IntEnum
from typing import Self, Generator, Callable

CONSISTENT = 'consistent'


class Direction(IntEnum):
    DOWN = -1
    UP = 1
    BOTH = 0


class EdgeSet[T]:
    def __init__(self):
        self.children: set[T] = set()
        self.parents: set[T] = set()

    def __add__(self, other):
        if not isinstance(other, EdgeSet):
            raise TypeError(f"Cannot add an EdgeSet to a {type(other)}")
        new_set = EdgeSet()
        new_set.children = self.children | other.children
        new_set.parents = self.parents | other.parents
        return new_set


class GenericStatefulGraph[T]:
    state_cache: dict[str, str] = {}
    """ component_state_id, state_name """

    def __init__(self, data: T):
        self.data = data
        self._state_ids: set[str] = set()
        self._connections: dict[str, EdgeSet[Self]] = {
            CONSISTENT: EdgeSet[Self]()
        }

    @classmethod
    def set_state(cls, component_state_id: str, state: str):
        cls.state_cache[component_state_id] = state

    def print(self, ignore_state: bool = False) -> str:
        """ Provides a quick summary of the node """
        connections = self.connections(ignore_state)
        n_children = len(connections.children)
        n_parents = len(connections.parents)
        states = ", ".join(
            f"{component_state_id}:{state}"
            for component_state_id, state in self.state_cache.items()
            if component_state_id in self._state_ids
        )
        return f"{self.data!s} ({n_children} children and {n_parents} parents; {states})"

    def _add_child(self, child: Self, component_state_id: str, state_name: str):
        if component_state_id is not None:
            self._state_ids.add(component_state_id)
            self.state_cache.setdefault(component_state_id, state_name)
        self._connections.setdefault(state_name, EdgeSet())
        self._connections[state_name].children.add(child)

    def _add_parent(self, parent: Self, component_state_id: str, state_name: str):
        if component_state_id is not None:
            self._state_ids.add(component_state_id)
            self.state_cache.setdefault(component_state_id, state_name)
        self._connections.setdefault(state_name, EdgeSet())
        self._connections[state_name].parents.add(parent)

    def connections(self, ignore_state: bool = False) -> EdgeSet[Self]:
        """ Finds all incoming/outgoing edges for this node in the current state """
        if ignore_state:
            return sum(self._connections.values(), start=EdgeSet())
        return sum(
            [
                self._connections.get(self.state_cache[state_id], EdgeSet())
                for state_id in self._state_ids
            ],
            start=self._connections[CONSISTENT]
        )

    def has_children(self, ignore_state: bool = False) -> int:
        """ Provides how many children the node has in the current state """
        return len(self.connections(ignore_state).children)

    def has_parents(self, ignore_state: bool = False) -> int:
        """ Provides how many parents the node has in the current state """
        return len(self.connections(ignore_state).parents)

    def connect(
            self,
            *targets: Self,
            for_state: tuple[str, str] = None,
            direction: Direction = Direction.DOWN
    ) -> Self:
        """ Connects caller to targets.

        :param for_state: To which state this connection applies (Default 1, the default state)
        :param direction: If DOWN, target is a child of the caller; If UP, target is a parent of the caller; If BOTH,
          then the edge is non-directional (target is both child and parent of the caller).
        :return: Self, to allow chaining of the connect call.
        """
        if for_state is None:
            for_state = (None, CONSISTENT)

        for target in targets:  # type: Self
            if direction <= 0:
                self._add_child(target, *for_state)
                target._add_parent(self, *for_state)
            if direction >= 0:
                self._add_parent(target, *for_state)
                target._add_child(self, *for_state)
        return self

    def _traverse(
            self,
            target: Callable[[Self], bool],
            direction: Direction,
            visited: set[Self] = None,
            path: list[Self] = None,
            ignore_state: bool = False
    ) -> Generator[tuple[Self, list[Self]], None, None]:
        if visited is None:
            visited = set()
        if path is None:
            path = []

        space: set[Self] = set()
        if direction <= 0:
            space |= self.connections(ignore_state).children  # space = the union of space and children
        if direction >= 0:
            space |= self.connections(ignore_state).parents

        # print(f"Search space: " + ", ".join([str(_n) for _n in space]))

        visited.add(self)
        path.append(self)
        if target(self):
            yield self, path.copy()
        for subgraph in space:  # type: Self
            if subgraph not in visited:
                yield from subgraph._traverse(target, direction, visited, path, ignore_state)
        path.pop()
        visited.remove(self)

    def traverse(
            self,
            condition: Callable[[Self], bool] = None,
            direction: Direction = Direction.DOWN,
            ignore_state: bool = False
    ) -> list[tuple[Self, list[Self]]]:
        """ Traverses the graph in search of a given condition.

        :param condition: Called on each node in the graph to determine if the traversal was successful.  By default,
          the condition is that the Node is childless (leaf).
        :param direction: Whether the search should explore only children (default) or parents as well.
        :param ignore_state: True, checks all connections, regardless of current state (Default: False)
        """
        if condition is None:
            condition: Callable[[GenericStatefulGraph[T]], bool] = lambda n: not n.has_children
        return [t for t in self._traverse(condition, direction, ignore_state=ignore_state)]
