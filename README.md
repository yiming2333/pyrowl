# pyrowl 🚀

**Python Workflow Orchestration Layer for AI Agents**

轻量级任务编排框架，让 AI agent 能将复杂多步骤任务拆解、执行、验证。

## 特性

- 🧩 **智能任务拆解** — 自动将复杂任务拆分为可执行步骤（支持 LLM + 启发式双模式）
- ✅ **验证循环** — 每步完成后验证结果，失败自动重试
- 📊 **状态持久化** — workflow JSON 持久化到磁盘，跨 session 恢复
- 🔗 **OpenClaw 集成** — context.json 自动注入 system prompt（via pyrowl-context extension）
- 🎯 **步骤分类** — 自动分类 read/write/cmd 三种步骤类型

## 架构

```
pyrowl/
├── __init__.py          # 导出接口
├── workflow.py          # M1: 核心状态机（WorkflowOrchestrator）
├── planner.py           # M2: 任务拆解器（plan_task / quick_parse）
├── validation_loop.py   # M3: 验证循环（ValidationLoop）
├── cli.py               # M4: 命令行工具
├── context_builder.py   # M5: 项目上下文构建
└── README.md
```

## 快速开始

```python
from pyrowl import WorkflowOrchestrator, plan_task

# 1. 拆解任务
task = "做一个K线图可视化工具，先获取股票数据，再用matplotlib画图，最后保存为PNG"
steps = plan_task(task)
# → [{"description": "做一个K线图可视化工具", "type": "write"}, ...]

# 2. 创建 workflow
orch = WorkflowOrchestrator('chat_123')
orch.new_workflow(task, steps)

# 3. 推进步骤
orch.begin_step()       # 开始第一步
# ... agent 执行第一步 ...
orch.complete_step()    # 完成第一步

# 4. 查看状态
print(orch.status_summary())
```

## 步骤类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `read` | 分析/获取/下载 | "获取股票数据", "分析页面结构" |
| `write` | 创建/开发/保存 | "编写爬虫代码", "画K线图" |
| `cmd` | 测试/部署/执行 | "运行测试", "部署到服务器" |

## OpenClaw 集成

pyrowl 通过 `session_todo.py` 的 `persist_context()` 将 workflow 状态写入 `~/.qclaw/pyrowl/context.json`。

配合 `pyrowl-context` OpenClaw 扩展，workflow 状态会自动注入到每轮对话的 system prompt 中，让 AI agent 感知当前任务进度。

### 安装扩展

1. 将 `extensions/pyrowl-context/` 复制到 QClaw 扩展目录
2. 在 `~/.qclaw/openclaw.json` 中添加：
```json
{
  "plugins": {
    "allow": ["pyrowl-context"],
    "load": { "paths": ["path/to/pyrowl-context"] },
    "entries": {
      "pyrowl-context": {
        "enabled": true,
        "config": { "contextPath": "~/.qclaw/pyrowl/context.json" }
      }
    }
  }
}
```
3. 重启 QClaw

## 持久化

Workflow 数据存储在 `~/.qclaw/pyrowl/` 下：

```
~/.qclaw/pyrowl/
├── context.json                    # 当前活跃 workflow 上下文
└── workflows/
    ├── wf_20260410_005106_feb930.json
    └── ...
```

## 版本

v0.1.0 — 初始版本，M1-M9 完成

## License

MIT
