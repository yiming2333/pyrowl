# -*- coding: utf-8 -*-
# pyrowl/context_builder.py - M3: 文件级上下文加载器

import os, re, hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

# 忽略模式
IGNORE_NAMES = {
    "__pycache__", ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv", "env",
    "dist", "build", ".egg-info",
    ".DS_Store", "Thumbs.db",
    ".pyrowl_ignore",
}
IGNORE_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".mp4", ".avi", ".mov", ".mp3", ".wav", ".flac",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".db", ".sqlite", ".sqlite3",
    ".pyc", ".pyo", ".class",
}
MAX_FILE_KB = 200
MAX_DIR_DEPTH = 5


class _CtxCache:
    """上下文缓存，避免重复 IO"""

    def __init__(self):
        self._cache: Dict[str, tuple] = {}  # path -> (content, mtime)

    def get(self, filepath: str) -> Optional[str]:
        try:
            mtime = os.path.getmtime(filepath)
            if filepath in self._cache and self._cache[filepath][1] == mtime:
                return self._cache[filepath][0]
        except Exception:
            pass
        return None

    def set(self, filepath: str, content: str):
        try:
            self._cache[filepath] = (content, os.path.getmtime(filepath))
        except Exception:
            pass

    def clear(self):
        self._cache.clear()


_ctx_cache = _CtxCache()


def _should_ignore(fp: Path) -> bool:
    if fp.name in IGNORE_NAMES:
        return True
    if fp.suffix.lower() in IGNORE_SUFFIXES:
        return True
    for pat in IGNORE_NAMES:
        if pat in str(fp):
            return True
    return False


def _read_file(fp: Path, max_lines: int = 300) -> Optional[str]:
    """智能读取文件，支持大文件截断和编码自动检测"""
    if not fp.is_file():
        return None
    try:
        size_kb = fp.stat().st_size / 1024
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
            try:
                with open(fp, "r", encoding=enc) as f:
                    if size_kb > MAX_FILE_KB:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= max_lines:
                                lines.append(f"\n... [truncated, {size_kb:.0f}KB total]")
                                break
                            lines.append(line)
                        return "".join(lines)
                    return f.read()
            except UnicodeDecodeError:
                continue
    except Exception:
        pass
    return None


def _scan_dir(root: Path, types: List[str] = None, max_depth: int = MAX_DIR_DEPTH) -> List[Path]:
    """扫描目录，返回匹配文件"""
    results = []
    types_lower = [t.lower() for t in (types or [])]

    def _walk(d: Path, depth: int):
        if depth > max_depth:
            return
        try:
            items = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for item in items:
                if _should_ignore(item):
                    continue
                if item.is_file():
                    if types and not any(re.match(t if t.startswith(".") else r".*\." + t, item.name, re.I)
                                         for t in types_lower):
                        continue
                    results.append(item)
                elif item.is_dir():
                    _walk(item, depth + 1)
        except PermissionError:
            pass

    _walk(root)
    return results


def _keyword_score(fp: Path, keywords: List[str], content: str) -> int:
    """计算文件与关键词的匹配分数"""
    rel = str(fp).lower()
    name = fp.name.lower()
    score = 0
    for kw in keywords:
        kl = kw.lower()
        if kl in rel:
            score += 10
        if kl in name:
            score += 5
        if content and kl in content.lower():
            score += 2
    return score


def build_context(
    project_root: str,
    keywords: List[str],
    types: List[str] = None,
    max_files: int = 10,
    max_chars: int = 8000,
) -> str:
    """
    基于关键词加载相关文件上下文
    """
    root = Path(project_root)
    if not root.exists():
        return "[pyrowl] project root not found: " + project_root

    files = _scan_dir(root, types)
    kw_lower = [k.lower() for k in keywords]

    scored = []
    for fp in files:
        content = _ctx_cache.get(str(fp))
        if content is None:
            content = _read_file(fp) or ""
            _ctx_cache.set(str(fp), content)
        score = _keyword_score(fp, kw_lower, content)
        if score > 0:
            scored.append((score, len(content), fp, content))

    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    selected = scored[:max_files]

    if not selected:
        return "[pyrowl] No keyword matches. Directory overview:\n" + _dir_overview(root)

    parts = []
    total = 0
    for score, _, fp, content in selected:
        rel = str(fp.relative_to(root))
        header = "\n" + "=" * 50 + "\n// " + rel + "\n" + "=" * 50 + "\n"
        needed = len(header) + len(content)
        if total + needed > max_chars:
            remaining = max_chars - total - len(header) - 30
            if remaining > 0:
                parts.append(header + content[:remaining] + "\n... [truncated]")
            break
        parts.append(header + content)
        total += needed

    return "".join(parts) if parts else "[pyrowl] context empty"


def get_project_context(project_root: str, task: str, types: List[str] = None) -> str:
    """
    高级入口：从任务描述自动提取关键词，加载上下文
    """
    words = re.findall(r"[\w]{3,30}", task.lower())
    stop = {"the", "and", "for", "that", "this", "with", "from", "file", "project",
            "task", "build", "make", "create", "add", "fix", "update", "check",
            "run", "test", "have", "can", "not", "but", "all", "need", "want",
            "一个", "的", "了", "是", "在", "和", "要", "做", "到", "说", "看",
            "我", "你", "他", "她", "它", "我们", "什么", "怎么"}
    keywords = [w for w in words if w not in stop and len(w) >= 3]
    return build_context(project_root, keywords, types)


def _dir_overview(root: Path, max_lines: int = 60) -> str:
    """生成目录树概览"""
    lines = []

    def walk(d: Path, indent: int = 0):
        if len(lines) >= max_lines:
            return
        try:
            items = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for item in items:
                if _should_ignore(item):
                    continue
                suffix = "/" if item.is_dir() else ""
                lines.append("  " * indent + item.name + suffix)
                if item.is_dir() and indent < 2:
                    walk(item, indent + 1)
        except PermissionError:
            pass
        except OSError:
            pass

    walk(root)
    return "\n".join(lines[:max_lines])
