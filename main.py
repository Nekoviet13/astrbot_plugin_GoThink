"""AstrBot composition root for GoThink."""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

from .core.common import SystemClock, UUIDGenerator
from .core.storage.dao import SQLiteThoughtDAO
from .core.storage.repository import ThoughtRepository
from .integrations.astrbot.adapter import AstrBotMemoryAdapter


@register(
    "astrbot_plugin_GoThink",
    "Nekoviet13",
    "GoThink cognitive memory framework",
    "v1.0.0",
    "https://github.com/Nekoviet13/astrbot_plugin_GoThink",
)
class GoThinkPlugin(AstrBotMemoryAdapter, Star):
    """AstrBot plugin entrypoint and GoThink dependency composer."""

    def __init__(self, context: Context, config: Optional[Dict[str, Any]] = None):
        """Create GoThink infrastructure and wire runtime dependencies."""
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self.clock = SystemClock()
        self.id_generator = UUIDGenerator()

        data_dir = self._plugin_data_dir()
        db_path = self._resolve_path(
            self.config.get("memory_db_path", "GoThink/thoughts.db"),
            data_dir,
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.thought_dao = SQLiteThoughtDAO(str(db_path))
        self.thought_dao.create_table()
        self.thought_repository = ThoughtRepository(self.thought_dao)

        self.enabled = bool(self.config.get("enabled", True))
        self.realtime_recording = bool(self.config.get("realtime_recording", True))
        self.target_user_id_list = set(self.config.get("target_user_id_list", []))
        self.username = str(self.config.get("username", "User"))
        self.ai_name = str(self.config.get("ai_name", "Assistant"))
        self.auto_recall_probability = float(
            self.config.get("auto_recall_probability", 0.3)
        )
        self.recent_injection_limit = int(self.config.get("recent_injection_limit", 10))

        logger.info("[GoThink] loaded with SQLite storage: %s", db_path)

    def _plugin_data_dir(self) -> Path:
        """Return AstrBot's plugin data directory with a local fallback."""
        try:
            return StarTools.get_data_dir()
        except RuntimeError as error:
            fallback = Path(__file__).resolve().parent / "data"
            logger.warning(
                "[GoThink] failed to get AstrBot data dir, using %s: %s",
                fallback,
                error,
            )
            return fallback

    @filter.on_llm_request()
    async def on_llm_request(self, event: Any, *args: Any, **kwargs: Any) -> None:
        """Record user input and inject relevant memory before LLM generation."""
        unified_id = self._get_unified_id(event)
        if not self._should_handle_user(unified_id):
            return

        text = self._plain_text(event)
        if self.realtime_recording and text:
            self._record_thought(
                unified_id=unified_id,
                character=self._get_sender_name(event),
                content=text,
                metadata={"topic": self._extract_topic(text)},
            )

        req = self._provider_request(args, kwargs)
        if not req or not text:
            return

        _, object_id = self._parse_object_info(unified_id)
        if await self._is_new_conversation(event, unified_id):
            recent = self.thought_repository.recent(
                object_id=object_id,
                limit=self.recent_injection_limit,
            )
            if recent:
                req.system_prompt += self._format_recall_block(
                    "历史记忆 - 最近对话回顾",
                    recent,
                    self.recent_injection_limit,
                )

        clean_text = re.sub(r"<system_reminder>.*?</system_reminder>", "", text)
        if self._should_auto_recall(clean_text):
            related = self._search_relevant(object_id, clean_text, limit=5)
            if related:
                req.system_prompt += self._format_recall_block(
                    "自动回想 - 相关记忆片段",
                    related,
                    3,
                )

    @filter.on_llm_response()
    async def on_llm_response(self, event: Any, *args: Any, **kwargs: Any) -> None:
        """Record assistant responses after LLM generation."""
        if not self.realtime_recording:
            return

        unified_id = self._get_unified_id(event)
        if not self._should_handle_user(unified_id):
            return

        resp = kwargs.get("resp") or (args[0] if args else getattr(event, "resp", None))
        if not resp:
            return

        extra = getattr(resp, "extra", {})
        if isinstance(extra, dict):
            thinking = extra.get("think", "") or extra.get("reasoning", "")
            if thinking:
                self._record_thought(unified_id, self.ai_name, f"(thinking) {thinking}")

        text = str(getattr(resp, "completion_text", "") or "").strip()
        if text:
            self._record_thought(unified_id, self.ai_name, text)

    @filter.on_llm_tool_respond()
    async def on_llm_tool_respond(self, event: Any, *args: Any, **kwargs: Any) -> None:
        """Record tool calls as assistant-side operational memories."""
        if not self.realtime_recording:
            return

        unified_id = self._get_unified_id(event)
        if self._should_handle_user(unified_id):
            self._record_thought(unified_id, self.ai_name, self._tool_call_text(args, kwargs))

    @filter.command_group("GoThink")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def gothink_group(self) -> None:
        """GoThink maintenance and recall command group."""

    @gothink_group.command("recent")
    async def recall_recent_command(self, event: AstrMessageEvent) -> None:
        """Show recent memories for the current conversation."""
        args = event.message_str.strip().split()
        limit = int(args[2]) if len(args) > 2 and args[2].isdigit() else 10
        unified_id = self._get_unified_id(event)
        _, object_id = self._parse_object_info(unified_id)
        thoughts = self.thought_repository.recent(object_id=object_id, limit=limit)
        if not thoughts:
            yield event.plain_result("还没有找到记忆。")
            return
        yield event.plain_result(self._format_public_list(thoughts))

    @gothink_group.command("search")
    async def recall_search_command(self, event: AstrMessageEvent) -> None:
        """Search memories for the current conversation."""
        query = re.sub(r"^/?GoThink\s+search\s*", "", event.message_str).strip()
        if not query:
            yield event.plain_result("请输入要搜索的关键词。")
            return

        unified_id = self._get_unified_id(event)
        _, object_id = self._parse_object_info(unified_id)
        thoughts = self._search_relevant(object_id, query, limit=20)
        if not thoughts:
            yield event.plain_result(f"没有找到包含「{query}」的记忆。")
            return
        yield event.plain_result(self._format_public_list(thoughts))

    @gothink_group.command("stats")
    async def stats_command(self, event: AstrMessageEvent) -> None:
        """Show lightweight memory storage statistics."""
        unified_id = self._get_unified_id(event)
        _, object_id = self._parse_object_info(unified_id)
        recent_count = len(self.thought_repository.recent(object_id=object_id, limit=100))
        yield event.plain_result(f"GoThink 已启用。当前会话最近可读记忆数：{recent_count}")

    @llm_tool(name="recall_memory_tool")
    async def recall_memory_tool(
        self,
        event: AstrMessageEvent,
        query: str = "",
        count: int = 5,
    ) -> str:
        """Search long-term memory for relevant thoughts."""
        if not query:
            return "需要提供 query。"

        unified_id = self._get_unified_id(event)
        _, object_id = self._parse_object_info(unified_id)
        thoughts = self._search_relevant(object_id, query, limit=count)
        if not thoughts:
            return "暂时没有找到相关记忆。"
        return self._format_public_list(thoughts)

    @llm_tool(name="write_memory_tool")
    async def write_memory_tool(
        self,
        event: AstrMessageEvent,
        content: str,
        topic: str = "",
    ) -> str:
        """Write one explicit memory into GoThink."""
        if not content.strip():
            return "content 不能为空。"

        unified_id = self._get_unified_id(event)
        if not unified_id:
            return "无法识别当前会话。"

        metadata = {"topic": topic.strip()} if topic.strip() else {}
        thought = self._record_thought(unified_id, self.username, content, 7, metadata)
        return f"已记住：{thought.content[:80]}" if thought else "没有写入任何内容。"

    async def terminate(self) -> None:
        """Handle plugin unload."""
        logger.info("[GoThink] unloaded")
