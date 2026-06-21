"""Tests for the thought domain model."""

import unittest
from dataclasses import FrozenInstanceError

from core.models import MemoryType, Thought


class ThoughtModelTest(unittest.TestCase):
    """Test immutable thought model behavior."""

    def test_thought_to_dict_round_trip(self) -> None:
        """Thought dictionaries should recreate the same entity."""
        thought = Thought(
            id="t1",
            session_id="s1",
            content="remember this",
            character="user",
            timestamp="2026-06-21T10:00:00",
            object_id="u1",
            importance=8,
            memory_type=MemoryType.SEMANTIC,
            metadata={"topic": "memory"},
            created_at="2026-06-21T10:00:00",
            updated_at="2026-06-21T10:00:00",
        )

        restored = Thought.from_dict(thought.to_dict())

        self.assertEqual(restored, thought)
        self.assertIs(restored.memory_type, MemoryType.SEMANTIC)
        self.assertEqual(restored.metadata, {"topic": "memory"})

    def test_thought_is_frozen(self) -> None:
        """Thought fields should not be assignable after construction."""
        thought = Thought(id="t1", session_id="s1", content="x", character="user")

        with self.assertRaises(FrozenInstanceError):
            thought.content = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
