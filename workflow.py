# -*- coding: utf-8 -*-
# pyrowl/workflow.py - M1: 核心状态机 + 持久化

import json, os, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

PYROWL_DIR = Path.home() / ".qclaw" / "pyrowl"
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
                 validation=None, rollback=None):
        self.id = sid
        self.description = description
        self.type = step_type
        self.action = action
        self.validation = validation or {}
        self.rollback = rollback
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
                 validation=None, rollback=None):
        self._counter += 1
        t = step_type.value if hasattr(step_type, "value") else step_type
        st = Step(self._counter - 1, description, StepType(t), action, validation, rollback)
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
                self._wf.add_step(s["description"], s.get("type", "cmd"),
                                  s.get("action"), s.get("validation"), s.get("rollback"))
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
            self._wf.add_step(s["description"], s.get("type", "cmd"),
                              s.get("action"), s.get("validation"), s.get("rollback"))
        self._wf.current_step = 0
        self._wf.status = WFStatus.EXECUTING
        self._wf.save()

    def begin_step(self):
        if not self._wf:
            return None
        step = self._wf.next_step_obj()
        if step:
            step.status = StepStatus.EXECUTING
            step.attempts += 1
            self._wf.status = WFStatus.EXECUTING
            self._wf.current_step = step.id
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
