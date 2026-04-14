# -*- coding: utf-8 -*-
# pyrowl/persistence.py - M4: Workflow Context 持久化与加载
# 将 workflow 状态写入 context.json，供外部系统（SOUL.md / Extension）读取注入

import json
import pathlib
import threading
from typing import Optional

_CONTEXT_DIR = pathlib.Path(r"D:\QClaw_workspace\.qclaw\pyrowl")
_CONTEXT_FILE = _CONTEXT_DIR / "context.json"
_context_lock = threading.Lock()


def persist_context(orch, pending_action: Optional[str] = None) -> dict:
    """
    将 pyrowl orchestrator 状态写入 context.json。

    Args:
        orch: WorkflowOrchestrator 实例
        pending_action: 告诉外部系统下一步要做什么
            - 'execute_step': 执行当前步骤（AI 需要执行具体操作）
            - 'advance': 推进到下一步
            - None: 等待外部输入

    Returns:
        (context_dict, reply_prefix) 元组
    """
    _CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    reply_prefix = ""

    if orch and orch.active and orch.wf:
        wf = orch.wf
        current = wf.current_step_obj()
        nxt = wf.next_step_obj()
        total = len(wf.steps)
        cur_num = (wf.current_step + 1) if wf.current_step is not None else 0

        ctx = {
            "active": True,
            "id": wf.id,
            "task": wf.task,
            "status": wf.status.value,
            "total_steps": total,
            "progress": f"{cur_num}/{total}",
            "current": {
                "step": cur_num,
                "description": current.description if current else "",
                "type": current.type.value if current else "",
                "files_read": getattr(current, "files_read", []),
                "files_write": getattr(current, "files_write", []),
                "action": getattr(current, "action", None),
                "validation": getattr(current, "validation", {}),
                "attempts": current.attempts if current else 0,
            } if wf.current_step is not None and current else None,
            "next": {
                "description": nxt.description if nxt else "",
                "type": nxt.type.value if nxt else "",
            } if nxt else None,
            "pending_action": pending_action,
        }

        reply_prefix = (
            f"[workflow {cur_num}/{total}] "
            f"{current.description[:60] if current else wf.task[:60]}"
        )
    else:
        ctx = {"active": False, "id": None, "pending_action": None}

    with _context_lock:
        with open(_CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)

    return ctx, reply_prefix


def load_context() -> dict:
    """
    读取当前 workflow context（供 SOUL.md / Extension / system prompt 使用）。
    """
    if _CONTEXT_FILE.exists():
        try:
            with open(_CONTEXT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active": False}


def clear_context():
    """清除 context.json（workflow 结束时调用）"""
    with _context_lock:
        if _CONTEXT_FILE.exists():
            _CONTEXT_FILE.unlink()
