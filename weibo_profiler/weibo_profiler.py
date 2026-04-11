# -*- coding: utf-8 -*-
"""微博人物性格画像分析工具 - 主程序"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

from weibo_scraper import WeiboScraper
from psychology_engine import PsychologyEngine
from holmes_analyzer import HolmesAnalyzer


def extract_uid(weibo_url: str) -> str:
    """从微博URL提取uid或username"""
    patterns = [
        r'weibo\.com/u/(\d+)',
        r'weibo\.com/(\d+)',
        r'weibo\.com/([a-zA-Z][\w]{2,14})(?:\?|$)',
    ]
    for pat in patterns:
        m = re.search(pat, weibo_url)
        if m:
            return m.group(1)
    return None


def analyze(weibo_url: str, max_pages: int = 5) -> dict:
    uid = extract_uid(weibo_url)
    if not uid:
        return {'error': '无法从URL提取用户ID，请检查链接格式是否正确'}

    scraper = WeiboScraper()
    engine = PsychologyEngine()
    holmes = HolmesAnalyzer()

    # 1. 获取用户信息
    print(f"[1/4] 获取用户信息 uid={uid}...")
    user_info = scraper.get_user_info(uid)
    print(f"  -> {user_info.get('name')} | {user_info.get('followers')}粉丝 | {user_info.get('posts')}条微博")

    # 2. 获取帖子
    print(f"[2/4] 获取微博帖子（最多{max_pages}页）...")
    posts = scraper.get_posts(uid, max_pages=max_pages)
    print(f"  -> 获取到{len(posts)}条微博")

    # 3. 心理学分析
    print("[3/4] 心理学人格分析（弗洛伊德/荣格/阿德勒）...")
    texts = [p['text'] for p in posts if p.get('text')]
    psych_result = engine.analyze_text(texts)
    print("  ->", psych_result['summary'].replace(chr(10), ' | '))

    # 4. 福尔摩斯验证
    print("[4/4] 福尔摩斯演绎推理核验...")
    verification = holmes.verify_profile(psych_result, posts)
    print("  ->", verification['final_verdict'])

    return {
        'user': user_info,
        'posts_count': len(posts),
        'psychology': psych_result,
        'verification': verification,
    }


if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"分析微博用户：{url}")
        print("=" * 50)
        result = analyze(url)
        print("=" * 50)
        print("\n最终报告：")
        print(result['psychology']['summary'])
        print(result['verification']['final_verdict'])
    else:
        print("用法: python weibo_profiler.py <微博链接>")
        print("示例: python weibo_profiler.py https://weibo.com/u/1195230310")
        print("      python weibo_profiler.py https://weibo.com/helloworld")
