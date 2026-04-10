# -*- coding: utf-8 -*-
# pyrowl/planner.py - M2: 任务拆解器

import json, os, re, pathlib
from typing import Optional, List, Dict

# Planning prompt template
PLANNING_PROMPT = """你是一个任务拆解专家。用户提出了一个任务，请拆解成具体的执行步骤。

任务：TASK_PLACEHOLDER

请按以下 JSON 格式输出步骤列表（不要输出其他内容）：
{ "steps": [ { "description": "步骤描述", "type": "cmd|write|read" } ] }

步骤类型规则：
- read: 分析/调研/获取/下载/读取/理解/查看（信息获取类）
- write: 创建/编写/开发/设计/搭建/实现/配置/保存/导出/生成/画/制作（生产创造类）
- cmd: 运行/测试/部署/安装/执行/启动/验证/清理（执行操作类）

原则：
- 大部分步骤应该是 write 类型（开发任务的核心是创建东西）
- read 类型只在明确需要"先调研/分析"时使用
- cmd 类型只在运行/测试/部署时使用
- 每个步骤应该可以独立验证
- 步骤数量建议 3-8 步
"""


def call_openclaw_model(prompt: str, model: str = None) -> str:
    """调用 OpenClaw model API 做 planning"""
    import json as _json
    import urllib.request

    # 从 ~/.qclaw/openclaw.json 读取 gateway 配置
    cfg_path = pathlib.Path.home() / '.qclaw' / 'openclaw.json'
    if not cfg_path.exists():
        return None
    try:
        cfg = _json.loads(open(cfg_path, encoding='utf-8').read())
        gw = cfg.get('gateway', {})
        port = gw.get('port', 28789)
        token = gw.get('auth', {}).get('token', '')
        base_url = f"http://127.0.0.1:{port}"
    except Exception:
        return None

    # 确定 model
    model_id = model or 'modelroute'

    data = _json.dumps({
        "model": model_id,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 800
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception:
        return None


def parse_plan_from_text(text: str) -> List[Dict]:
    """从 model 输出中提取 JSON plan"""
    if not text:
        return []
    patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
        r'\{[^{}]*?"steps"\s*:\s*\[.*?\]\s*\}',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                raw = m.group(1) if m.lastindex else m.group(0)
                data = json.loads(raw)
                if "steps" in data and isinstance(data["steps"], list):
                    return data["steps"]
            except Exception:
                continue
    return []


def _guess_step_type(text: str) -> str:
    # 高优先级：复合模式优先匹配
    # "初始化/部署/配置" 等建设性动作优先于内含的分析/读取关键词
    write_compound = ['初始化', '项目初始化', '环境配置', '创建项目', '搭建项目',
                      '新建项目', '生成报告', '导出数据', '保存文件']
    cmd_compound = ['部署到', '上线到', '发布版本', '运行测试', '执行脚本',
                    '安装依赖', '清理缓存', '验证结果']

    if any(text.startswith(kw) or text.endswith(kw) or f' {kw}' in text for kw in cmd_compound):
        return 'cmd'
    if any(text.startswith(kw) or text.endswith(kw) or f' {kw}' in text for kw in write_compound):
        return 'write'

    # read: 分析/研究/理解/调研/获取/下载/收集/抓取/查看/读取
    if any(kw in text for kw in [
        '分析', '统计', '挖掘', '建模', '读取', '扫描', '查看',
        '调研', '理解', '了解', '获取数据', '下载数据', '抓取数据',
        '收集', '检索', '搜索', '爬取', '需求分析', '可行性',
        '获取股票', '获取接口', '获取API', '读取文件', '解析数据',
    ]):
        return 'read'
    # write: 写/创建/新建/搭建/开发/制作/构建/设计/保存/导出/生成/编写
    if any(kw in text for kw in [
        '写', '创建', '新建', '搭建', '开发', '制作', '构建', '设计',
        '保存', '导出', '生成', '编写', '画', '绘制', '渲染',
        '初始化', '配置', '集成', '封装', '打包',
        '实现', '编写代码', '写代码', '保存为',
        '做一', '做一个',
        '画像', '图表', '趋势', '列表', '界面', '页面', '模块',
        '功能', '接口', '表单', '组件', '布局', '样式',
    ]):
        return 'write'
    # cmd: 部署/上线/发布/安装/跑/运行/执行/测试/清理/验证
    return 'cmd'


def quick_parse(task: str) -> List[Dict]:
    """从任务文本中用关键词启发式拆解多个步骤"""
    if not task:
        return []
    steps = []
    main_task = re.sub(r'^(帮我|给我|给我做|帮我做|我想要)\s*', '', task).strip()

    # 策略1：识别子任务列表（包含/需要/包括/支持）
    list_markers = ['包含', '包括', '需要', '支持', '具备', '含']
    sub_parts = []
    remaining = main_task
    has_subtasks = False
    for marker in list_markers:
        if marker in remaining:
            parts = remaining.split(marker, 1)
            remaining = parts[0].strip().rstrip('，,')  # 清理尾部逗号
            if len(parts) > 1:
                sub = [s.strip() for s in re.split(r'[,，、和与]+', parts[1]) if s.strip() and len(s.strip()) >= 2]
                sub_parts.extend(sub)
                has_subtasks = True

    # 主任务处理：
    # - 有子任务列表时：推断一个初始化步骤（如"项目初始化"）
    # - 无子任务列表时：不加主任务，让策略2-4处理（避免重复）
    if remaining and has_subtasks:
        # 有子任务时，推断一个合理的初始化步骤
        if any(kw in remaining for kw in ['工具', '系统', '平台', '应用']):
            init_step = f"{remaining.rstrip('工具系统平台应用')}项目初始化"
            if len(init_step) >= 4:
                steps.append({'description': init_step, 'type': 'cmd'})

    # 子任务
    seen = {s['description'].lower() for s in steps}
    for sub in sub_parts:
        nl = sub.lower()
        if nl and nl not in seen and len(sub) >= 2:
            seen.add(nl)
            steps.append({'description': sub, 'type': _guess_step_type(sub)})

    # 策略2：如果步骤太少，按逗号/分号拆分
    if len(steps) < 2:
        parts = re.split(r'[,，；]+', main_task)
        for part in parts:
            part = part.strip()
            nl = part.lower()
            if part and len(part) >= 4 and nl not in seen:
                seen.add(nl)
                steps.append({'description': part, 'type': _guess_step_type(part)})

    # 策略3：检测技术栈关键词，推断额外步骤
    tech_kw = {
        '前端': '前端界面开发', '后端': '后端 API 开发',
        '数据库': '数据库设计', '爬虫': '数据爬取逻辑',
        'API': 'API 接口对接', '登录': '登录认证功能',
        '图表': '数据图表开发', '可视化': '可视化页面',
        '页面': '页面结构搭建', '系统': '系统架构设计',
    }
    for kw, extra in tech_kw.items():
        if kw in main_task and not any(kw in s['description'] for s in steps):
            steps.append({'description': extra, 'type': 'write'})

    # 策略4：阶段词拆分（先/然后/再/接着）
    if len(steps) < 2:
        stage_markers = ['先', '然后', '再', '接着', '最后']
        for marker in stage_markers:
            idx = main_task.find(marker)
            if idx > 0:
                part = main_task[idx:].strip()
                if len(part) >= 4:
                    steps.append({'description': part, 'type': _guess_step_type(part)})

    # 去重
    seen2 = set()
    unique = []
    for s in steps:
        norm = s['description'].lower().strip()
        if norm and norm not in seen2 and len(s['description']) >= 2:
            seen2.add(norm)
            unique.append(s)

    return unique[:8]


def plan_task(task: str, context: str = "") -> List[Dict]:
    """主入口：给定任务，返回结构化步骤列表"""
    prompt = PLANNING_PROMPT.replace("TASK_PLACEHOLDER", task)
    if context:
        prompt += "\n\n当前项目上下文：\n" + context[:500]
    result = call_openclaw_model(prompt)
    if result:
        steps = parse_plan_from_text(result)
        if steps:
            return steps
    return quick_parse(task)


def apply_plan(orch, steps: List[Dict]):
    """将拆解结果应用到 orchestrator"""
    if not orch.active:
        return
    orch.set_steps(steps)
    if orch.wf:
        orch.wf.add_history("plan_applied", str(len(steps)) + " steps")
    return orch.wf
