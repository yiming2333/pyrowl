# -*- coding: utf-8 -*-
# pyrowl/validation_loop.py - M4: run-fail-fix-retry 循环

import subprocess, re, time, os
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class ValResult(str, Enum):
    PASS  = "PASS"
    FAIL  = "FAIL"
    ERROR = "ERROR"
    SKIP  = "SKIP"


class ValidationLoop:
    """
    执行一步并验证，失败时自动修复重试（最多 max_retries 次）

    验证类型：
      returncode    - 检查退出码
      stderr        - 检查 stderr 是否包含/不含某字符串
      stdout        - 检查 stdout 是否包含/不含某字符串
      file_exists   - 检查文件是否存在
      output_match  - 用 regex 匹配 output
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.history: list = []

    # ---- 验证器 ----

    def validate(self, rule: Dict, result: Dict) -> ValResult:
        vtype = rule.get("type", "returncode")
        expected = rule.get("expected")
        invert = bool(rule.get("invert", False))

        if vtype == "returncode":
            rc = result.get("returncode", 1)
            ok = (rc == expected) if expected is not None else (rc == 0)
            return ValResult.PASS if ok else ValResult.FAIL

        elif vtype == "stderr":
            err = result.get("stderr", "")
            if expected is not None:
                ok = expected in err
            else:
                ok = err == ""
            return ValResult.PASS if ok ^ invert else ValResult.FAIL

        elif vtype == "stdout":
            out = result.get("stdout", "")
            if expected is not None:
                ok = expected in out
            else:
                ok = out != ""
            return ValResult.PASS if ok ^ invert else ValResult.FAIL

        elif vtype == "file_exists":
            ok = os.path.exists(str(expected)) if expected else False
            return ValResult.PASS if ok ^ invert else ValResult.FAIL

        elif vtype == "output_match":
            out = result.get("stdout", "") + "\n" + result.get("stderr", "")
            m = re.search(str(expected or ""), out, re.MULTILINE | re.DOTALL)
            ok = m is not None
            return ValResult.PASS if ok ^ invert else ValResult.FAIL

        return ValResult.SKIP

    # ---- 错误解析 ----

    def parse_error(self, result: Dict) -> Optional[str]:
        """从错误输出中识别问题类型"""
        combined = result.get("stderr", "") + "\n" + result.get("stdout", "")
        patterns = [
            (r"No module named ['\"]?([\w.]+)['\"]?", "missing_module"),
            (r"SyntaxError[:\s]", "syntax_error"),
            (r"ImportError[:\s]", "import_error"),
            (r"File[\s(].*?not found", "file_not_found"),
            (r"Permission denied", "permission_error"),
            (r"command not found|not recognized", "command_not_found"),
            (r"ECONNREFUSED|ECONNRESET", "connection_error"),
            (r"timeout|Timeout|timed out", "timeout_error"),
            (r"npm ERR!", "npm_error"),
            (r"pip install|requirements", "pip_error"),
            (r"exit code \d+", "exit_code_nonzero"),
            (r"UnicodeDecodeError|UnicodeEncodeError", "encoding_error"),
            (r"JSONDecodeError|Expecting value", "json_error"),
        ]
        for pat, err_type in patterns:
            if re.search(pat, combined, re.I):
                return err_type
        return None

    def suggest_fix(self, err_type: str, step_action: str = "") -> Optional[str]:
        """根据错误类型给出修复建议"""
        fixes = {
            "missing_module": None,
            "syntax_error": "Fix the syntax error shown above",
            "import_error": "Check import paths and package installation",
            "file_not_found": "Verify the file path is correct",
            "permission_error": "Check file/directory permissions",
            "command_not_found": "Install the required command-line tool",
            "connection_error": "Check network connectivity",
            "timeout_error": "Increase timeout or check network",
            "npm_error": "Run: npm install in the project directory",
            "pip_error": "Run: pip install -r requirements.txt",
            "encoding_error": "Check file encoding (try UTF-8)",
            "json_error": "Validate JSON syntax",
        }
        fix = fixes.get(err_type)
        if fix is None and err_type == "missing_module":
            m = re.search(r"No module named ['\"]?([\w.]+)['\"]?", step_action + "\n" +
                          (result.get("stderr", "") if "result" in dir() else ""))
            if m:
                fix = f"pip install {m.group(1).split('.')[0]}"
        return fix

    # ---- 执行 ----

    def execute_and_validate(
        self,
        step_action: str,
        step_type: str,
        validation_rule: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        主入口：执行 + 验证 + 失败重试

        Returns:
            {
                "result": "PASS"|"FAIL"|"ERROR",
                "output": stdout,
                "stderr": stderr,
                "returncode": int,
                "attempts": int,
                "fix_suggestion": str or None,
                "history": [每次执行结果],
            }
        """
        attempts = 0
        history = []
        last_result = {}

        while attempts < self.max_retries:
            attempts += 1

            # 执行
            exec_result = self._execute_step(step_action, step_type)
            last_result = exec_result
            history.append({
                "attempt": attempts,
                "returncode": exec_result.get("returncode"),
                "stderr_snippet": exec_result.get("stderr", "")[:200],
            })

            # 验证
            if not validation_rule:
                val_res = ValResult.PASS
            else:
                val_res = self.validate(validation_rule, exec_result)

            if val_res == ValResult.PASS:
                err_type = self.parse_error(exec_result)
                return {
                    "result": "PASS",
                    "output": exec_result.get("stdout", ""),
                    "stderr": exec_result.get("stderr", ""),
                    "returncode": exec_result.get("returncode", 0),
                    "attempts": attempts,
                    "history": history,
                    "fix_suggestion": None,
                }

            # 失败 → 指数退避重试
            if attempts < self.max_retries:
                delay = self.retry_delay * (2 ** (attempts - 1))
                if delay > 0:
                    time.sleep(delay)

        # 超过重试次数
        err_type = self.parse_error(last_result)
        return {
            "result": "FAIL",
            "output": last_result.get("stdout", ""),
            "stderr": last_result.get("stderr", ""),
            "returncode": last_result.get("returncode", 1),
            "attempts": attempts,
            "history": history,
            "fix_suggestion": self.suggest_fix(err_type or "", step_action),
        }

    def _execute_step(self, action: str, step_type: str) -> Dict[str, Any]:
        if step_type == "cmd":
            return self._run_cmd(action)
        elif step_type == "write":
            return self._check_write(action)
        elif step_type == "read":
            return self._check_read(action)
        else:
            return {"returncode": 0, "stdout": "skipped", "stderr": ""}

    def _run_cmd(self, cmd: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=60, encoding="utf-8", errors="replace",
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": "",
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "Command timed out (60s)"}
        except Exception as e:
            return {"returncode": 1, "stdout": "", "stderr": str(e)}

    def _check_write(self, filepath: str) -> Dict[str, Any]:
        exists = os.path.exists(filepath)
        return {
            "returncode": 0 if exists else 1,
            "stdout": f"File {'exists' if exists else 'NOT found'}: {filepath}",
            "stderr": "" if exists else f"File not found: {filepath}",
        }

    def _check_read(self, filepath: str) -> Dict[str, Any]:
        try:
            content = open(filepath, "r", encoding="utf-8", errors="ignore").read(200)
            return {"returncode": 0, "stdout": content[:200], "stderr": ""}
        except Exception as e:
            return {"returncode": 1, "stdout": "", "stderr": str(e)}


# ---- standalone smoke test ----
if __name__ == "__main__":
    vl = ValidationLoop(max_retries=2, retry_delay=0.1)

    # Test: 成功命令
    r = vl.execute_and_validate("echo hello", "cmd", {"type": "stdout", "expected": "hello"})
    print(f"Test 1 (PASS expected): {r['result']}, attempts={r['attempts']}")

    # Test: 失败命令
    r = vl.execute_and_validate("exit 1", "cmd", {"type": "returncode", "expected": 0})
    print(f"Test 2 (FAIL expected): {r['result']}, attempts={r['attempts']}")

    # Test: 无验证
    r = vl.execute_and_validate("echo ok", "cmd", None)
    print(f"Test 3 (PASS no rule): {r['result']}")

    # Test: file_exists
    r = vl.execute_and_validate(__file__, "write", {"type": "file_exists", "expected": __file__})
    print(f"Test 4 (PASS file exists): {r['result']}")

    print("All tests done.")
