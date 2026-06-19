import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
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
        
        # ---- 配置项 ----
        self.idle_threshold = config.get("idle_threshold", 300)
        self.thinking_interval = config.get("thinking_interval", 600)
        self.max_thoughts = config.get("max_thoughts", 5)
        self.context_message_limit = config.get("context_message_limit", 5)
        self.enabled = config.get("enabled", True)
        self.debug_mode = config.get("debug_mode", True)
        self.log_thoughts = config.get("log_thoughts", True)
        self.log_thoughts_path = config.get("log_thoughts_path", "./data/logs/gothink/thoughts.jsonl")
        
        # ---- 状态变量 ----
        self.last_user_activity = time.time()
        self.is_idle = False
        self.thinking_task: Optional[asyncio.Task] = None
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.thought_vault: list = []
        self.thought_count = 0
        self._active = True
        
        # ---- 初始化日志文件 ----
        if self.log_thoughts:
            self._init_log_file()
        
        logger.info("=" * 60)
        logger.info("[GoThink] 🚀 俺寻思插件已加载")
        logger.info(f"[GoThink] 空闲阈值: {self.idle_threshold}秒")
        logger.info(f"[GoThink] 思考间隔: {self.thinking_interval}秒")
        logger.info(f"[GoThink] 最大缓存思考数: {self.max_thoughts}")
        logger.info(f"[GoThink] 上下文消息条数: {self.context_message_limit}")
        logger.info(f"[GoThink] 思考日志: {'开启' if self.log_thoughts else '关闭'}")
        if self.log_thoughts:
            logger.info(f"[GoThink] 日志路径: {self.log_thoughts_path}")
        logger.info("=" * 60)
        
        self._init_scheduler()
    
    def _init_log_file(self):
        """初始化思考日志文件"""
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
        """将思考内容写入日志文件"""
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
        
        if self.is_idle and self.thought_vault:
            logger.info(f"[GoThink] 🔔 用户唤醒，准备注入 {len(self.thought_vault)} 条思考")
            await self._on_wake_up(event)
        
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
        """获取最近的对话上下文，只取用户消息"""
        limit = self.context_message_limit
        
        try:
            # 方法1：从 conversation_manager 获取
            conv_mgr = self.context.conversation_manager
            if conv_mgr:
                session_id = getattr(self.context, 'unified_msg_origin', None)
                if session_id:
                    cid = await conv_mgr.get_curr_conversation_id(session_id)
                    if cid:
                        conv = await conv_mgr.get_conversation(session_id, cid)
                        if conv and conv.history:
                            history = json.loads(conv.history) if isinstance(conv.history, str) else conv.history
                            if history:
                                user_messages = []
                                for msg in history[-20:]:  # 多取一些，确保够用
                                    if msg.get('role') == 'user':
                                        content = msg.get('message', '')
                                        if content and len(content) > 0:
                                            user_messages.append(content[:300])
                                if user_messages:
                                    # 取最后 limit 条
                                    selected = user_messages[-limit:] if len(user_messages) > limit else user_messages
                                    return "用户说：\n" + "\n".join(selected)
        except Exception as e:
            logger.debug(f"[GoThink] 方法1获取上下文失败: {e}")
        
        try:
            # 方法2：直接从 context 的 _conversation_history 获取
            if hasattr(self.context, '_conversation_history'):
                history = self.context._conversation_history
                if history:
                    user_messages = []
                    for msg in history[-20:]:
                        if msg.get('role') == 'user':
                            content = msg.get('message', '')
                            if content and len(content) > 0:
                                user_messages.append(content[:300])
                    if user_messages:
                        selected = user_messages[-limit:] if len(user_messages) > limit else user_messages
                        return "用户说：\n" + "\n".join(selected)
        except Exception as e:
            logger.debug(f"[GoThink] 方法2获取上下文失败: {e}")
        
        return "（没有最近的对话内容）"
    
    async def _generate_thought(self) -> Optional[str]:
        provider = self.context.get_using_provider()
        if not provider:
            logger.warning("[GoThink] ⚠️ 未找到 LLM 提供商")
            return None

        recent_context = await self._get_recent_context()
        
        system_prompt = """你是一个善于思考的AI助手，名叫Nekoro。

你的任务是围绕**用户最近的对话内容**进行思考，而不是思考"思考本身"。

强制规则：
1. 你的思考必须基于用户最近说的具体话题展开
2. 如果用户说了具体内容（如"晚上吃什么"），你的思考要围绕这个话题展开
3. 禁止谈论AI、思考的本质、元认知等抽象话题
4. 禁止分析用户意图
5. 思考要自然、有温度，像一个人在心里琢磨事情

思考方向示例：
- 如果用户说"晚上吃什么" → 思考ta可能喜欢的口味、推荐什么食物、有什么故事
- 如果用户说"今天好累" → 思考ta经历了什么、怎么放松、有什么小建议
- 如果用户说"随便" → 思考ta可能想随意聊聊、或者不太确定自己想要什么

请基于用户最近的具体话题进行思考，直接输出想法。"""

        user_prompt = f"""用户最近的对话内容：
{recent_context}

请基于以上内容，进行贴近话题的、自然的思考。"""

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
        
        # 写入磁盘
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
        """查看最近的思考内容。用法：/gothink_peek"""
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