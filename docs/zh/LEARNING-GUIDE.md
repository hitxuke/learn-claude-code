# 学习路径指南 - 如何使用本仓库

> 本指南将帮助你一步一步学习 Agent (智能体) Harness (工具架) 工程。

## 目录

1. [前置准备](#1-前置准备)
2. [学习路径概览](#2-学习路径概览)
3. [第一阶段：核心循环](#3-第一阶段核心循环)
4. [第二阶段：规划与知识](#4-第二阶段规划与知识)
5. [第三阶段：持久化](#5-第三阶段持久化)
6. [第四阶段：团队协作](#6-第四阶段团队协作)
7. [实战项目](#7-实战项目)
8. [常见问题](#8-常见问题)

---

## 1. 前置准备

### 1.1 环境要求

- Python 3.11+
- Node.js 20+
- Anthropic API Key (或其他兼容 API)

### 1.2 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/shareAI-lab/learn-claude-code
cd learn-claude-code

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 Web 平台依赖 (可选，但推荐)
cd web && npm install && cd ..

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 1.3 快速验证

```bash
# 验证 Python 环境
python agents/s01_agent_loop.py
# 输入 "你好" 测试是否正常运行

# 验证 Web 平台 (可选)
cd web && npm run dev
# 访问 http://localhost:3000
```

---

## 2. 学习路径概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        学习路径总览                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  第一阶段：核心循环                    第二阶段：规划与知识            │
│  ═══════════════════                  ════════════════════          │
│  s01 Agent Loop              [1]       s03 TodoWrite        [5]     │
│       while + stop_reason               TodoManager + nag reminder  │
│       │                                   │                         │
│       +-> s02 Tool Use          [4]      +-> s04 Subagents    [5]   │
│                dispatch map                          fresh messages[] │
│                                                 │                    │
│                                            s05 Skills         [5]    │
│                                                 SKILL.md via        │
│                                                 tool_result         │
│                                                 │                    │
│                                            s06 Context Compact [5]  │
│                                                 3-layer compression  │
│                                                                     │
│  第三阶段：持久化                    第四阶段：团队协作                │
│  ═══════════════════                  ══════════════════════        │
│  s07 Tasks                    [8]      s09 Agent Teams      [9]     │
│       file-based CRUD + deps          teammates + JSONL mailboxes  │
│       │                               │                           │
│  s08 Background Tasks         [6]      s10 Team Protocols   [12]   │
│       daemon threads + notify          shutdown + plan approval    │
│                                    │                               │
│                               s11 Autonomous Agents    [14]        │
│                                    idle cycle + auto-claim        │
│                               │                                   │
│                               s12 Worktree Isolation    [16]        │
│                                    task coordination + isolated   │
│                                    execution lanes                 │
│                                                                     │
│  [N] = 工具数量                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 第一阶段：核心循环

### s01 - The Agent Loop (智能体循环)

**核心概念**: 理解 Agent 的本质 -- 一个 while 循环 + stop_reason 控制

**学习目标**:
- 理解 `stop_reason == "tool_use"` 的含义
- 掌握消息列表的追加模式
- 理解循环如何驱动 Agent 自主行动

**代码位置**: `agents/s01_agent_loop.py`

**学习步骤**:

1. **阅读** `docs/zh/s01-the-agent-loop.md`
2. **运行** `python agents/s01_agent_loop.py`
3. **理解** 核心循环逻辑：

```python
def agent_loop(messages):
    while True:
        # 1. 调用 LLM
        response = client.messages.create(model=MODEL, messages=messages, tools=TOOLS)
        
        # 2. 追加助手响应
        messages.append({"role": "assistant", "content": response.content})
        
        # 3. 检查停止条件
        if response.stop_reason != "tool_use":
            return  # 模型停止，退出循环
        
        # 4. 执行工具
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        
        # 5. 追加结果，继续循环
        messages.append({"role": "user", "content": results})
```

**练习**:
- 修改 prompt，观察 Agent 的行为变化
- 添加一个新工具（如 `read_file`）

---

### s02 - Tool Use (工具使用)

**核心概念**: 添加工具 = 添加一个 handler，循环不变

**学习目标**:
- 掌握 `TOOL_HANDLERS` 分派模式
- 理解工具定义的 JSON Schema

**代码位置**: `agents/s02_tool_use.py`

**学习步骤**:

1. **阅读** `docs/zh/s02-tool-use.md`
2. **对比** s01 和 s02 的代码差异
3. **理解** 分派模式：

```python
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"]),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    # 新工具只需添加一个映射
}

def handle_tool_call(block):
    handler = TOOL_HANDLERS.get(block.name)
    if handler:
        return handler(**block.input)
    return f"Unknown: {block.name}"
```

**练习**:
- 为 Agent 添加一个 `glob` 工具
- 实现一个简单的文件搜索功能

---

## 4. 第二阶段：规划与知识

### s03 - TodoWrite (任务规划)

**核心概念**: Agent 没有计划就会迷失方向

**学习目标**:
- 理解 TodoManager 的设计
- 掌握 `activeForm` 的用法

**代码位置**: `agents/s03_todo_write.py`

**学习步骤**:

1. **阅读** `docs/zh/s03-todo-write.md`
2. **运行** `python agents/s03_todo_write.py`
3. **观察** Agent 如何使用 TodoWrite 工具

**核心模式**:

```python
# TodoWrite 接收的格式
{
    "items": [
        {"content": "安装依赖", "status": "pending", "activeForm": "正在安装依赖"},
        {"content": "编写测试", "status": "in_progress", "activeForm": "正在编写测试"},
        {"content": "提交代码", "status": "pending", "activeForm": "正在提交代码"}
    ]
}
```

---

### s04 - Subagents (子智能体)

**核心概念**: 拆分大任务，每个子任务获得独立上下文

**学习目标**:
- 理解子 Agent 的独立消息列表
- 掌握父子 Agent 的通信模式

**代码位置**: `agents/s04_subagent.py`

**核心模式**:

```python
def run_subagent(prompt: str):
    # 独立的消息列表，不污染主上下文
    sub_msgs = [{"role": "user", "content": prompt}]
    
    # 独立的工具集
    sub_tools = [{"name": "bash", ...}, {"name": "read_file", ...}]
    
    # 独立运行
    while True:
        response = client.messages.create(model=MODEL, messages=sub_msgs, tools=sub_tools)
        # ... 执行工具 ...
```

---

### s05 - Skill Loading (技能加载)

**核心概念**: 需要时加载知识，不要预先塞入

**学习目标**:
- 理解 SKILL.md 的格式
- 掌握 `tool_result` 注入模式

**代码位置**: `agents/s05_skill_loading.py`

**SKILL.md 格式**:

```markdown
---
name: python-style
description: Python 代码风格指南
---

# Python 代码风格

## 命名规范
- 函数: snake_case
- 类名: PascalCase
...
```

---

### s06 - Context Compact (上下文压缩)

**核心概念**: 上下文会填满，需要腾出空间

**学习目标**:
- 掌握三层压缩策略
- 理解自动压缩的触发条件

**代码位置**: `agents/s06_context_compact.py`

**三层压缩**:

1. **Microcompact**: 清理末尾的 tool_result
2. **Token 阈值**: 超过阈值触发压缩
3. **手动压缩**: 通过 `/compact` 命令触发

---

## 5. 第三阶段：持久化

### s07 - Task System (任务系统)

**核心概念**: 将大目标拆分为小任务，持久化到磁盘

**学习目标**:
- 掌握文件型任务管理
- 理解任务依赖图

**代码位置**: `agents/s07_task_system.py`

**核心功能**:
- `task_create`: 创建任务
- `task_update`: 更新状态
- `task_list`: 列出所有任务
- 依赖管理 (`blockedBy`, `blocks`)

---

### s08 - Background Tasks (后台任务)

**核心概念**: 慢操作放后台，Agent 继续思考

**学习目标**:
- 掌握守护线程模式
- 理解通知队列机制

**代码位置**: `agents/s08_background_tasks.py`

**核心模式**:

```python
class BackgroundManager:
    def run(self, command: str, timeout: int = 120) -> str:
        tid = str(uuid.uuid4())[:8]
        # 后台线程执行
        threading.Thread(target=self._exec, args=(tid, command, timeout), daemon=True).start()
        return f"Background task {tid} started"
    
    def drain(self) -> list:
        # 抽取通知
        notifs = []
        while not self.notifications.empty():
            notifs.append(self.notifications.get_nowait())
        return notifs
```

---

## 6. 第四阶段：团队协作

### s09 - Agent Teams (智能体团队)

**核心概念**: 任务太大时，委托给队友

**学习目标**:
- 掌握持久化队友模式
- 理解 JSONL 邮箱通信

**代码位置**: `agents/s09_agent_teams.py`

**核心模式**:

```python
class MessageBus:
    def send(self, sender: str, to: str, content: str):
        # 写入 JSONL 文件
        with open(INBOX_DIR / f"{to}.jsonl", "a") as f:
            f.write(json.dumps(msg) + "\n")
    
    def read_inbox(self, name: str) -> list:
        # 读取并清空
        path = INBOX_DIR / f"{name}.jsonl"
        msgs = [json.loads(l) for l in path.read_text().splitlines()]
        path.write_text("")
        return msgs
```

---

### s10 - Team Protocols (团队协议)

**核心概念**: 队友需要共同的通信规则

**学习目标**:
- 掌握关闭协议（request_id 握手）
- 理解计划审批 FSM

**代码位置**: `agents/s10_team_protocols.py`

---

### s11 - Autonomous Agents (自主智能体)

**核心概念**: 队友自己扫描任务板并认领

**学习目标**:
- 掌握空闲-工作循环
- 理解自动认领机制

**代码位置**: `agents/s11_autonomous_agents.py`

---

### s12 - Worktree Isolation (工作区隔离)

**核心概念**: 每人工作在独立目录，互不干扰

**学习目标**:
- 掌握任务协调 + 隔离执行
- 理解 worktree 管理

**代码位置**: `agents/s12_worktree_task_isolation.py`

---

## 7. 实战项目

### 7.1 完整 capstone: s_full.py

将所有机制组合的完整实现：

```bash
python agents/s_full.py
```

REPL 命令：
- `/compact` - 手动压缩上下文
- `/tasks` - 列出所有任务
- `/team` - 列出所有队友
- `/inbox` - 查看收件箱

### 7.2 建议练习项目

1. **扩展 s01**: 添加文件读写工具
2. **扩展 s03**: 添加任务优先级
3. **扩展 s07**: 添加子任务支持
4. **扩展 s09**: 添加群组消息

---

## 8. 常见问题

### Q1: 遇到 API 错误怎么办？

检查 `.env` 文件，确保 API key 配置正确：
```bash
cat .env

# 支持的 API (任选其一):
#   - Groq (推荐): GEMINI_API_KEY=xxx, BASE_URL=https://api.groq.com/openai/v1/
#   - Gemini: GEMINI_API_KEY=xxx
#   - Anthropic: ANTHROPIC_API_KEY=xxx
```

### Q2: 工具调用超时怎么办？

s_full.py 默认超时 120 秒，可通过 `background_run` 工具指定更长的超时时间。

### Q3: 上下文过长怎么办？

```python
# 在 s_full.py 中调整阈值
TOKEN_THRESHOLD = 100000  # 默认值，可调小
```

### Q4: 如何调试 Agent 行为？

在 `agent_loop` 中添加打印：
```python
print(f"[DEBUG] stop_reason: {response.stop_reason}")
print(f"[DEBUG] tool_calls: {[b.name for b in response.content if b.type == 'tool_use']}")
```

---

## 继续学习

- [Web 平台](https://github.com/shareAI-lab/learn-claude-code#web-platform) - 交互式可视化
- [文档目录](./docs/zh/) - 详细的中文文档
- [下一步：Kode Agent CLI](https://github.com/shareAI-lab/Kode-cli) - 开源 Agent CLI

---

**记住**: 模型是智能体，代码是工具架。构建好的工具架，智能体自会完成工作。🛠️
