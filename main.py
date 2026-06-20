import asyncio
import time
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_GoThink",
    "Nekoviet13",
    "让你的机器人在你不在的时候主动消化并搜索新内容",
    "v1.0.0",
    "https://github.com/Nekoviet13/astrbot_plugin_GoThink"
)
class GoThinkPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        
        self.idle_threshold = config.get("idle_threshold", 300)
        self.thinking_interval = config.get("thinking_interval", 600)
        self.max_thoughts = config.get("max_thoughts", 5)
        self.context_message_limit = config.get("context_message_limit", 5)  # ✅ 新增
        self.enabled = config.get("enabled", True)
        self.debug_mode = config.get("debug_mode", True)
        self.log_thoughts = config.get("log_thoughts", True)
        self.log_thoughts_path = config.get("log_thoughts_path", "./data/logs/gothink/thoughts.jsonl")
        
        self.last_user_activity = time.time()
        self.is_idle = False
        self.thinking_task: Optional[asyncio.Task] = None
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.thought_vault: List[dict] = []
        self.thought_count = 0
        self._active = True
        # 最近对话缓存
        self.context_cache = {}
# 当前思考目标
        self.focus_session_id = None

        # 每个会话的思维链
        self.thought_chains = {}
        
        if self.log_thoughts:
            self._init_log_file()
        
        logger.info("=" * 60)
        logger.info("[GoThink] 🚀 俺寻思插件已加载")
        logger.info(f"[GoThink] 空闲阈值: {self.idle_threshold}秒")
        logger.info(f"[GoThink] 思考间隔: {self.thinking_interval}秒")
        logger.info(f"[GoThink] 最大缓存思考数: {self.max_thoughts}")
        logger.info(f"[GoThink] 上下文参考条数: {self.context_message_limit}")  # ✅ 新增
        logger.info(f"[GoThink] 思考日志: {'开启' if self.log_thoughts else '关闭'}")
        if self.log_thoughts:
            logger.info(f"[GoThink] 日志路径: {self.log_thoughts_path}")
        logger.info("=" * 60)
        
        self._init_scheduler()
    
    def _init_log_file(self):
        try:
            log_path = Path(self.log_thoughts_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if not log_path.exists():
                log_path.touch()
                logger.info(f"[GoThink] 📁 创建思考日志文件: {log_path}")
            else:
                logger.info(f"[GoThink] 📁 思考日志文件已存在: {log_path}")
        except Exception as e:
            logger.error(f"[GoThink] ❌ 初始化日志文件失败: {e}")
            self.log_thoughts = False
    
    def _write_thought_to_log(self, thought: str):
        if not self.log_thoughts:
            return
        try:
            log_path = Path(self.log_thoughts_path)
            entry = {
                "id": f"t_{int(time.time())}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "content": thought,
                "character": "Nekoro"
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.debug(f"[GoThink] 💾 思考已写入日志: {entry['id']}")
        except Exception as e:
            logger.error(f"[GoThink] ❌ 写入思考日志失败: {e}")
    
    def _init_scheduler(self):
        try:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.add_job(
                self._idle_check_loop,
                'interval',
                seconds=30,
                id='gothink_idle_check',
                next_run_time=datetime.now()
            )
            self.scheduler.start()
            logger.info("[GoThink] ✅ 空闲检查调度器已启动 (间隔: 30秒)")
        except Exception as e:
            logger.error(f"[GoThink] ❌ 调度器启动失败: {e}")
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def track_activity(self, event: AstrMessageEvent):
        if not self.enabled or not self._active:
            return
        
        role = getattr(event, 'role', None)
        if role not in ['user', 'admin']:
            return
        
        message = event.message_str.strip() if event.message_str else ""
        if message.startswith('/'):
            return
        
        self.last_user_activity = time.time()
        logger.debug(f"[GoThink] 📩 收到用户消息")
        
        if message and not message.startswith('/'):
            self.last_topic_context = message[:200]

            session_id = getattr(event, "unified_msg_origin", None)

            if session_id:

                if self.focus_session_id is None:
                    self.focus_session_id = session_id

                if session_id not in self.context_cache:
                    self.context_cache[session_id] = deque(maxlen=20)

                self.context_cache[session_id].append({
                    "role": "user",
                    "content": message[:500]
                })

                if session_id not in self.thought_chains:
                    self.thought_chains[session_id] = []

                logger.debug(
                    f"[GoThink] 📚 缓存消息 | session={session_id} "
                    f"| count={len(self.context_cache[session_id])}"
                )

                logger.debug(
                    f"[GoThink] 📚 缓存消息 | session={session_id} "
                    f"| count={len(self.context_cache[session_id])}"
                )
        
        if self.is_idle and self.thought_vault:
            logger.info(f"[GoThink] 🔔 用户唤醒，准备注入 {len(self.thought_vault)} 条思考")
            await self._on_wake_up(event)
            self.focus_session_id = None
        
        if self.is_idle:
            self.is_idle = False
            logger.debug("[GoThink] 空闲状态已重置")
    
    async def _idle_check_loop(self):
        if not self.enabled or not self._active:
            return
        
        idle_time = time.time() - self.last_user_activity
        
        if idle_time >= self.idle_threshold and not self.is_idle:
            logger.info(f"[GoThink] 🟢 进入空闲状态 (已空闲 {idle_time:.1f}秒)")
            self.is_idle = True
            
            if not self.thinking_task or self.thinking_task.done():
                logger.info("[GoThink] 🧠 启动后台思考")
                self.thinking_task = asyncio.create_task(self._background_think())
    
    async def _background_think(self):
        cycle = 0
        logger.info("[GoThink] 🔄 后台思考循环开始")
        
        while self.is_idle and self._active and self.enabled:
            cycle += 1
            logger.info(f"[GoThink] 🧠 第 {cycle} 轮思考开始")
            
            try:
                thought = await self._generate_thought()
                if thought:
                    self._store_thought(thought)
                    self.thought_count += 1
                    logger.info(f"[GoThink] ✅ 思考完成 | 第 {self.thought_count} 条")
                    logger.debug(f"[GoThink] 📝 内容: {thought[:80]}...")
                else:
                    logger.warning("[GoThink] ⚠️ 思考生成失败")
            except Exception as e:
                logger.error(f"[GoThink] ❌ 思考出错: {e}")
            
            logger.debug(f"[GoThink] ⏳ 等待 {self.thinking_interval} 秒")
            await asyncio.sleep(self.thinking_interval)
        
        logger.info("[GoThink] 🔄 后台思考循环结束")
    
    async def _get_recent_context(self) -> str:
        """
        获取最近上下文
        优先使用实时缓存
        """

        try:
            if not self.last_session_id:
                return "（没有最近的对话内容）"

            history = self.context_cache.get(
                self.focus_session_id,
                None
            )

            if not history:
                return "（没有最近的对话内容）"

            lines = []

            for msg in list(history)[-self.context_message_limit:]:
                role = "用户"

                lines.append(
                    f"{role}：{msg['content']}"
                )

            context = "\n".join(lines)

            logger.debug(
                f"[GoThink] 📖 获取上下文成功:\n{context}"
            )

            return context

        except Exception as e:
            logger.error(
                f"[GoThink] ❌ 获取上下文失败: {e}"
            )

            return "（没有最近的对话内容）"
    
    async def _generate_thought(self) -> Optional[str]:
        provider = self.context.get_using_provider()
        if not provider:
            logger.warning("[GoThink] ⚠️ 未找到 LLM 提供商")
            return None

        recent_context = await self._get_recent_context()
        previous_thoughts = []

        if self.focus_session_id:
            previous_thoughts = self.thought_chains.get(
                self.focus_session_id,
                []
            )[-3:]
        previous_context = "\n".join(previous_thoughts)
        
        system_prompt = """
你是一个后台思维引擎。

你的任务：

根据用户最近的聊天内容，
在用户离开期间继续联想。

目标：

发现新的聊天方向，
帮助下一轮对话更加自然。

规则：

1. 必须基于最近聊天内容
2. 不允许讨论AI
3. 不允许讨论思考本身
4. 不允许讨论自己正在思考
5. 必须具体
6. 必须围绕实际话题

输出格式：

主题：
（当前主要话题）

延伸：
（1~3个值得继续聊的方向）

想法：
（一个具体的新角度）
"""

        user_prompt = f"""
最近聊天内容：

{recent_context}

之前已经产生的思考：

{previous_context}

要求：

1. 继续深化之前的思考
2. 不要重复已有内容
3. 不要重新总结聊天
4. 必须提出新的观察

输出：

主题：
延伸：
想法：
"""

        try:
            response = await provider.text_chat(
                prompt=user_prompt,
                system_prompt=system_prompt,
                contexts=[],
                temperature=0.8
            )
            
            if response and response.completion_text:
                return response.completion_text.strip()
            return None
            
        except Exception as e:
            logger.error(f"[GoThink] ❌ LLM 调用失败: {e}")
            return None
    
    def _store_thought(self, thought: str):
        entry = {
            "id": f"t_{int(time.time())}",
            "content": thought,
            "presented": False
        }
        self.thought_vault.append(entry)
        if self.focus_session_id:

            if self.focus_session_id not in self.thought_chains:
                self.thought_chains[self.focus_session_id] = []

            self.thought_chains[
                self.focus_session_id
            ].append(thought)

            self.thought_chains[
                self.focus_session_id
            ] = self.thought_chains[
                self.focus_session_id
            ][-10:]
        self._write_thought_to_log(thought)
        
        if len(self.thought_vault) > self.max_thoughts:
            removed = self.thought_vault.pop(0)
            logger.debug(f"[GoThink] 🗑️ 移除旧思考: {removed['id']}")
        
        logger.debug(f"[GoThink] 💾 当前缓存: {len(self.thought_vault)} 条")
    
    async def _on_wake_up(self, event: AstrMessageEvent):
        if not self.thought_vault:
            return
        
        thoughts = self.thought_vault[-3:]
        event.set_extra("gothink_thoughts", [t["content"] for t in thoughts if not t.get("presented")])
        
        for t in thoughts:
            t["presented"] = True
        
        logger.info(f"[GoThink] 📤 已注入 {len(thoughts)} 条思考到上下文")
    
    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req):
        thoughts = event.get_extra("gothink_thoughts")
        if not thoughts:
            return
        
        injection = "\n\n【你在后台的思考】\n" + "\n".join([f"- {t}" for t in thoughts])
        req.system_prompt += injection
        
        logger.debug(f"[GoThink] 📤 已注入 {len(thoughts)} 条思考到系统提示词")
        event.set_extra("gothink_thoughts", None)
    
    @filter.command("gothink_status")
    async def status_command(self, event: AstrMessageEvent):
        status = f"""📊 GoThink 俺寻思状态
━━━━━━━━━━━━━━━━━━━━
当前状态: {'🟢 运行中' if self.enabled else '🔴 已暂停'}
空闲状态: {'💤 空闲中' if self.is_idle else '🟢 活跃中'}
思考计数: {self.thought_count} 条
缓存思考: {len(self.thought_vault)} 条
━━━━━━━━━━━━━━━━━━━━
/gothink_status - 查看此状态
/gothink_toggle - 启用/禁用"""
        yield event.plain_result(status)
    
    @filter.command("gothink_toggle")
    async def toggle_command(self, event: AstrMessageEvent):
        self.enabled = not self.enabled
        status = "✅ 已启用" if self.enabled else "⛔ 已禁用"
        logger.info(f"[GoThink] 状态切换: {status}")
        yield event.plain_result(f"GoThink 俺寻思: {status}")
    
    @filter.command("gothink_peek")
    async def peek_thoughts(self, event: AstrMessageEvent):
        if not self.thought_vault:
            yield event.plain_result("💭 当前没有缓存的思考内容")
            return
        
        result = "💭 最近的思考内容：\n"
        for i, t in enumerate(self.thought_vault[-3:], 1):
            content = t['content']
            if len(content) > 100:
                content = content[:100] + "..."
            result += f"{i}. {content}\n"
        
        yield event.plain_result(result)
    
    async def terminate(self):
        self._active = False
        self.enabled = False
        if self.scheduler:
            try:
                self.scheduler.shutdown()
            except Exception:
                pass
        if self.thinking_task and not self.thinking_task.done():
            self.thinking_task.cancel()
        logger.info("[GoThink] 插件已卸载")