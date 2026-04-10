# -*- coding: utf-8 -*-
# pyrowl/cli.py - M5: 命令行入口 + skill 集成
"""
pyrowl CLI 用法：
  python -m pyrowl.cli new "任务描述" [--chat_id xxx]
  python -m pyrowl.cli status [--chat_id xxx]
  python -m pyrowl.cli next [--chat_id xxx]
  python -m pyrowl.cli abort [--chat_id xxx]
  python -m pyrowl.cli list

Python 集成：
  from pyrowl import WorkflowOrchestrator
  orch = WorkflowOrchestrator(chat_id="...")
  orch.new_workflow("我的任务")
"""

import sys, argparse, json, os
from pathlib import Path

# Add pyrowl to path
sys.path.insert(0, str(Path(__file__).parent))

from workflow import WorkflowOrchestrator, WFStatus, StepType, StepStatus
from planner import plan_task, apply_plan
from context_builder import build_context, get_project_context
from validation_loop import ValidationLoop


def cmd_new(args):
    chat = args.chat_id or os.environ.get("QCLAW_CHAT_ID", "default")
    orch = WorkflowOrchestrator(chat)

    # 如果已有活跃 workflow，先查
    if orch.active:
        print(f"[pyrowl] Already have active workflow:")
        print(orch.status_summary())
        return

    # 自动拆解步骤
    print(f"[pyrowl] Planning: {args.task}")
    steps = plan_task(args.task, args.context or "")

    if not steps:
        print("[pyrowl] Could not parse steps, creating empty workflow")
        orch.new_workflow(args.task)
    else:
        orch.new_workflow(args.task, steps)

    print(f"[pyrowl] Created: {orch.wf.id}")
    print(orch.status_summary())
    return orch


def cmd_status(args):
    chat = args.chat_id or os.environ.get("QCLAW_CHAT_ID", "default")
    orch = WorkflowOrchestrator(chat)
    if orch.active:
        print(orch.status_summary())
        # 打印 LLM 上下文
        ctx = orch.get_context_for_llm()
        if args.verbose and ctx:
            print("\n-- LLM Context --")
            print(ctx)
    else:
        print("[pyrowl] No active workflow")
        # 也列出最近几个
        all_wf = WorkflowOrchestrator(chat)._load_active() or []
        from workflow import WorkflowRecord
        recent = WorkflowRecord.list_all()[:3]
        if recent:
            print("\nRecent workflows:")
            for wf in recent:
                print(f"  {wf.id[:20]} [{wf.status.value}] {wf.task[:50]}")


def cmd_next(args):
    chat = args.chat_id or os.environ.get("QCLAW_CHAT_ID", "default")
    orch = WorkflowOrchestrator(chat)

    if not orch.active:
        print("[pyrowl] No active workflow to advance")
        return

    step = orch.begin_step()
    if not step:
        print("[pyrowl] All steps completed")
        orch.done("All steps done")
        print(orch.status_summary())
        return

    print(f"[pyrowl] Executing step {step.id}: {step.description}")
    print(f"  type={step.type} action={str(step.action)[:60] if step.action else '(none)'}")

    # 执行 + 验证
    val_loop = ValidationLoop(max_retries=args.max_retries or 3, retry_delay=1.0)
    result = val_loop.execute_and_validate(
        step.action or "",
        step.type.value if hasattr(step.type, "value") else str(step.type),
        step.validation,
    )

    if result["result"] == "PASS":
        orch.complete_step(result["output"] or "done")
        print(f"  [OK] attempts={result['attempts']}")
        if result["output"]:
            for line in str(result["output"]).split("\n")[:5]:
                print(f"    {line[:80]}")
    else:
        orch.complete_step(error=result["stderr"] or result["fix_suggestion"] or "failed")
        print(f"  [FAIL] attempts={result['attempts']}")
        if result["fix_suggestion"]:
            print(f"  Fix: {result['fix_suggestion']}")
        if result["stderr"]:
            for line in str(result["stderr"]).split("\n")[:3]:
                print(f"    {line[:80]}")

    # 看下一步
    print()
    print(orch.status_summary())

    # 自动推进下一步（如果需要）
    if args.auto and result["result"] == "PASS":
        next_step = orch.wf.next_step_obj() if orch.wf else None
        if next_step:
            print(f"\n[pyrowl] Auto-advancing to next step...")


def cmd_context(args):
    """加载项目上下文"""
    if not args.project:
        # 尝试从当前 workflow 推断
        chat = args.chat_id or os.environ.get("QCLAW_CHAT_ID", "default")
        orch = WorkflowOrchestrator(chat)
        if orch.active and orch.wf and orch.wf.metadata.get("project_root"):
            args.project = orch.wf.metadata["project_root"]

    if not args.project:
        print("[pyrowl] No project specified. Use --project /path/to/project")
        return

    ctx = get_project_context(args.project, args.task or "", args.types.split(",") if args.types else None)
    print(ctx[: args.max_chars or 4000])


def cmd_list(args):
    from workflow import WorkflowRecord
    all_wf = WorkflowRecord.list_all()
    print(f"[pyrowl] Total workflows: {len(all_wf)}")
    for wf in all_wf[:20]:
        active_icon = "*" if wf.status not in (WFStatus.DONE, WFStatus.FAILED) else " "
        done = sum(1 for s in wf.steps if s.status == StepStatus.DONE)
        total = len(wf.steps)
        print(f"  {active_icon}{wf.id[:20]} [{wf.status.value:12s}] {done}/{total} {wf.task[:50]}")


def cmd_abort(args):
    chat = args.chat_id or os.environ.get("QCLAW_CHAT_ID", "default")
    orch = WorkflowOrchestrator(chat)
    if orch.active:
        orch.abort(args.reason or "user_abort")
        print(f"[pyrowl] Aborted: {orch.wf.id}")
    else:
        print("[pyrowl] No active workflow to abort")


def main():
    parser = argparse.ArgumentParser(prog="pyrowl", description="Python Orchestration Layer for OpenClaw")
    sub = parser.add_subparsers(dest="cmd")

    p_new = sub.add_parser("new", help="Create a new workflow")
    p_new.add_argument("task", help="Task description")
    p_new.add_argument("--chat_id", help="Chat ID (defaults to QCLAW_CHAT_ID env)")
    p_new.add_argument("--context", help="Additional context for planning")

    p_status = sub.add_parser("status", help="Show current workflow status")
    p_status.add_argument("--chat_id")
    p_status.add_argument("--verbose", "-v", action="store_true")

    p_next = sub.add_parser("next", help="Execute next step")
    p_next.add_argument("--chat_id")
    p_next.add_argument("--max_retries", type=int, default=3)
    p_next.add_argument("--auto", action="store_true", help="Auto-advance through all steps")

    p_ctx = sub.add_parser("context", help="Build project context")
    p_ctx.add_argument("--project", help="Project root path")
    p_ctx.add_argument("--task", help="Task description for keyword extraction")
    p_ctx.add_argument("--types", help="File types, comma-separated, e.g. py,json")
    p_ctx.add_argument("--max_chars", type=int, default=4000)

    p_list = sub.add_parser("list", help="List all workflows")

    p_abort = sub.add_parser("abort", help="Abort current workflow")
    p_abort.add_argument("--chat_id")
    p_abort.add_argument("--reason", default="user_abort")

    args = parser.parse_args()

    if args.cmd == "new":
        cmd_new(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "next":
        cmd_next(args)
    elif args.cmd == "context":
        cmd_context(args)
    elif args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "abort":
        cmd_abort(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
