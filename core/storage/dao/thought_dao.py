"""SQLite DAO for thought CRUD operations."""

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ...models import Thought
from ...models.enums import MemoryType


class SQLiteThoughtDAO:
    """SQLite implementation of the thought DAO port."""

    def __init__(self, db_path: str) -> None:
        """Initialize the DAO with a database path."""
        self.db_path = db_path

    def create_table(self) -> None:
        """Create the thoughts table if it does not exist."""
        self._ensure_parent()
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thoughts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    character TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    platform TEXT NOT NULL DEFAULT '',
                    object_type TEXT NOT NULL DEFAULT '',
                    object_id TEXT NOT NULL DEFAULT '',
                    importance INTEGER,
                    memory_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thoughts_timestamp "
                "ON thoughts(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thoughts_session "
                "ON thoughts(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thoughts_object ON thoughts(object_id)"
            )

    def insert(self, thought: Thought) -> None:
        """Insert a thought record."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO thoughts (
                    id, session_id, content, character, timestamp,
                    platform, object_type, object_id, importance,
                    memory_type, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(thought),
            )

    def update(self, thought: Thought) -> None:
        """Update an existing thought record."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE thoughts
                SET session_id = ?, content = ?, character = ?, timestamp = ?,
                    platform = ?, object_type = ?, object_id = ?,
                    importance = ?, memory_type = ?, metadata = ?,
                    created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    thought.session_id,
                    thought.content,
                    thought.character,
                    thought.timestamp,
                    thought.platform,
                    thought.object_type,
                    thought.object_id,
                    thought.importance,
                    thought.memory_type.value,
                    json.dumps(thought.metadata, ensure_ascii=False),
                    thought.created_at,
                    thought.updated_at,
                    thought.id,
                ),
            )

    def delete(self, thought_id: str) -> None:
        """Delete a thought record by ID."""
        with self._connection() as conn:
            conn.execute("DELETE FROM thoughts WHERE id = ?", (thought_id,))

    def get_by_id(self, thought_id: str) -> Thought | None:
        """Return one thought by ID if it exists."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM thoughts WHERE id = ?",
                (thought_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_recent(
        self,
        object_id: str | None = None,
        limit: int = 20,
    ) -> Sequence[Thought]:
        """Return recent thoughts ordered by timestamp descending."""
        if object_id:
            sql = (
                "SELECT * FROM thoughts WHERE object_id = ? "
                "ORDER BY timestamp DESC LIMIT ?"
            )
            params: tuple[Any, ...] = (object_id, limit)
        else:
            sql = "SELECT * FROM thoughts ORDER BY timestamp DESC LIMIT ?"
            params = (limit,)

        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_session(self, session_id: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts for one session ordered by timestamp descending."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM thoughts
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_memory_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> Sequence[Thought]:
        """Return thoughts for one memory type ordered by timestamp descending."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM thoughts
                WHERE memory_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (memory_type.value, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def search_keyword(self, keyword: str, limit: int = 50) -> Sequence[Thought]:
        """Return thoughts containing a keyword."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM thoughts
                WHERE content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{keyword}%", limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_parent(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _to_row(self, thought: Thought) -> tuple[Any, ...]:
        return (
            thought.id,
            thought.session_id,
            thought.content,
            thought.character,
            thought.timestamp,
            thought.platform,
            thought.object_type,
            thought.object_id,
            thought.importance,
            thought.memory_type.value,
            json.dumps(thought.metadata, ensure_ascii=False),
            thought.created_at,
            thought.updated_at,
        )

    def _from_row(self, row: sqlite3.Row) -> Thought:
        return Thought.from_dict(
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "content": row["content"],
                "character": row["character"],
                "timestamp": row["timestamp"],
                "platform": row["platform"],
                "object_type": row["object_type"],
                "object_id": row["object_id"],
                "importance": row["importance"],
                "memory_type": row["memory_type"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
