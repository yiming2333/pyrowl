# -*- coding: utf-8 -*-
"""微博人格分析工具 - 测试套件"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from weibo_profiler.psychology_engine import PsychologyEngine
from weibo_profiler.holmes_analyzer import HolmesAnalyzer


def test_psychology_engine():
    print("=== 心理学引擎测试 ===")
    engine = PsychologyEngine()
    sample = [
        "今天被老板批评了，感觉很压抑，工作没有意义，深夜的失眠让我很焦虑",
        "深夜睡不着，思考人生的意义到底是什么，童年的创伤似乎还在影响我",
        "健身能让心情变好，我要努力追求更好的自己，目标导向明确",
        "和朋友的聚会很开心，大家一起合作完成项目很有成就感",
    ]
    result = engine.analyze_text(sample)
    print(result['summary'])
    assert result['freud'], "心理学分析失败"
    print("[PASS] PsychologyEngine\n")

def test_holmes_analyzer():
    print("=== 福尔摩斯推理测试 ===")
    holmes = HolmesAnalyzer()
    psych = {
        'freud': {'scores': {'id_drive': 65, 'defense': 30}},
        'jung': {'scores': {'archetype': 40}},
        'adler': {'scores': {'social': 55}},
    }
    posts = [
        {'text': '加班到深夜，很压抑', 'created_at': '2024-01-01 23:30'},
        {'text': '今天跑了10公里，状态不错', 'created_at': '2024-01-02 07:00'},
        {'text': '和朋友聚会很开心', 'created_at': '2024-01-03 20:00'},
    ]
    r = holmes.verify_profile(psych, posts)
    print("综合评分:", r['consistency_score'])
    print("盲点:", r['blind_spots'])
    print("结论:", r['final_verdict'])
    print("[PASS] HolmesAnalyzer\n")

def test_import():
    print("=== 导入测试 ===")
    from weibo_profiler import WeiboScraper
    s = WeiboScraper()
    print("[PASS] All imports OK\n")

if __name__ == '__main__':
    test_import()
    test_psychology_engine()
    test_holmes_analyzer()
    print("=" * 50)
    print("All tests PASSED!")
    print("=" * 50)
    print("\n使用说明:")
    print("  python test_profiler.py  # 本地测试（无需真实微博数据）")
    print("  python weibo_profiler.py <微博链接>  # 真实分析")
