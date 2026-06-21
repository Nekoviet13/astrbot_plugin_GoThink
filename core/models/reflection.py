"""Reflection model for higher-level memory synthesis."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass(frozen=True)
class Reflection:
    """Immutable reflection generated from one or more thoughts."""

    id: str
    session_id: str
    content: str
    source_thought_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert this reflection to a storage-friendly dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "source_thought_ids": list(self.source_thought_ids),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Reflection":
        """Create a reflection from a dictionary."""
        return cls(
            id=str(data["id"]),
            session_id=str(data["session_id"]),
            content=str(data["content"]),
            source_thought_ids=list(data.get("source_thought_ids") or []),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or _now_iso()),
        )
