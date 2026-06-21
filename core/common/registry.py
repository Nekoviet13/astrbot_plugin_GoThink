"""Non-singleton registry infrastructure."""

from typing import Dict, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class BaseRegistry(Generic[T]):
    """Small explicit registry for pluggable components."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._items: Dict[str, T] = {}

    def register(self, name: str, item: T) -> None:
        """Register an item by name."""
        if not name:
            raise ValueError("registry name must not be empty")
        self._items[name] = item

    def get(self, name: str) -> Optional[T]:
        """Return a registered item by name if it exists."""
        return self._items.get(name)

    def require(self, name: str) -> T:
        """Return a registered item or raise KeyError."""
        item = self.get(name)
        if item is None:
            raise KeyError(f"registry item not found: {name}")
        return item

    def names(self) -> Iterable[str]:
        """Return registered names."""
        return tuple(self._items.keys())

    def values(self) -> Iterable[T]:
        """Return registered values."""
        return tuple(self._items.values())
