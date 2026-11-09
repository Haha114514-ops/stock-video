# -*- coding: utf-8 -*-
"""rlib.py —— stock-report 的公共小件：找 stock-video 目录、冻结数字（put）、估值分位、近一年窗口、读 facts。

stock-report 不另抓数、不另写口径：抓数（fetch_data.py / fetch_hk.py / report_cut.py）、看 facts（facts_peek.py）、
口径（方法与口径.md）都用 stock-video 的。这里的 put / pct_stats / window_1y 和 stock-video 的 components.py 同一写法，
facts.json 格式完全一样——同一期可以先出报告、再出视频，facts.py 共用。
（不直接 import components：它会带起整个视频引擎 motion.py。）

找 stock-video 的顺序：环境变量 STOCK_VIDEO_SKILL → 本目录的上一级（仓库里 stock-report/ 放在 stock-video 根目录下）
→ 同级的 stock-video/（两个 skill 并排装）→ 用户目录下的 .claude/skills、.config/opencode/skill(s)。
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # stock-report/scripts
REPORT_SKILL = HERE.parent                       # stock-report/


def _is_video(p):
    return p and (Path(p) / 'scripts' / 'fetch_data.py').exists() and (Path(p) / '方法与口径.md').exists()


def video_skill():
    """stock-video 的目录；找不到就报错并说怎么办"""
    home = Path.home()
    cands = [os.environ.get('STOCK_VIDEO_SKILL'), REPORT_SKILL.parent, REPORT_SKILL.parent / 'stock-video',
             home / '.claude/skills/stock-video', home / '.config/opencode/skills/stock-video',
             home / '.config/opencode/skill/stock-video']
    for c in cands:
        if _is_video(c): return Path(c).resolve()
    sys.exit('找不到 stock-video（stock-report 用它的抓数脚本和 方法与口径.md）：\n'
             '  把 stock-video 装在 stock-report 旁边，或设环境变量 STOCK_VIDEO_SKILL=<stock-video 目录>')


def video_scripts():
    """把 stock-video/scripts 加进 sys.path（review_pack 的数字对账、sysenv 的字体），返回目录"""
    p = video_skill() / 'scripts'
    if str(p) not in sys.path: sys.path.insert(0, str(p))
    return p


# ---------- facts.py 用：和 stock-video components.py 同一写法 ----------
def put(fx, key, value, label, quote=None):
    """把一个数和它的说法一起冻结。key 可带点号写进嵌套字典（'val.pb.cur'）；
    说法存进 fx['labels'][key]，公告原文摘录存进 fx['quotes'][key]。返回 value，方便接着算。"""
    d = fx; ks = key.split('.')
    for k in ks[:-1]: d = d.setdefault(k, {})
    d[ks[-1]] = value
    fx.setdefault('labels', {})[key] = label
    if quote: fx.setdefault('quotes', {})[key] = quote
    return value


def window_1y(df, date_col, cutoff=None):
    """"近一年" = 截止日往回 365 天"""
    import pandas as pd
    d = pd.to_datetime(df[date_col]); end = pd.to_datetime(cutoff) if cutoff else d.iloc[-1]
    return df[(d > end - pd.Timedelta(days=365)) & (d <= end)]


def pct_stats(values, cur=None):
    """估值分位：p20 / p50 / p80 和现值分位 pct（现值以下的时间占比，%）"""
    import numpy as np
    v = np.asarray([x for x in values if x == x], float); cur = v[-1] if cur is None else cur
    return dict(p20=float(np.percentile(v, 20)), p50=float(np.percentile(v, 50)), p80=float(np.percentile(v, 80)),
                pct=float((v < cur).mean() * 100), cur=float(cur))


# ---------- 读 facts ----------
def load_facts(proj):
    p = Path(proj) / 'facts.json'
    if not p.exists(): sys.exit(f'没有 {p}：先写 facts.py 并运行')
    return json.loads(p.read_text(encoding='utf-8-sig'))


def get(fx, key):
    """'a.b.0.c' → 值；找不到抛 KeyError（报告稿里 {{键}} 写错要立刻发现）"""
    d = fx
    for k in key.split('.'):
        if isinstance(d, list): d = d[int(k)]
        elif isinstance(d, dict) and k in d: d = d[k]
        else: raise KeyError(key)
    return d


def label(fx, key):
    return fx.get('labels', {}).get(key, '')


def fmt(v, spec=''):
    """{{键|规格}} 的格式化。规格：空 = 原样（浮点保留两位）；'.1f' 之类 = Python 格式；
    '亿' = 元→亿元两位；'亿1' = 一位；'%' = 比例×100 一位加 %；'%0' = 不带小数；'倍' = 两位加"倍" """
    if isinstance(v, str): return v
    if spec in ('', None): return f'{v:.2f}' if isinstance(v, float) else str(v)
    if spec.startswith('亿'):
        d = int(spec[1:] or 2); return f'{v / 1e8:.{d}f}'
    if spec.startswith('%'):
        d = int(spec[1:] or 1); return f'{v * 100:.{d}f}%'
    if spec == '倍': return f'{v:.2f}倍'
    return format(v, spec)
