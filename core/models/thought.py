"""Thought model for the cognitive memory system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import MemoryType


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass(frozen=True)
class Thought:
    """Immutable thought or memory entity."""

    id: str
    session_id: str
    content: str
    character: str
    timestamp: str = field(default_factory=_now_iso)
    platform: str = ""
    object_type: str = ""
    object_id: str = ""
    importance: int | None = None
    memory_type: MemoryType = MemoryType.EPISODIC
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert this thought to a storage-friendly dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "character": self.character,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "importance": self.importance,
            "memory_type": self.memory_type.value,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Thought":
        """Create a thought from a dictionary."""
        memory_type = data.get("memory_type", MemoryType.EPISODIC)
        if isinstance(memory_type, str):
            memory_type = MemoryType(memory_type)

        return cls(
            id=str(data["id"]),
            session_id=str(data["session_id"]),
            content=str(data["content"]),
            character=str(data["character"]),
            timestamp=str(data.get("timestamp") or _now_iso()),
            platform=str(data.get("platform", "")),
            object_type=str(data.get("object_type", "")),
            object_id=str(data.get("object_id", "")),
            importance=data.get("importance"),
            memory_type=memory_type,
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )
