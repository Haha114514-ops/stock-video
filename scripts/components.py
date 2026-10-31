# -*- coding: utf-8 -*-
"""components.py —— 分镜常用组件（从爱美客 / 高鑫 / 晨光三期里各自重写过的部件抽出来）

    from components import *

这里只放"每期都要画、画法差不多"的部件：数字卡、柱图、折线、水平参考线、估值分位面板、金句卡、交叉淡入；
以及 facts.py 用的 put（数和说法一起冻结）、window_1y（近一年 = 截止日往回 365 天）、pct_stats。
构图、章节顺序、每章讲什么，不在这里——那是每期从自己的主线推出来的。
不提供"先画空卡片框占位"的部件：讲到什么才出现什么，没讲到的位置就空着（或者构图里不留那个位置）。
"""
import numpy as np
from motion import *


def xfade(t, t0, d=0.5):
    """同一位置换内容：t0 前旧的淡出、t0 后新的淡入；返回 (旧透明度, 新透明度)"""
    return out(t, t0 - d, d), pg(t, t0, d)


def legend(f, xy, items, a=1.0, size=20, gap=28):
    """小图例：items = [(颜色, 说明), ...]，横排，xy 是左端、垂直居中。
    红绿表示"对利润好 / 坏"等涨跌以外的意思时必须加（A 股观众默认红涨绿跌）。返回总宽度"""
    if a <= 0.01: return 0
    x, y = xy; x0 = x
    for col, lab in items:
        f.rect((x, y - 8, x + 22, y + 8), col, a, r=3)
        f.text((x + 30, y), lab, size, SUB, a, 'r', 'lm')
        x += 30 + f.tw(lab, size) + gap
    f.legend = True
    return x - gap - x0


def tile(f, box, label, val, sub=None, col=GOLD, a=1.0, vsize=72, edge=None):
    """数字卡：小标题 + 大数字 + 一行注脚（口径、对比）"""
    if a <= 0.01: return
    f.card(box, a, edge=edge or EDGE)
    x0, y0, x1, y1 = box
    f.text((x0 + 30, y0 + 44), label, 26, SUB, a, 'b', 'lm')
    f.text((x0 + 26, (y0 + y1) / 2 + (6 if sub else 14)), val, vsize, col, a, 'n', 'lm')
    if sub: f.text((x0 + 30, y1 - 34), sub, 22, DIM, a, 'r', 'lm')


def vbars(f, t, box, labels, vals, t0, vmax=None, cols=GOLD, fmt='{:.1f}', stagger=0.25, a=1.0, lsize=22, vsize=26):
    """竖柱图（坐标从 0 起）：第 i 根在 t0 + i*stagger 开始长高，数值随柱子淡入。cols 可以是一个颜色或每根一个"""
    if a <= 0.01: return
    x0, y0, x1, y1 = box; n = len(vals); vmax = vmax or max(vals) * 1.15
    slot = (x1 - x0) / n; bw = slot * 0.58
    for i, (lab, v) in enumerate(zip(labels, vals)):
        p = eio(pg(t, t0 + i * stagger, 0.9)); c = cols[i] if isinstance(cols, (list, tuple)) and not isinstance(cols[0], int) else cols
        cx = x0 + slot * (i + 0.5); h = (y1 - y0) * max(v, 0) / vmax * p
        f.rect((cx - bw / 2, y1 - h, cx + bw / 2, y1), c, a, r=6)
        f.text((cx, y1 - h - 22), fmt.format(v), vsize, TXT, a * clamp(p * 2 - 1), 'n', 'mm')
        f.text((cx, y1 + 24), str(lab), lsize, DIM, a, 'n', 'mm')


def line_chart(f, t, box, vals, lo, hi, t0, col=GOLD, dur=2.0, ticks=None, fmt='{:g}', xlabels=None, fill=0.10,
               a=1.0, log=False, w=3, dot=True):
    """折线：t0 起 dur 秒描出来。xlabels=[(位置0~1, 文字)]；log=True 用对数纵轴（刻度仍写普通数字）。返回各点坐标"""
    if a <= 0.01: return []
    T = (lambda v: np.log(max(v, lo))) if log else (lambda v: v)
    if ticks:
        for tk in ticks:
            y = ymap(box, T(tk), T(lo), T(hi)); f.line([(box[0], y), (box[2], y)], GRID, 1, 0.5 * a)
            f.text((box[0] - 10, y), fmt.format(tk), 18, DIM, a, 'n', 'rm')
    for x, s in (xlabels or []):
        f.text((box[0] + (box[2] - box[0]) * x, box[3] + 22), s, 18, DIM, a, 'n', 'mm')
    pts = to_xy(box, [T(v) for v in vals], T(lo), T(hi))
    draw_line(f, box, partial(pts, eio(pg(t, t0, dur))), col, w, fill, box[3], a, dot=dot)
    return pts


def year_labels(dates, years):
    """给 line_chart 的 xlabels：dates 是按时间排好的日期序列（pandas 或字符串），years 是要标的年份"""
    ds = [str(d)[:10] for d in dates]; n = len(ds); o = []
    for y in years:
        i = sum(d < f'{y}-01-01' for d in ds)
        if 0 < i < n: o.append((i / (n - 1), str(y)))
    return o


def hline(f, box, v, lo, hi, p, col=GOLD, label=None, a=1.0, log=False, size=20):
    """水平参考线（只算利润的参考价、中位数）：p 控制从左往右画出的进度。
    参考价的 label 写"只算利润的参考价 X（非目标价）"（56号，方法与口径 §2）"""
    if a <= 0.01 or p <= 0: return
    T = (lambda x: np.log(max(x, lo))) if log else (lambda x: x)
    y = ymap(box, T(v), T(lo), T(hi))
    f.dash(box[0], y, box[0] + (box[2] - box[0]) * p, y, col, 3, a, 12, 8)
    if label: f.text((box[2] + 12, y), label, size, col, a * clamp(p * 2 - 1), 'b', 'lm')   # 放在图框右侧，不压线；构图时右边留 ~120px


def put(fx, key, value, label, quote=None):
    """facts.py 用（56号）：把一个数和它的说法一起冻结。
    key 可以带点号写到嵌套字典里（'val.hi1'）；说法存进 fx['labels'][key]，公告原文摘录存进 fx['quotes'][key]。
    说法写清对象 / 时间 / 口径 / 前提，例如 put(FX, 'val.hi1', 6.71, '2025-09-16 收盘，区间最高，距截止日 13 个月')。
    review_pack.py 会把旁白里的每个数和这里的说法并排列出来。返回 value，方便接着算。"""
    d = fx; ks = key.split('.')
    for k in ks[:-1]: d = d.setdefault(k, {})
    d[ks[-1]] = value
    fx.setdefault('labels', {})[key] = label
    if quote: fx.setdefault('quotes', {})[key] = quote
    return value


def window_1y(df, date_col, cutoff=None):
    """"近一年" = 截止日往回 365 天（56号统一口径）。df 按日期排好；cutoff 默认取最后一天。返回窗口内的行"""
    import pandas as pd
    d = pd.to_datetime(df[date_col]); end = pd.to_datetime(cutoff) if cutoff else d.iloc[-1]
    return df[(d > end - pd.Timedelta(days=365)) & (d <= end)]


def pct_stats(values, cur=None):
    """估值分位：返回 p20/p50/p80 和现值分位 pct（现值以下的时间占比，%）。给 facts.py 用，结果冻结进 facts.json"""
    v = np.asarray([x for x in values if x == x], float); cur = v[-1] if cur is None else cur
    return dict(p20=float(np.percentile(v, 20)), p50=float(np.percentile(v, 50)), p80=float(np.percentile(v, 80)),
                pct=float((v < cur).mean() * 100), cur=float(cur))


def val_panel(f, t, box, title, vals, st, lo, hi, ticks, t0, xlabels=None, log=True, dim=0.0, hl=0.0, unit='倍'):
    """估值四宫格的一格：低 / 中 / 高三档分位带 + 序列描线 + 现值点 + 现值分位（st 来自 pct_stats，冻结在 facts.json）"""
    a = pg(t, t0, 0.6) * (1 - 0.55 * dim)
    if a <= 0.01: return
    f.card(box, a)
    if hl > 0: f.rect(box, None, 0, r=18, outline=GOLD, ow=3, oa=hl)
    x0, y0, x1, y1 = box
    f.text((x0 + 28, y0 + 34), title, 26, TXT, a, 'b', 'lm')
    cb = (x0 + 76, y0 + 72, x1 - 270, y1 - 40)
    T = (lambda v: np.log(max(v, lo))) if log else (lambda v: v)
    ly = lambda v: ymap(cb, T(v), T(lo), T(hi))
    bp = pg(t, t0 + 0.2, 0.6)
    y20, y50, y80 = ly(st['p20']), ly(st['p50']), ly(st['p80'])
    f.rect((cb[0], cb[1], cb[2], y80), RED, 0.10 * a * bp)
    f.rect((cb[0], y80, cb[2], y20), SUB, 0.05 * a * bp)
    f.rect((cb[0], y20, cb[2], cb[3]), GREEN, 0.15 * a * bp)
    f.dash(cb[0], y50, cb[2], y50, SUB, 2, 0.7 * a * bp)
    labs, yy = [(y20, f'低 {st["p20"]:.1f}', GREEN), (y50, f'中 {st["p50"]:.1f}', SUB), (y80, f'高 {st["p80"]:.1f}', RED)], []
    for y_, _, _ in labs: yy.append(min(y_, yy[-1] - 22) if yy else y_)
    for (_, lab, c), y_ in zip(labs, yy): f.text((cb[2] + 10, y_), lab, 18, c, a * bp, 'n', 'lm')
    pts = line_chart(f, t, cb, list(vals) + [st['cur']], lo, hi, t0 + 0.2, (170, 186, 220), 1.8, ticks, '{:g}', xlabels, 0, a, log, 2, False)
    ca = pg(t, t0 + 1.9, 0.5)
    if pts: marker(f, *pts[-1], GOLD, ca * a, 8)
    ix = x1 - 160
    f.text((ix, y0 + 96), '现值分位', 22, SUB, ca * a, 'b', 'lm')
    f.text((ix - 2, y0 + 152), f'{st["pct"] * pg(t, t0 + 1.9, 1.0):.1f}%', 52, GOLD, ca * a, 'n', 'lm')
    f.text((ix, y0 + 212), f'现值 {st["cur"]:.2f} {unit}' if st['cur'] < 10 else f'现值 {st["cur"]:.1f} {unit}', 22, TXT, ca * a, 'r', 'lm')


def quote(f, t, t0, lines, cols=None, alpha=0.9):
    """金句卡：压暗全幅 + 两三行大字。全片两三次，留给高潮；压暗要够，别让底下的字透出来。返回进度 q（0 时不画）"""
    q = pg(t, t0, 0.6)
    overlay(f, q, alpha)
    if q <= 0: return 0
    sizes = [46, 84, 40]; cols = cols or [SUB, GOLD, TXT]; y = 440 + 30 * (1 - q)
    for i, s in enumerate(lines[:3]):
        f.text((W / 2, y + [0, 100, 196][i]), s, sizes[i], cols[i], pg(t, t0 + 0.6 * i, 0.6), 'b', 'mm')
    return q
