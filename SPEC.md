# pyrowl - Python Orchestration Layer for OpenClaw

## 目标
在 OpenClaw reactive loop 之上，叠加三层能力：
1. **Workflow** - 有状态的任务流（plan-execute-validate-iterate）
2. **Context Builder** - 按需加载项目相关文件，不全量塞入 prompt
3. **Validation Loop** - 自动 run-fail-fix-retry

## 架构
用户消息 -> skill_matcher -> 发现需要 workflow -> pyrowl.orchestrate(task)
-> planner 拆解 -> workflow orchestrator 执行
-> 每步 validation loop -> 通过则下一步，失败则 fix-retry
-> 最终结果写入 memory/

## 模块设计
1. workflow.py: WorkflowOrchestrator 状态机
2. planner.py: 任务拆解（调用 OpenClaw model）
3. context_builder.py: 文件级上下文加载器
4. validation_loop.py: run-fail-fix-retry 循环
5. cli.py: 命令行入口

## 状态文件
~/.qclaw/pyrowl/workflows/{wf_id}.json

## 里程碑
- [x] M0: SPEC + 目录结构
- [x] M1: workflow.py - 核心状态机 + 持久化 ✅ 测试通过
- [x] M2: planner.py - 多策略步骤拆解 ✅ 支持"包含A、B、C"格式
- [x] M3: context_builder.py - 文件扫描 + 关键词匹配 + 缓存 + 智能截断 ✅
- [x] M4: validation_loop.py - run-fail-fix-retry 循环 ✅ 测试通过
- [x] M5: cli.py - new/status/next/list/abort/context 命令 ✅
- [x] M6: session_todo 集成 - is_workflow_intent + auto_detect_and_act ✅
- [ ] M7: 端到端真实任务测试（与 OpenClaw 真实对话）

## 待集成（与 OpenClaw 的连接）
1. **skill_matcher → pyrowl**：在 skill_matcher 中检测 workflow 意图，创建 workflow
2. **pyrowl → LLM context**：get_context_for_llm() 注入到 OpenClaw system prompt
3. **OpenClaw hooks → pyrowl.next()**：before_prompt_build 或 after_tool_call 推进 workflow
