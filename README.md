# GoThink 俺寻思

让 AstrBot 在 QQ 里拥有一套可持续演进的长期记忆。

GoThink 不是“聊天记录存档器”，而是一个正在成型的认知记忆框架。当前版本先完成最重要的第一步：把 QQ 对话稳定记录下来，并能在后续对话里按对象召回。

## 它现在能做什么

- 自动记录用户消息、AI 回复和工具调用
- 把记忆保存到 SQLite 数据库
- 在新会话开始时注入最近记忆
- 在用户提到“之前、记得、上次”等词时尝试自动召回
- 提供 QQ 内可用的查询命令
- 提供两个 LLM 工具：搜索记忆、写入记忆

一句话理解：

> 你和机器人说过的话，会被整理成“记忆条目”。以后你问“你还记得之前吗”，它就有机会把相关内容拿出来参考。

## 当前适用场景

本仓库当前按 QQ 使用场景优先设计。

所有 QQ 私聊和群聊共用同一个数据库文件，但每条记忆会记录自己的会话对象信息。召回时会按当前对象过滤，所以正常情况下：

- 私聊 A 不会读到私聊 B 的记忆
- 群 A 不会读到群 B 的记忆
- 所有记忆仍然统一存在一个 `thoughts.db` 里，方便备份和迁移

如果只在 QQ 上使用，对象 ID 串流概率很低，当前实现足够用于测试和日常试跑。后续多平台混用时，再升级为更严格的 `(object_type, object_id)` 或 `session_id` 复合隔离。

## 安装与启用

1. 将插件放入 AstrBot 的插件目录：

   ```text
   AstrBot/data/plugins/astrbot_plugin_GoThink
   ```

2. 在 AstrBot 控制台启用插件。

3. 日志里看到下面这行，说明加载成功：

   ```text
   [GoThink] loaded with SQLite storage: ...\GoThink\thoughts.db
   ```

4. 数据库默认保存到：

   ```text
   AstrBot/data/plugin_data/astrbot_plugin_GoThink/GoThink/thoughts.db
   ```

## 推荐配置

测试阶段建议这样配：

```json
{
  "enabled": true,
  "debug_mode": false,
  "memory_db_path": "GoThink/thoughts.db",
  "realtime_recording": true,
  "target_user_id_list": [],
  "username": "User",
  "ai_name": "Assistant",
  "auto_recall_probability": 1.0,
  "recent_injection_limit": 10
}
```

确认可用后，建议把 `auto_recall_probability` 改回 `0.3`。

配置项说明：

| 配置项 | 说明 |
| --- | --- |
| `enabled` | 是否启用 GoThink |
| `debug_mode` | 是否输出后台调试日志，开启后日志前缀为 `[GoThink:debug]` |
| `memory_db_path` | 记忆数据库路径，相对路径基于 AstrBot 插件数据目录 |
| `realtime_recording` | 是否实时记录对话 |
| `target_user_id_list` | 目标会话 ID 列表，留空表示记录所有会话 |
| `username` | 识别不到用户昵称时使用的默认名字 |
| `ai_name` | 记录 AI 回复时使用的名字 |
| `auto_recall_probability` | 每次请求自动尝试召回的概率 |
| `recent_injection_limit` | 新会话开始时最多注入多少条最近记忆 |

## QQ 内怎么验证

启动后，先在 QQ 里发几条普通消息：

```text
我正在测试 GoThink 记忆插件
请记住我喜欢用 AstrBot 做长期记忆
```

然后执行：

```text
/GoThink stats
```

再查看最近记忆：

```text
/GoThink recent
```

搜索关键词：

```text
/GoThink search AstrBot
```

如果能看到刚才发过的内容，说明记录和查询已经工作。

## 可用命令

| 命令 | 用途 |
| --- | --- |
| `/GoThink stats` | 查看当前会话的记忆状态 |
| `/GoThink recent` | 查看当前会话最近记忆 |
| `/GoThink recent 20` | 查看最近 20 条记忆 |
| `/GoThink search 关键词` | 在当前会话记忆里搜索关键词 |

## LLM 工具

GoThink 会向 AstrBot 注册两个函数调用工具：

| 工具 | 用途 |
| --- | --- |
| `recall_memory_tool` | 让模型主动搜索长期记忆 |
| `write_memory_tool` | 让模型主动写入一条明确记忆 |

你可以对机器人说：

```text
请记住：我的 GoThink 测试关键词是 blue-memory
```

然后再查：

```text
/GoThink search blue-memory
```

## 当前架构

当前代码已经按 GoThink v1.0 的冻结架构起步：

```text
main.py
  -> integrations/astrbot/
  -> core/storage/repository.py
  -> core/storage/dao/thought_dao.py
  -> SQLite
```

核心原则：

- `core/` 不依赖 AstrBot
- 模型使用不可变 dataclass
- Repository 返回 `Thought` 对象，不返回裸字典
- DAO 只做 SQLite CRUD
- `main.py` 负责组装依赖，是 Composition Root

## 目录结构

```text
astrbot_plugin_GoThink/
├── main.py
├── _conf_schema.json
├── metadata.yaml
├── core/
│   ├── common/
│   ├── interfaces/
│   ├── models/
│   └── storage/
├── integrations/
│   └── astrbot/
├── tests/
│   └── unit/
└── assets/
```

## 常见问题

### 插件加载成功，但 `/GoThink recent` 没有记忆

先检查：

- `realtime_recording` 是否为 `true`
- `target_user_id_list` 是否限制错了
- 是否在启用插件后才开始发消息

测试阶段建议 `target_user_id_list` 留空。

### 记忆会不会在所有群之间混用？

物理上共用一个数据库，逻辑上按当前对象过滤。只在 QQ 上使用时，一般不会串。

### 数据库在哪里？

默认在：

```text
AstrBot/data/plugin_data/astrbot_plugin_GoThink/GoThink/thoughts.db
```

### 报 `database is locked` 是 GoThink 的问题吗？

如果堆栈里是 AstrBot 的 `preferences` 表，多半是 AstrBot 主数据库被占用，不是 GoThink 的记忆库。通常关闭重复 AstrBot 进程、重启后再点一次启用即可。

### 为什么自动召回有时没触发？

当前自动召回由两种方式触发：

- 命中“之前、记得、上次”等关键词
- 命中 `auto_recall_probability` 概率

测试时可以把概率设为 `1.0`，确认工作后再调回 `0.3`。

## 开发状态

当前已完成：

- Phase 1 的模型、存储接口、SQLite DAO、Repository
- AstrBot 入口接入
- QQ 内命令验证路径
- 基础单元测试

后续计划：

- 提取器系统
- 多 Provider 召回
- 重要性评分
- 反思记忆
- 更严格的会话隔离策略
- FTS5/Embedding 检索

## 本地检查

运行单元测试：

```bash
python -m unittest discover -s tests
```

Ruff 检查与格式化：

```bash
ruff format .
ruff check --fix .
```

## 许可证

本项目使用 AGPL-3.0 许可证，详见 [LICENSE](LICENSE)。
