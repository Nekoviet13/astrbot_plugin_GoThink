"""Tests for thought DAO and repository persistence."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.models import MemoryType, Thought
from core.storage.dao import SQLiteThoughtDAO
from core.storage.repository import ThoughtRepository


class ThoughtStorageTest(unittest.TestCase):
    """Test SQLite thought storage behavior."""

    def test_repository_saves_and_gets_thought(self) -> None:
        """Saved thoughts should be returned unchanged."""
        with TemporaryDirectory() as tmp:
            repo = _repo(Path(tmp))
            thought = Thought(
                id="t1",
                session_id="s1",
                content="first memory",
                character="user",
                timestamp="2026-06-21T10:00:00",
                object_id="u1",
                memory_type=MemoryType.EPISODIC,
                metadata={"k": "v"},
            )

            saved = repo.save(thought)
            loaded = repo.get("t1")

            self.assertEqual(saved, thought)
            self.assertEqual(loaded, thought)

    def test_repository_recent_filters_by_object_id(self) -> None:
        """Recent queries should support object filtering."""
        with TemporaryDirectory() as tmp:
            repo = _repo(Path(tmp))
            repo.save(_thought("t1", "2026-06-21T10:00:00", "u1"))
            repo.save(_thought("t2", "2026-06-21T11:00:00", "u2"))
            repo.save(_thought("t3", "2026-06-21T12:00:00", "u1"))

            result = repo.recent(object_id="u1", limit=10)

            self.assertEqual([thought.id for thought in result], ["t3", "t1"])

    def test_repository_searches_keyword(self) -> None:
        """Keyword search should match thought content."""
        with TemporaryDirectory() as tmp:
            repo = _repo(Path(tmp))
            repo.save(_thought("t1", "2026-06-21T10:00:00", "u1", "alpha memory"))
            repo.save(_thought("t2", "2026-06-21T11:00:00", "u1", "beta note"))

            result = repo.search("alpha")

            self.assertEqual([thought.id for thought in result], ["t1"])

    def test_repository_updates_existing_thought(self) -> None:
        """Saving the same ID again should update the record."""
        with TemporaryDirectory() as tmp:
            repo = _repo(Path(tmp))
            repo.save(_thought("t1", "2026-06-21T10:00:00", "u1", "old"))
            updated = _thought("t1", "2026-06-21T10:00:00", "u1", "new")

            repo.save(updated)

            self.assertEqual(repo.get("t1"), updated)


def _repo(tmp_path: Path) -> ThoughtRepository:
    dao = SQLiteThoughtDAO(str(tmp_path / "thoughts.db"))
    dao.create_table()
    return ThoughtRepository(dao)


def _thought(
    thought_id: str,
    timestamp: str,
    object_id: str,
    content: str = "content",
) -> Thought:
    return Thought(
        id=thought_id,
        session_id="s1",
        content=content,
        character="user",
        timestamp=timestamp,
        object_id=object_id,
    )


if __name__ == "__main__":
    unittest.main()
