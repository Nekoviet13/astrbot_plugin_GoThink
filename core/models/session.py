"""Session model for grouping thoughts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass(frozen=True)
class Session:
    """Immutable conversation session entity."""

    id: str
    object_type: str
    object_id: str
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Convert this session to a storage-friendly dictionary."""
        return {
            "id": self.id,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "title": self.title,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create a session from a dictionary."""
        return cls(
            id=str(data["id"]),
            object_type=str(data["object_type"]),
            object_id=str(data["object_id"]),
            title=str(data.get("title", "")),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )
