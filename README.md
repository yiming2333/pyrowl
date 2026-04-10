# pyrowl

**Python Workflow Orchestration Layer for OpenClaw**

在 OpenClaw 之上构建有状态的多步骤任务编排系统。

## 特性

- **Workflow 状态机** — 创建 → 执行 → 验证 → 迭代
- **LLM 智能拆解** — 调用 OpenClaw gateway API 自动拆解任务为具体步骤
- **Validation Loop** — 自动 run → fail → fix → retry
- **Context Builder** — 按需加载项目文件，不全量塞入 prompt
- **跨 Session 持久化** — workflow 状态保存在 `~/.qclaw/pyrowl/`

## 安装

```bash
# 作为 Python 包安装
pip install -e .

# 或直接使用
python -m pyrowl.cli new "做一个K线图可视化工具"
```

## 快速开始

```python
from pyrowl import WorkflowOrchestrator, plan_task, apply_plan, persist_context

# 1. 创建 orchestrator
orch = WorkflowOrchestrator("user123")

# 2. LLM 拆解任务
task = "做一个K线图可视化工具，先获取股票数据，再画K线图"
steps = plan_task(task)

# 3. 创建 workflow
orch.new_workflow(task, steps)

# 4. 推进步骤
while orch.active:
    step = orch.begin_step()
    print(f"执行: {step.description}")
    # ... 执行步骤 ...
    orch.complete_step("OK")

# 5. 查看状态
print(orch.status_summary())
```

## CLI

```bash
# 创建 workflow
python -m pyrowl.cli new "做一个爬虫，先分析页面，再写代码"

# 查看状态
python -m pyrowl.cli status

# 推进步骤
python -m pyrowl.cli next

# 列出所有 workflow
python -m pyrowl.cli list

# 查看当前 context
python -m pyrowl.cli context
```

## 架构

```
用户消息
  ↓
skill_matcher → pyrowl skill
  ↓
auto_detect_and_act → workflow 创建
  ↓
planner.plan_task() → LLM 拆解步骤
  ↓
workflow.py 状态机 → 执行步骤
  ↓
validation_loop → 验证 + 自动修复
  ↓
persist_context → context.json 持久化
  ↓
pyrowl-context extension → 注入 system prompt
```

## OpenClaw 集成

pyrowl 通过 OpenClaw skill 系统工作。当用户说多步骤任务时：

1. `skill_matcher` 识别 pyrowl 意图
2. `auto_detect_and_act` 创建 workflow
3. `persist_context` 写入 `~/.qclaw/pyrowl/context.json`
4. `pyrowl-context` extension 读取 context 并注入 system prompt

## 许可证

MIT
