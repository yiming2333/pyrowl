# -*- coding: utf-8 -*-
"""福尔摩斯推理模块 - 演绎法查漏补缺核验"""
from typing import Dict, List


class HolmesAnalyzer:
    """以福尔摩斯视角验证人格画像的可靠性与一致性"""

    def verify_profile(self, psych_result: Dict, posts: List[Dict]) -> Dict:
        posts_text = ' '.join([p.get('text', '') for p in posts[:20]])
        consistency = self._check_consistency(psych_result, posts_text)
        blind_spots = self._find_blind_spots(psych_result, posts)
        contradictions = self._find_contradictions(psych_result, posts)
        notes = self._deductive_notes(psych_result, posts)
        verdict = self._final_verdict(consistency, blind_spots, contradictions)
        return {
            'consistency_score': consistency,
            'blind_spots': blind_spots,
            'contradictions': contradictions,
            'deductive_notes': notes,
            'final_verdict': verdict,
        }

    def _check_consistency(self, psych: Dict, text: str) -> float:
        scores = psych or {}
        all_scores = []
        for school in scores.get('freud', {}).get('scores', {}).values():
            all_scores.append(school)
        for school in scores.get('jung', {}).get('scores', {}).values():
            all_scores.append(school)
        for school in scores.get('adler', {}).get('scores', {}).values():
            all_scores.append(school)
        avg = sum(all_scores) / max(len(all_scores), 1)
        return round(min(100, avg * 1.1), 1)

    def _find_blind_spots(self, psych: Dict, posts: List[Dict]) -> List[str]:
        spots = []
        posts_text = ' '.join([p.get('text', '') for p in posts[:20]])
        if len(posts) < 5:
            spots.append('数据量极少（<5条），分析偏差风险高')
        if '深夜' not in posts_text and '凌晨' not in posts_text:
            spots.append('未观察到深夜发文习惯（情绪波动期表达缺失）')
        if posts_text.count('转发') > posts_text.count('原创') * 2:
            spots.append('以转发为主，主动表达受限，需判断社交策略类型')
        time_patterns = self._analyze_time_pattern(posts)
        if time_patterns:
            spots.append('时间模式：' + time_patterns)
        if not spots:
            spots.append('数据覆盖较好，未发现明显盲点')
        return spots

    def _analyze_time_pattern(self, posts: List[Dict]) -> str:
        times = [p.get('created_at', '') for p in posts if p.get('created_at')]
        if len(times) < 3:
            return ''
        late_night = sum(1 for t in times if any(k in t for k in ['00:', '01:', '02:', '03:', '23:']))
        if late_night > len(times) * 0.3:
            return '高频深夜发文，提示情绪管理问题或高压状态'
        return ''

    def _find_contradictions(self, psych: Dict, posts: List[Dict]) -> List[str]:
        contradictions = []
        try:
            freud_drive = psych.get('freud', {}).get('scores', {}).get('id_drive', 0)
            if freud_drive > 60 and len(posts) < 5:
                contradictions.append('弗洛伊德本我特征极高但发帖极少，存在强烈表达抑制')
            adler_social = psych.get('adler', {}).get('scores', {}).get('social', 0)
            posts_text = ' '.join([p.get('text', '') for p in posts[:10]])
            if adler_social > 60 and '朋友' not in posts_text and '合作' not in posts_text:
                contradictions.append('阿德勒社会兴趣高但内容中未见人际关系表达')
        except Exception:
            pass
        if not contradictions:
            contradictions.append('未发现明显矛盾，人格画像与行为数据基本一致')
        return contradictions

    def _deductive_notes(self, psych: Dict, posts: List[Dict]) -> str:
        notes = ['=== 福尔摩斯推理分析 ===']
        notes.append(f'观察到{len(posts)}条微博，时间跨度反映行为模式')
        notes.append('基于行为模式的演绎推理：')
        posts_text = ' '.join([p.get('text', '') for p in posts[:10]])
        if any(w in posts_text for w in ['加班', '工作', '压力', '辞职']):
            notes.append('  -> 工作压力信号明显，可能是现实自我与理想自我的冲突点')
        if any(w in posts_text for w in ['健身', '跑步', '运动']):
            notes.append('  -> 存在积极自我调节行为，提示自我管理意识强')
        if any(w in posts_text for w in ['朋友', '聚会', '社交']):
            notes.append('  -> 社交活动频繁，社会兴趣指标验证阿德勒理论')
        return '\n'.join(notes)

    def _final_verdict(self, score: float, spots: List, contradictions: List) -> str:
        gaps = len([s for s in spots if '风险' in s or '极少' in s or '高频' in s])
        gaps += len([c for c in contradictions if '未发现' not in c])
        if score >= 75 and gaps == 0:
            return f'综合判断：人格画像可靠性高（{score}%），各维度一致，予以采信'
        elif score >= 60:
            return f'综合判断：人格画像基本可靠（{score}%），存在{gaps}处次要偏差，供参考'
        else:
            return f'综合判断：数据量不足或一致性较低（{score}%），画像可靠性存疑，建议补充数据后再分析'


if __name__ == '__main__':
    holmes = HolmesAnalyzer()
    psych = {
        'freud': {'scores': {'id_drive': 60, 'defense': 40}},
        'jung': {'scores': {'archetype': 30}},
        'adler': {'scores': {'social': 50}},
    }
    posts = [{'text': '今天加班很压抑', 'created_at': '2024-01-01 23:30'}] * 5
    r = holmes.verify_profile(psych, posts)
    print(r['final_verdict'])
