"""ID generation infrastructure."""

from typing import Protocol
from uuid import uuid4


class IdGenerator(Protocol):
    """Port for externally supplied entity IDs."""

    def new_id(self, prefix: str = "") -> str:
        """Return a new entity ID."""


class UUIDGenerator:
    """UUID4-based ID generator."""

    def new_id(self, prefix: str = "") -> str:
        """Return a UUID4 string, optionally prefixed."""
        value = uuid4().hex
        return f"{prefix}{value}" if prefix else value
