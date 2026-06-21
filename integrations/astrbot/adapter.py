"""AstrBot adapter helpers for GoThink."""

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from astrbot.api import logger
from astrbot.api.provider import ProviderRequest
from astrbot.core.conversation_mgr import Conversation

from ...core.models import Thought


RECALL_KEYWORDS = (
    "之前",
    "记得",
    "回忆",
    "想起",
    "以前",
    "过去",
    "曾经",
    "刚才",
    "上次",
)


class AstrBotMemoryAdapter:
    """Reusable AstrBot memory behavior for the registered plugin."""

    def _resolve_path(self, path_str: str, base_dir: Path) -> Path:
        """Resolve a configured path against AstrBot's data directory."""
        path = Path(path_str)
        if path.is_absolute():
            return path
        return (base_dir / path).resolve()

    def _should_handle_user(self, unified_id: Optional[str]) -> bool:
        """Return whether GoThink should process this conversation."""
        if not self.enabled or not unified_id:
            return False
        return not self.target_user_id_list or unified_id in self.target_user_id_list

    def _get_unified_id(self, event: Any) -> Optional[str]:
        """Extract AstrBot's unified conversation ID from an event."""
        actual_event = getattr(event, "event", event)
        for attr in ("unified_id", "unified_msg_origin"):
            value = getattr(actual_event, attr, None)
            if value:
                return str(value)

        get_unified_id = getattr(actual_event, "get_unified_id", None)
        if callable(get_unified_id):
            try:
                value = get_unified_id()
                if value:
                    return str(value)
            except Exception:
                logger.debug("[GoThink] failed to call get_unified_id", exc_info=True)

        message_obj = getattr(actual_event, "message_obj", None)
        sender = getattr(message_obj, "sender", None)
        user_id = getattr(sender, "user_id", None)
        platform = getattr(message_obj, "platform", "")
        if user_id:
            return f"{platform}:{user_id}" if platform else str(user_id)
        return None

    def _get_sender_name(self, event: Any) -> str:
        """Extract a display name for a message sender."""
        actual_event = getattr(event, "event", event)
        get_sender_name = getattr(actual_event, "get_sender_name", None)
        if callable(get_sender_name):
            try:
                value = get_sender_name()
                if value:
                    return str(value)
            except Exception:
                logger.debug("[GoThink] failed to call get_sender_name", exc_info=True)

        sender = getattr(getattr(actual_event, "message_obj", None), "sender", None)
        for attr in ("nickname", "name", "card", "user_id"):
            value = getattr(sender, attr, None)
            if value:
                return str(value)
        return self.username

    def _parse_object_info(self, unified_id: Optional[str]) -> tuple[str, str]:
        """Parse object type and object ID from a unified ID."""
        if not unified_id:
            return "unknown", "unknown"
        parts = unified_id.split(":")
        if len(parts) >= 3:
            return parts[0].lower(), parts[-1]
        if len(parts) == 2:
            return parts[0].lower(), parts[1]
        return "unknown", unified_id

    def _plain_text(self, event: Any) -> str:
        """Extract plain message text from an event."""
        actual_event = getattr(event, "event", event)
        get_plain_text = getattr(actual_event, "get_plain_text", None)
        if callable(get_plain_text):
            return str(get_plain_text() or "")
        return str(getattr(actual_event, "message_str", "") or "")

    def _record_thought(
        self,
        unified_id: str,
        character: str,
        content: str,
        importance: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Thought]:
        """Persist one conversation thought."""
        content = content.strip()
        if not content:
            return None

        object_type, object_id = self._parse_object_info(unified_id)
        now = self.clock.now_iso()
        thought = Thought(
            id=self.id_generator.new_id("t_"),
            session_id=unified_id,
            content=content,
            character=character,
            timestamp=now,
            platform=object_type,
            object_type=object_type,
            object_id=object_id,
            importance=importance,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        return self.thought_repository.save(thought)

    def _format_recall_block(
        self,
        title: str,
        thoughts: Sequence[Thought],
        limit: int,
    ) -> str:
        """Format thoughts for prompt injection."""
        lines = [f"\n\n【{title}】"]
        for thought in thoughts[:limit]:
            lines.append(
                f"- {self._short_time(thought.timestamp)} | "
                f"{thought.character}: {thought.content[:160]}"
            )
        return "\n".join(lines)

    def _format_public_list(self, thoughts: Iterable[Thought]) -> str:
        """Format thoughts for command output."""
        lines = []
        for thought in thoughts:
            topic = thought.metadata.get("topic", "")
            suffix = f" [#{topic}]" if topic else ""
            lines.append(
                f"{self._short_time(thought.timestamp)} | "
                f"{thought.character}: {thought.content[:120]}{suffix}"
            )
        return "\n".join(lines)

    def _short_time(self, value: str) -> str:
        """Format an ISO timestamp for compact display."""
        try:
            return datetime.fromisoformat(value).strftime("%m-%d %H:%M")
        except ValueError:
            return "unknown time"

    def _extract_topic(self, content: str) -> str:
        """Extract a simple hash-tag topic from content."""
        match = re.search(r"#([^\s#]+)", content)
        return match.group(1) if match else ""

    def _search_relevant(self, object_id: str, query: str, limit: int) -> Sequence[Thought]:
        """Search relevant memories for one object."""
        words = [word for word in re.split(r"\s+", query.strip()) if word]
        keyword = max(words, key=len) if words else query.strip()
        return [
            thought
            for thought in self.thought_repository.search(keyword, limit=limit * 3)
            if thought.object_id == object_id
        ][:limit]

    async def _is_new_conversation(self, event: Any, unified_id: str) -> bool:
        """Return whether the current AstrBot conversation appears empty."""
        actual_event = getattr(event, "event", event)
        uid = getattr(actual_event, "unified_msg_origin", None) or unified_id
        conv_mgr = getattr(self.context, "conversation_manager", None)
        if not conv_mgr or not uid:
            return False

        current_id = await conv_mgr.get_curr_conversation_id(uid)
        if current_id is None:
            return True

        conversation: Conversation = await conv_mgr.get_conversation(uid, current_id)
        return not conversation or not conversation.history or conversation.history == "[]"

    def _provider_request(
        self,
        args: Sequence[Any],
        kwargs: Dict[str, Any],
    ) -> Optional[ProviderRequest]:
        """Find AstrBot's ProviderRequest in callback arguments."""
        req = kwargs.get("req")
        if isinstance(req, ProviderRequest):
            return req
        for arg in args:
            if isinstance(arg, ProviderRequest):
                return arg
        return None

    def _tool_call_text(self, args: Sequence[Any], kwargs: Dict[str, Any]) -> str:
        """Format a tool call response into memory text."""
        tool_name = kwargs.get("tool_name") or (args[0] if args else "unknown")
        tool_args = kwargs.get("args") or (args[1] if len(args) > 1 else {})
        try:
            args_text = json.dumps(tool_args, ensure_ascii=False)
        except TypeError:
            args_text = str(tool_args)
        return f"(tool) {tool_name}: {args_text[:200]}"

    def _should_auto_recall(self, text: str) -> bool:
        """Return whether a request should trigger automatic memory recall."""
        hit_keyword = any(keyword in text for keyword in RECALL_KEYWORDS)
        hit_probability = random.random() <= self.auto_recall_probability
        return hit_keyword or hit_probability
