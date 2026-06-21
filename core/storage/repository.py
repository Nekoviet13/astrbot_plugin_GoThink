"""Repository implementations for memory aggregates."""

from collections.abc import Sequence

from ..interfaces.storage import IThoughtDAO
from ..models import Thought
from ..models.enums import MemoryType


class ThoughtRepository:
    """Repository for thought persistence and aggregate queries."""

    def __init__(self, dao: IThoughtDAO) -> None:
        """Initialize the repository with a thought DAO."""
        self._dao = dao

    def save(self, thought: Thought) -> Thought:
        """Persist and return the thought."""
        if self._dao.get_by_id(thought.id) is None:
            self._dao.insert(thought)
        else:
            self._dao.update(thought)
        return thought

    def get(self, thought_id: str) -> Thought | None:
        """Return one thought by ID if it exists."""
        return self._dao.get_by_id(thought_id)

    def remove(self, thought_id: str) -> None:
        """Remove a thought by ID."""
        self._dao.delete(thought_id)

    def recent(
        self,
        object_id: str | None = None,
        limit: int = 20,
    ) -> Sequence[Thought]:
        """Return recent thoughts."""
        return self._dao.list_recent(object_id=object_id, limit=limit)

    def by_session(self, session_id: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts from a session."""
        return self._dao.list_by_session(session_id=session_id, limit=limit)

    def by_memory_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> Sequence[Thought]:
        """Return thoughts of a memory type."""
        return self._dao.list_by_memory_type(memory_type=memory_type, limit=limit)

    def search(self, keyword: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts matching a keyword."""
        return self._dao.search_keyword(keyword=keyword, limit=limit)
