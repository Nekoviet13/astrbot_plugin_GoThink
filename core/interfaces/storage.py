"""Storage ports for persistence infrastructure."""

from collections.abc import Sequence
from typing import Protocol

from ..models import Thought
from ..models.enums import MemoryType


class IThoughtDAO(Protocol):
    """Low-level CRUD interface for thought records."""

    def create_table(self) -> None:
        """Create required database tables if they do not exist."""

    def insert(self, thought: Thought) -> None:
        """Insert a thought record."""

    def update(self, thought: Thought) -> None:
        """Update an existing thought record."""

    def delete(self, thought_id: str) -> None:
        """Delete a thought record by ID."""

    def get_by_id(self, thought_id: str) -> Thought | None:
        """Return one thought by ID if it exists."""

    def list_recent(
        self,
        object_id: str | None = None,
        limit: int = 20,
    ) -> Sequence[Thought]:
        """Return recent thoughts ordered by timestamp descending."""

    def list_by_session(self, session_id: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts for one session ordered by timestamp descending."""

    def list_by_memory_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> Sequence[Thought]:
        """Return thoughts for one memory type ordered by timestamp descending."""

    def search_keyword(self, keyword: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts containing a keyword."""


class IThoughtRepository(Protocol):
    """Repository interface for aggregate thought queries."""

    def save(self, thought: Thought) -> Thought:
        """Persist and return the thought."""

    def get(self, thought_id: str) -> Thought | None:
        """Return one thought by ID if it exists."""

    def remove(self, thought_id: str) -> None:
        """Remove a thought by ID."""

    def recent(
        self,
        object_id: str | None = None,
        limit: int = 20,
    ) -> Sequence[Thought]:
        """Return recent thoughts."""

    def by_session(self, session_id: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts from a session."""

    def by_memory_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> Sequence[Thought]:
        """Return thoughts of a memory type."""

    def search(self, keyword: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts matching a keyword."""
