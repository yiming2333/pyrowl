# -*- coding: utf-8 -*-
"""微博数据获取模块 - WeiboScraper"""
import requests
import re
import json
import time
from typing import List, Dict


class WeiboScraper:
    BASE_URL = 'https://m.weibo.cn/api/container/getIndex'

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
            'Referer': 'https://m.weibo.cn/',
            'Accept': 'application/json, text/plain, */*',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_user_info(self, uid: str) -> Dict:
        """获取用户基本信息"""
        params = {'uid': uid, 'type': 'uid', 'containerid': '100505' + uid}
        r = self.session.get(self.BASE_URL, params=params, timeout=10)
        data = r.json()
        user_info = data.get('data', {}).get('userInfo', {})
        return {
            'id': user_info.get('id'),
            'name': user_info.get('screen_name'),
            'followers': user_info.get('followers_count', 0),
            'following': user_info.get('follow_count', 0),
            'posts': user_info.get('statuses_count', 0),
            'verified': user_info.get('verified', False),
            'description': user_info.get('description', ''),
        }

    def get_posts(self, uid: str, max_pages: int = 5) -> List[Dict]:
        """获取用户微博帖子列表（最多max_pages页，每页约10条）"""
        containerid = '107603' + uid
        posts = []
        for page in range(1, max_pages + 1):
            params = {'uid': uid, 'containerid': containerid, 'page': page}
            try:
                r = self.session.get(self.BASE_URL, params=params, timeout=10)
                data = r.json()
                cards = data.get('data', {}).get('cards', [])
                for card in cards:
                    mblog = card.get('mblog', {})
                    if mblog:
                        posts.append({
                            'mid': mblog.get('id'),
                            'text': mblog.get('text', ''),
                            'created_at': mblog.get('created_at'),
                            'reposts_count': mblog.get('reposts_count', 0),
                            'comments_count': mblog.get('comments_count', 0),
                            'attitudes_count': mblog.get('attitudes_count', 0),
                            'source': mblog.get('source'),
                        })
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Page {page} failed: {e}")
        return posts

    def get_post_detail(self, mid: str) -> str:
        """获取单条微博详情（含长文本）"""
        url = f'https://m.weibo.cn/detail/{mid}'
        try:
            r = self.session.get(url, timeout=10)
            match = re.search(
                r'\$render_data\s*=\s*\[\\d+\]\s*\|\|\s*\({.*}\)\[\\0\\\]\;',
                r.text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data.get('status', {}).get('text', '')
        except Exception as e:
            print(f"[WARN] Detail {mid} failed: {e}")
        return ''

if __name__ == '__main__':
    print('WeiboScraper ready. Usage: s = WeiboScraper(); info = s.get_user_info(uid)')
