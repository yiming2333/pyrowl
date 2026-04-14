# -*- coding: utf-8 -*-
# pyrowl/workflow.py - M1: 核心状态机 + 持久化

import json, os, re, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

PYROWL_DIR = Path(r"D:\QClaw_workspace\.qclaw\pyrowl")
WORKFLOWS_DIR = PYROWL_DIR / "workflows"
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

class WFStatus(str, Enum):
    IDLE       = "IDLE"
    PLANNING   = "PLANNING"
    EXECUTING  = "EXECUTING"
    VALIDATING = "VALIDATING"
    FIXING     = "FIXING"
    WAITING    = "WAITING"
    DONE       = "DONE"
    FAILED     = "FAILED"

class StepType(str, Enum):
    CMD    = "cmd"
    WRITE  = "write"
    READ   = "read"
    BROWSE = "browse"
    SKILL  = "skill"
    USER   = "user"

class StepStatus(str, Enum):
    PENDING   = "PENDING"
    EXECUTING = "EXECUTING"
    DONE      = "DONE"
    FAILED    = "FAILED"
    SKIPPED   = "SKIPPED"

class Step:
    def __init__(self, sid, description, step_type, action=None,
                 validation=None, rollback=None,
                 files_read=None, files_write=None,
                 parallel_group=None):
        self.id = sid
        self.description = description
        self.type = step_type
        self.action = action
        self.validation = validation or {}
        self.rollback = rollback
        # 并行执行支持：读写文件列表 + 并行组号
        self.files_read = files_read or []   # 读取的文件路径（用于依赖分析）
        self.files_write = files_write or []  # 写入的文件路径（用于依赖分析）
        self.parallel_group = parallel_group  # None=串行, >0=并行组号
        self.status = StepStatus.PENDING
        self.result = None
        self.error = None
        self.attempts = 0
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.finished_at = None

    def to_dict(self):
        t = self.type.value if hasattr(self.type, "value") else self.type
        return dict(id=self.id, description=self.description, type=t,
                    action=self.action, validation=self.validation,
                    rollback=self.rollback, status=self.status.value,
                    result=self.result, error=self.error,
                    attempts=self.attempts, created_at=self.created_at,
                    finished_at=self.finished_at)

    @staticmethod
    def from_dict(d):
        s = Step(d["id"], d["description"],
                 StepType(d["type"]) if "type" in d else StepType.CMD,
                 d.get("action"), d.get("validation"), d.get("rollback"))
        s.status = StepStatus(d["status"])
        s.result = d.get("result")
        s.error = d.get("error")
        s.attempts = d.get("attempts", 0)
        s.created_at = d.get("created_at")
        s.finished_at = d.get("finished_at")
        return s

class WorkflowRecord:
    def __init__(self, task, chat_id, wf_id=None):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.id = wf_id or f"wf_{ts}_{uuid.uuid4().hex[:6]}"
        self.task = task
        self.chat_id = chat_id
        self.steps = []
        self.status = WFStatus.IDLE
        self.current_step = -1
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.history = []
        self.metadata = {}
        self._counter = 0

    def add_step(self, description, step_type, action=None,
                 validation=None, rollback=None,
                 files_read=None, files_write=None):
        self._counter += 1
        t = step_type.value if hasattr(step_type, "value") else step_type
        st = Step(self._counter - 1, description, StepType(t), action, validation, rollback,
                  files_read, files_write)
        self.steps.append(st)
        return st

    def current_step_obj(self):
        for s in self.steps:
            if s.id == self.current_step:
                return s
        return None

    def next_step_obj(self):
        for s in sorted(self.steps, key=lambda x: x.id):
            if s.status == StepStatus.PENDING:
                return s
        return None

    def to_dict(self):
        return dict(id=self.id, task=self.task, chat_id=self.chat_id,
                    status=self.status.value, current_step=self.current_step,
                    steps=[s.to_dict() for s in self.steps],
                    created_at=self.created_at, updated_at=self.updated_at,
                    history=self.history, metadata=self.metadata)

    @staticmethod
    def from_dict(d):
        wf = WorkflowRecord(d["task"], d["chat_id"], d["id"])
        wf.status = WFStatus(d["status"])
        wf.current_step = d["current_step"]
        wf.steps = [Step.from_dict(s) for s in d.get("steps", [])]
        wf._counter = len(wf.steps)
        wf.created_at = d.get("created_at", wf.created_at)
        wf.updated_at = d.get("updated_at", wf.updated_at)
        wf.history = d.get("history", [])
        wf.metadata = d.get("metadata", {})
        return wf

    def save(self):
        self.updated_at = datetime.now(timezone.utc).isoformat()
        path = WORKFLOWS_DIR / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def load(wf_id):
        path = WORKFLOWS_DIR / f"{wf_id}.json"
        if not path.exists():
            return None
        try:
            return WorkflowRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    @staticmethod
    def list_all():
        results = []
        for f in WORKFLOWS_DIR.glob("*.json"):
            try:
                results.append(WorkflowRecord.from_dict(json.loads(f.read_text(encoding="utf-8"))))
            except Exception:
                pass
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def add_history(self, event, detail=""):
        self.history.append(dict(event=event, detail=detail,
                                  ts=datetime.now(timezone.utc).isoformat()))

class WorkflowOrchestrator:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self._wf = None
        self._load_active()

    def _load_active(self):
        for wf in WorkflowRecord.list_all():
            if wf.chat_id == self.chat_id and wf.status not in (WFStatus.DONE, WFStatus.FAILED):
                self._wf = wf
                return

    @property
    def active(self):
        return self._wf is not None and self._wf.status not in (WFStatus.DONE, WFStatus.FAILED)

    @property
    def wf(self):
        return self._wf

    def new_workflow(self, task, steps=None):
        self._wf = WorkflowRecord(task, self.chat_id)
        if steps:
            for s in steps:
                self._wf.add_step(
                    s["description"], s.get("type", "cmd"),
                    s.get("action"), s.get("validation"), s.get("rollback"),
                    s.get("files_read", []), s.get("files_write", []),
                )
            self._wf.current_step = 0
            self._wf.status = WFStatus.EXECUTING
        else:
            self._wf.status = WFStatus.PLANNING
        self._wf.save()
        self._wf.add_history("workflow_created", f"task={task}")
        return self._wf

    def set_steps(self, steps):
        if not self._wf:
            return
        for s in steps:
            self._wf.add_step(
                s["description"], s.get("type", "cmd"),
                s.get("action"), s.get("validation"), s.get("rollback"),
                s.get("files_read", []), s.get("files_write", []),
            )

    def begin_step(self):
        if not self._wf:
            return None
        step = self._wf.next_step_obj()
        if step:
            step.status = StepStatus.EXECUTING
            step.attempts += 1
            self._wf.status = WFStatus.EXECUTING
            self._wf.current_step = step.id
            self._wf.add_history("step_started", f"step={step.id}")
            self._wf.save()
        return step

    def complete_step(self, result="", error=None):
        if not self._wf:
            return
        step = self._wf.current_step_obj()
        if not step:
            return
        if error:
            step.status = StepStatus.FAILED
            step.error = error
            self._wf.add_history("step_failed", f"step={step.id} error={str(error)[:100]}")
        else:
            step.status = StepStatus.DONE
            step.result = result
            step.finished_at = datetime.now(timezone.utc).isoformat()
            self._wf.add_history("step_done", f"step={step.id}")
        # Check if all steps are done → mark workflow as DONE
        all_done = all(s.status == StepStatus.DONE or s.status == StepStatus.SKIPPED
                       for s in self._wf.steps)
        if all_done:
            self._wf.status = WFStatus.DONE
            self._wf.add_history("workflow_done", "all steps completed")
        self._wf.save()

    def skip_step(self):
        if not self._wf:
            return
        step = self._wf.current_step_obj()
        if step:
            step.status = StepStatus.SKIPPED
            self._wf.add_history("step_skipped", f"step={step.id}")
            self._wf.save()

    def abort(self, reason=""):
        if not self._wf:
            return
        self._wf.status = WFStatus.FAILED
        self._wf.add_history("workflow_aborted", reason)
        self._wf.save()

    def done(self, result=""):
        if not self._wf:
            return
        self._wf.status = WFStatus.DONE
        self._wf.add_history("workflow_done", result)
        self._wf.save()

    def status_summary(self):
        if not self._wf:
            return "[pyrowl] no active workflow"
        done = sum(1 for s in self._wf.steps if s.status == StepStatus.DONE)
        total = len(self._wf.steps)
        prog = f"{done}/{total}" if total else "-"
        step = self._wf.current_step_obj()
        cur = step.description[:40] if step else "-"
        icons = {"PENDING": "O", "EXECUTING": "R", "DONE": "V", "FAILED": "X", "SKIPPED": "S"}
        lines = [
            f"[pyrowl] #{self._wf.id[:20]} [{self._wf.status.value}]",
            f"  task: {self._wf.task[:60]}",
            f"  progress: {prog} | current: {cur}",
        ]
        for s in sorted(self._wf.steps, key=lambda x: x.id):
            icon = icons.get(s.status.value, "?")
            arrow = ">" if s.id == self._wf.current_step else " "
            lines.append(f"  {arrow}[{icon}] {s.description[:50]}")
            if s.result and len(str(s.result)) < 80:
                lines.append(f"      -> {str(s.result)[:70]}")
            if s.error:
                lines.append(f"      X  {str(s.error)[:70]}")
        return "\n".join(lines)

    def get_context_for_llm(self):
        if not self._wf:
            return ""
        lines = [
            f"Current Workflow: {self._wf.task}",
            f"Status: {self._wf.status.value} | Step: {self._wf.current_step+1}/{len(self._wf.steps)}",
        ]
        for s in sorted(self._wf.steps, key=lambda x: x.id):
            icon = {"PENDING": "O", "EXECUTING": "R", "DONE": "V", "FAILED": "X", "SKIPPED": "S"}.get(s.status.value, "?")
            lines.append(f"  {icon} [{s.type}] {s.description}")
            if s.result:
                lines.append(f"    -> {str(s.result)[:100]}")
            if s.error:
                lines.append(f"    X  {str(s.error)[:100]}")
        return "\n".join(lines)

    # ====================================================================
    # 并行执行：自动分析可并行的步骤组
    # ====================================================================

    def _extract_files(self, text):
        """从描述中提取文件路径（简单启发式）"""
        patterns = [
            r'(?:src/|lib/|app/|tools/|scripts/|config/|data/|models/)[^\s]+\.py',
            r'(?:src/|lib/|app/|components/)[^\s]+\.[jt]sx?',
            r'(?:public/|static/|assets/)[^\s]+\.[a-z]+',
            r'[A-Za-z]:[\\\/][^\s:]+\.[a-z]+',
            r'[./][^\s]+\.py',
            r'[./][^\s]+\.js',
            r'[./][^\s]+\.json',
            r'[./][^\s]+\.yaml',
            r'[./][^\s]+\.csv',
            r'[./][^\s]+\.md',
        ]
        files = set()
        for pat in patterns:
            for m in re.findall(pat, text, re.IGNORECASE):
                files.add(m.lower())
        return files

    def _file_conflicts(self, files_a, files_b):
        """检查两个步骤是否有文件冲突（一个读一个写同一文件）"""
        for fa in files_a:
            for fb in files_b:
                # 完全相同
                if fa == fb:
                    return True
                # 一个是另一个的前缀（如 "src" vs "src/a.py"）
                if fa.startswith(fb.rsplit('.', 1)[0]) or fb.startswith(fa.rsplit('.', 1)[0]):
                    return True
        return False

    def compute_parallel_groups(self):
        """
        分析所有 PENDING 步骤，计算可并行的组。
        原则：write↔write、read↔read、cmd↔cmd 之间无文件冲突时可以并行。
        Returns: list of [step_id, ...] 组列表
        """
        pending = [s for s in self._wf.steps if s.status == StepStatus.PENDING]
        if not pending:
            return []

        # 提取每个步骤的文件
        for s in pending:
            if not s.files_write and not s.files_read:
                s.files_write = list(self._extract_files(s.description))
            if not s.files_read and not s.files_write:
                s.files_read = list(self._extract_files(s.description))

        groups = []
        used = set()
        # 第一次：同 type 的 PENDING 步骤
        for t in ("write", "cmd", "read"):
            group = [s for s in pending if s.type == t and s.id not in used]
            conflict = False
            for i, s1 in enumerate(group):
                for s2 in group[i+1:]:
                    all_f1 = set(s1.files_read) | set(s1.files_write)
                    all_f2 = set(s2.files_read) | set(s2.files_write)
                    if self._file_conflicts(all_f1, all_f2):
                        conflict = True
                        break
                if conflict:
                    break
            if group and not conflict:
                groups.append([s.id for s in group])
                used.update(s.id for s in group)

        # 第二次：剩余的单独成组
        for s in pending:
            if s.id not in used:
                groups.append([s.id])
                used.add(s.id)

        return groups

    def begin_parallel_group(self):
        """
        开始下一个可并行的步骤组。
        Returns: list of Step 对象
        """
        groups = self.compute_parallel_groups()
        if not groups:
            return []
        group_ids = groups[0]
        steps = []
        for sid in group_ids:
            for s in self._wf.steps:
                if s.id == sid:
                    s.status = StepStatus.EXECUTING
                    s.attempts += 1
                    steps.append(s)
        if steps:
            self._wf.status = WFStatus.EXECUTING
            # 第一个步骤设为 current_step
            self._wf.current_step = steps[0].id
            self._wf.save()
        return steps

    def complete_step_by_id(self, step_id, result="", error=None):
        """完成指定 ID 的步骤（并行模式下使用）"""
        for s in self._wf.steps:
            if s.id == step_id:
                if error:
                    s.status = StepStatus.FAILED
                    s.error = error
                    self._wf.add_history("step_failed", f"step={s.id} error={str(error)[:100]}")
                else:
                    s.status = StepStatus.DONE
                    s.result = result
                    s.finished_at = datetime.now(timezone.utc).isoformat()
                    self._wf.add_history("step_done", f"step={s.id}")
                self._wf.save()
                # 检查是否全部完成
                all_done = all(st.status in (StepStatus.DONE, StepStatus.SKIPPED, StepStatus.FAILED)
                               for st in self._wf.steps)
                if all_done:
                    self._wf.status = WFStatus.DONE
                    self._wf.add_history("workflow_done", "all steps completed")
                    self._wf.save()
                return

    # ========================================================================
    # 自动推进：report_step_result / skip_step
    # ========================================================================

    def report_step_result(self, success: bool, output: str = None, error: str = None) -> dict:
        """
        报告当前步骤执行结果，自动推进到下一步。

        Args:
            success: 步骤是否成功执行
            output: 步骤输出（字符串或 dict）
            error: 错误信息

        Returns:
            dict，含下一步执行指令或 workflow_done
        """
        from .persistence import persist_context, clear_context

        if not self._wf:
            return {"action": "error", "message": "No active workflow"}

        current = self._wf.current_step_obj()
        if not current:
            return {"action": "error", "message": "No current step"}

        if success:
            self.complete_step(output or "OK")
            # 推进到下一步
            next_step = self._wf.next_step_obj()
            if not next_step:
                self._wf.status = WFStatus.DONE
                self._wf.add_history("workflow_done", "all steps completed")
                self._wf.save()
                clear_context()
                return {
                    "action": "workflow_done",
                    "message": "Workflow 完成！",
                    "workflow": {"id": self._wf.id, "status": "DONE"},
                }
            else:
                # begin_step 设置为 EXECUTING
                self.begin_step()
                persist_context(self, pending_action="execute_step")
                return _build_step_response(self, self._wf.current_step_obj(), "execute_step")
        else:
            # 失败处理
            if current.attempts < 3:
                # 重试
                self._wf.add_history("step_retry", f"step={current.id} attempts={current.attempts}")
                persist_context(self, pending_action="execute_step")
                return {
                    "action": "retry_step",
                    "message": f"Step {current.id + 1} failed, retrying...",
                    "step": {
                        "id": current.id,
                        "type": current.type.value,
                        "description": current.description,
                        "attempts": current.attempts,
                    },
                    "error": error,
                }
            else:
                # 超过重试次数 → 跳过
                current.status = StepStatus.SKIPPED
                current.result = f"SKIPPED after {current.attempts} retries: {error}"
                self._wf.add_history("step_skipped", f"step={current.id} reason=max_retries")
                self._wf.save()
                # 继续推进
                return self.skip_step("max retries exceeded")

    def skip_step(self, reason: str = "User skipped") -> dict:
        """
        跳过当前步骤，推进到下一步。

        Args:
            reason: 跳过原因

        Returns:
            dict，含下一步执行指令或 workflow_done
        """
        from .persistence import persist_context, clear_context

        if not self._wf:
            return {"action": "error", "message": "No active workflow"}

        current = self._wf.current_step_obj()
        if current:
            current.status = StepStatus.SKIPPED
            current.result = f"SKIPPED: {reason}"
            self._wf.add_history("step_skipped", f"step={current.id} reason={reason}")
            self._wf.save()

        # 推进到下一步
        next_step = self._wf.next_step_obj()
        if not next_step:
            self._wf.status = WFStatus.DONE
            self._wf.add_history("workflow_done", "all steps skipped or completed")
            self._wf.save()
            clear_context()
            return {
                "action": "workflow_done",
                "message": "Workflow 完成！",
                "workflow": {"id": self._wf.id, "status": "DONE"},
            }
        else:
            self.begin_step()
            persist_context(self, pending_action="execute_step")
            return _build_step_response(self, self._wf.current_step_obj(), "execute_step")


def _build_step_response(orch, step, action: str) -> dict:
    """构建步骤执行响应"""
    from .persistence import persist_context

    if not step:
        return {"action": "workflow_done", "message": "No more steps"}

    progress = f"{step.id + 1}/{len(orch._wf.steps)}"
    icon = {"read": "📖", "write": "✏️", "cmd": "⚡", "browse": "🌐", "skill": "🔧"}.get(
        step.type.value, "▶"
    )

    persist_context(orch, pending_action="execute_step")

    return {
        "action": action,
        "message": f"{icon} [{progress}] {step.description[:60]}",
        "progress": progress,
        "step": {
            "id": step.id,
            "type": step.type.value,
            "description": step.description,
            "files_read": getattr(step, "files_read", []),
            "files_write": getattr(step, "files_write", []),
            "action": getattr(step, "action", None),
            "validation": getattr(step, "validation", {}),
        },
        "workflow": {
            "id": orch._wf.id,
            "progress": progress,
            "task": orch._wf.task,
        },
    }

