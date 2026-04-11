# -*- coding: utf-8 -*-
"""心理学人格分析引擎 - 弗洛伊德 / 荣格 / 阿德勒"""
from typing import Dict, List


class PsychologyEngine:
    """整合三大心理学派的人格分析引擎"""

    FREUD_PATTERNS = {
        'id_drive': ['欲望', '本能', '冲动', '压抑', '潜意识', '童年', '梦', '焦虑'],
        'defense': ['否认', '投射', '合理化', '升华', '退行', '转移', '自我防御'],
        'structure': ['本我', '自我', '超我', '道德', '内疚', '羞耻'],
    }

    JUNG_PATTERNS = {
        'archetype': ['阴影', '人格面具', '阿尼玛', '阿尼姆斯', '自性', '集体潜意识'],
        'cognitive': ['直觉', '感觉', '思维', '情感', '内倾', '外倾', '性格类型'],
        'complex': ['自卑情结', '权力情结', '母亲情结', '父亲情结', '未愈合'],
    }

    ADLER_PATTERNS = {
        'lifestyle': ['优越感', '自卑感', '生活风格', '创造性自我', '个人目标'],
        'social': ['合作', '归属感', '社会兴趣', '共同体感觉', '朋友圈', '人际'],
        'goal': ['追求卓越', '虚构目的论', '目标导向', '动力', '成就', '野心'],
    }

    def analyze_text(self, texts: List[str]) -> Dict:
        """分析微博文本，返回三派分析结果"""
        combined = ' '.join(texts)
        freud = self._score(combined, self.FREUD_PATTERNS)
        jung = self._score(combined, self.JUNG_PATTERNS)
        adler = self._score(combined, self.ADLER_PATTERNS)
        return {
            'freud': {'scores': freud, 'profile': self._freud(freud)},
            'jung': {'scores': jung, 'profile': self._jung(jung)},
            'adler': {'scores': adler, 'profile': self._adler(adler)},
            'summary': self._summary(freud, jung, adler),
        }

    def _score(self, text: str, patterns: Dict) -> Dict:
        return {
            k: round(sum(1 for kw in kws if kw in text) / max(len(kws), 1) * 100, 1)
            for k, kws in patterns.items()
        }

    def _freud(self, scores: Dict) -> str:
        dom = max(scores, key=scores.get)
        profiles = {
            'id_drive': '强烈本我驱动，关注本能与欲望表达，可能存在冲动控制问题',
            'defense': '防御机制活跃，心理自我保护意识强，善于情感隔离',
            'structure': '超我约束明显，道德感强，易产生内疚与自我批判',
        }
        return profiles.get(dom, '人格结构相对平衡') if scores.get(dom, 0) > 25 else '弗洛伊德特征不明显'

    def _jung(self, scores: Dict) -> str:
        dom = max(scores, key=scores.get)
        profiles = {
            'archetype': '原型意识强，集体潜意识影响显著，善于象征性思维',
            'cognitive': '认知风格偏向直觉/感觉类型，对外部信息敏感',
            'complex': '存在明显情结倾向，可能有未解决的心理议题',
        }
        return profiles.get(dom, '荣格特征不明显') if scores.get(dom, 0) > 25 else '荣格特征不明显'

    def _adler(self, scores: Dict) -> str:
        dom = max(scores, key=scores.get)
        profiles = {
            'lifestyle': '生活风格已形成，追求优越目标，自我驱动型人格',
            'social': '社会兴趣强，注重合作与归属，人际导向明显',
            'goal': '高度目标导向，追求成就与卓越，竞争意识强',
        }
        return profiles.get(dom, '阿德勒特征不明显') if scores.get(dom, 0) > 25 else '阿德勒特征不明显'

    def _summary(self, freud: Dict, jung: Dict, adler: Dict) -> str:
        fs = max(freud.values()) if freud else 0
        js = max(jung.values()) if jung else 0
        as_ = max(adler.values()) if adler else 0
        return (
            f"人格综合画像：\n"
            f"  弗洛伊德维度（{fs:.0f}%）：{self._freud(freud)}\n"
            f"  荣格维度（{js:.0f}%）：{self._jung(jung)}\n"
            f"  阿德勒维度（{as_:.0f}%）：{self._adler(adler)}\n"
        )


if __name__ == '__main__':
    engine = PsychologyEngine()
    sample = ['今天加班很压抑，深深的自卑感涌上来', '但还是要努力追求更好的自己']
    print(engine.analyze_text(sample)['summary'])
