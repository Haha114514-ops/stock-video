# -*- coding: utf-8 -*-
"""components.py —— 分镜常用组件（从爱美客 / 高鑫 / 晨光三期里各自重写过的部件抽出来）

    from components import *

这里只放"每期都要画、画法差不多"的部件：数字卡、柱图（可带负值 / 分组）、资产负债表两根堆叠柱 bs_bars、折线、水平参考线、估值分位面板、金句卡、交叉淡入；
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


def vbars(f, t, box, labels, vals, t0, vmax=None, cols=None, fmt='{:.1f}', stagger=0.25, a=1.0, lsize=22, vsize=26,
          vmin=None, names=None, group_gap=0.12):
    """竖柱图：第 i 根（组）在 t0 + i*stagger 开始长；t0 也可以是列表（每根 / 每组一个开始时刻，挂到 B.at 上）。
    - 全是正数：坐标从 0 起，和以前一样（cols 默认 GOLD，可以是一个颜色或每根一个）。
    - 有负数（亏损年份、负现金流、单季利润为负）：零轴按数据放在中间，纵轴范围跟数据走（vmin / vmax 可手给）；
      cols 不给时正值红、负值绿（A 股配色，柱子在零轴上下已经说明正负，不另加图例）；负值的数字写在柱底下面。
    - 分组：vals 每项是一组数（[[利润, 经营现金流], …]），cols 是每个系列一个颜色（默认 GOLD / TEAL），
      names = ['归母净利润', '经营现金流'] 时在图框左上角画图例。
    返回 [(柱中心 x, 柱顶 y, 柱底 y), ...]（分组时按 组 × 系列 展开）"""
    if a <= 0.01: return []
    x0, y0, x1, y1 = box; n = len(vals)
    grouped = n > 0 and isinstance(vals[0], (list, tuple))
    flat = [v for g in vals for v in g] if grouped else list(vals)
    neg = any(v < 0 for v in flat)
    hi = max(max(flat), 0.0); lo = min(min(flat), 0.0)
    if vmax is None: vmax = hi * 1.15 if hi > 0 else (hi - lo) * 0.08
    if vmin is None: vmin = lo * 1.15 if lo < 0 else 0.0
    if vmax <= vmin: vmax = vmin + 1
    Y = lambda v: ymap(box, v, vmin, vmax); yz = Y(0)
    sign = cols is None and neg and not grouped
    if grouped:
        k = len(vals[0]); scol = cols if isinstance(cols, (list, tuple)) and cols and not isinstance(cols[0], int) else [GOLD, TEAL, PURPLE, ORANGE][:k]
    else:
        scol = cols if cols is not None else GOLD
    slot = (x1 - x0) / n
    t_at = (lambda i: t0[min(i, len(t0) - 1)]) if isinstance(t0, (list, tuple)) else (lambda i: t0 + i * stagger)
    if neg: f.line([(x0, yz), (x1, yz)], GRID, 2, 0.8 * a * clamp(pg(t, t_at(0), 0.4)))
    if grouped and names: legend(f, (x0 + 10, y0 - 30), list(zip(scol, names)), a * clamp(pg(t, t_at(0), 0.4)))   # 图框上方，不压柱顶数字
    if sign: f.legend = True                  # 零轴上下的红 / 绿就是正 / 负，不再要求图例
    out_ = []
    for i, lab in enumerate(labels):
        g = vals[i] if grouped else [vals[i]]; p = eio(pg(t, t_at(i), 0.9)) if t >= t_at(i) else 0.0
        cx = x0 + slot * (i + 0.5); gw = slot * (0.78 if grouped else 0.58); bw = gw / len(g) * (1 - group_gap if grouped else 1)
        for j, v in enumerate(g):
            bx = cx - gw / 2 + gw / len(g) * (j + 0.5)
            if grouped: c = scol[j % len(scol)]
            elif sign: c = RED if v >= 0 else GREEN
            else: c = scol[i] if isinstance(scol, (list, tuple)) and not isinstance(scol[0], int) else scol
            ye = lerp(yz, Y(v), p); top, bot = min(yz, ye), max(yz, ye)
            out_.append((bx, min(yz, Y(v)), max(yz, Y(v))))
            if p <= 0: continue
            f.rect((bx - bw / 2, top, bx + bw / 2, bot), c, a, r=6 if bot - top > 12 else 2)
            vs = vsize if not grouped else max(18, int(vsize * 0.8))
            ty = (top - vs * 0.85) if v >= 0 else (bot + vs * 0.85)
            f.text((bx, ty), fmt.format(v), vs, TXT, a * clamp(p * 2 - 1), 'n', 'mm')
        f.text((cx, y1 + 24), str(lab), lsize, DIM, a, 'n', 'mm')
    return out_


def bs_bars(f, t, box, left, right, t0, heads=('有什么', '钱是谁的'), stagger=0.35, d=0.6, fmt='{:.0f}', unit='',
            a=1.0, hl=None, hla=0.6, lsize=22, vsize=24, bar=0.26, min_in=None, totals=True):
    """资产负债表两根等高堆叠柱（方法与口径 §0：每期总览必画）。
    left = 资产分段 [(标签, 值, 颜色), …]，right = 负债和权益分段 [(标签, 值, 颜色), …]，都是自下而上。
    两根柱各按自己的合计画满同一高度（资产 = 负债 + 权益；差一点是四舍五入）。
    t0：一个数 → 左柱各段、右柱各段依次每 stagger 秒点亮一段；列表 → 每段一个时刻（先左后右，长度 = 段数），
    挂到 B.at(句, '现金') 上就是"念到哪段亮哪段"。没点亮的段不画，不先画空框。
    分段高度小于 min_in（默认 2 行字高）时，标签和数值放到柱外（左柱放左边、右柱放右边），引线连回分段，上下自动错开不叠字；
    柱外标签画在 box 以内，box 左右各留 ~160px（放不下先缩到 20 号字）。
    hl = ('L', 序号) / ('R', 序号) 或它们的列表：突出这几段，其余按 hla 压暗（hla=0 不压）。
    返回 {('L'|'R', 序号): 分段框}"""
    if a <= 0.01: return {}
    x0, y0, x1, y1 = box; W_ = x1 - x0
    top = y0 + (44 if heads else 0); H_ = y1 - top
    bw = W_ * bar; cxs = (x0 + W_ * 0.30, x0 + W_ * 0.70)
    min_in = min_in or (lsize + vsize + 14)
    segs = [('L', i, s) for i, s in enumerate(left)] + [('R', i, s) for i, s in enumerate(right)]
    t_at = (lambda k: t0[min(k, len(t0) - 1)]) if isinstance(t0, (list, tuple)) else (lambda k: t0 + k * stagger)
    hls = set([hl] if isinstance(hl, tuple) and hl and isinstance(hl[0], str) else (hl or []))
    out_ = {}; outside = {'L': [], 'R': []}
    for side, cx, items, k0 in (('L', cxs[0], left, 0), ('R', cxs[1], right, len(left))):
        tot = sum(abs(s[1]) for s in items) or 1; yb = y1
        ha = pg(t, t_at(k0), 0.5)
        if heads and ha > 0:
            h_ = heads[0] if side == 'L' else heads[1]
            if totals: h_ += f'  {fmt.format(sum(s[1] for s in items))}{unit}'
            f.text((cx, y0 + 18), h_, 26, TXT, a * ha, 'b', 'mm')
        for i, s in enumerate(items):
            lab, v, col = s[0], s[1], (s[2] if len(s) > 2 else GOLD)
            h = H_ * abs(v) / tot; box_ = (cx - bw / 2, yb - h, cx + bw / 2, yb); yb -= h
            out_[(side, i)] = box_
            p = pg(t, t_at(k0 + i), d)
            if p <= 0: continue
            dim = (1 - hla) if hls and (side, i) not in hls else 1.0
            aa = a * p * dim
            f.rect((box_[0], box_[1] + 1, box_[2], box_[3] - 1), col, aa, r=4)
            val = fmt.format(v) + unit
            if h >= min_in:
                f.text((cx, (box_[1] + box_[3]) / 2 - vsize * 0.55), lab, lsize, TXT, aa, 'b', 'mm')
                f.text((cx, (box_[1] + box_[3]) / 2 + lsize * 0.6), val, vsize, TXT, aa, 'n', 'mm')
            elif h >= lsize + 6 and f.tw(f'{lab} {val}', lsize) < bw - 16:
                f.text((cx, (box_[1] + box_[3]) / 2), f'{lab} {val}', lsize, TXT, aa, 'b', 'mm')
            else:
                outside[side].append(((box_[1] + box_[3]) / 2, f'{lab} {val}', aa, box_))
    gap = lsize + 8
    for side, lst in outside.items():                 # 柱外标签：按高度排好，上下至少隔一行，再整体挪回图框里
        lst.sort(key=lambda x: x[0]); ys = []
        for yc, *_ in lst: ys.append(max(yc, ys[-1] + gap) if ys else yc)
        over = (ys[-1] - (y1 - lsize / 2)) if ys else 0
        if over > 0: ys = [y - over for y in ys]
        under = (top + lsize / 2) - ys[0] if ys else 0       # 往上也别顶出柱顶、压到柱头标题
        if under > 0: ys = [y + under for y in ys]
        for (yc, s, aa, b), y in zip(lst, ys):
            ex = b[0] - 8 if side == 'L' else b[2] + 8; tx = ex - 28 if side == 'L' else ex + 28
            room = (tx - x0) if side == 'L' else (x1 - tx); sz = lsize
            while sz > 20 and f.tw(s, sz) > room: sz -= 1      # 放不下先缩字（最小 20 号），再放不下就贴图框边
            if side == 'L':
                tx = max(tx, x0 + f.tw(s, sz))
                f.line([(b[0], yc), (ex, yc), (tx + 6, y)], SUB, 1, aa * 0.8); f.text((tx, y), s, sz, SUB, aa, 'r', 'rm')
            else:
                tx = min(tx, x1 - f.tw(s, sz))
                f.line([(b[2], yc), (ex, yc), (tx - 6, y)], SUB, 1, aa * 0.8); f.text((tx, y), s, sz, SUB, aa, 'r', 'lm')
    return out_


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


def val_panel(f, t, box, title, vals, st, lo, hi, ticks, t0, xlabels=None, log=True, dim=0.0, hl=0.0, unit='倍',
              mode='pct', ref=None, ref_label=None, cur_delay=0.0, fade=None):
    """估值四宫格的一格：低 / 中 / 高三档分位带 + 序列描线 + 现值点 + 右侧大数字（st 来自 pct_stats，冻结在 facts.json）。
    mode='pct'：右侧写"现值分位 X%"（默认，和以前一样）；
    mode='vs'：右侧写"比现在高 X%"——ref 是要比的那个值（例如中位数 st['p50']、同行倍数），
      X = ref / 现值 − 1；ref_label 换掉小标题（默认"中位数比现在"）；低于现值时自动写"低"。
    cur_delay：右侧大数字晚于面板几秒出现（默认 0 = 和面板一起出，不再固定等 1.9 秒）。
    fade=(开始秒, 时长)：面板整体淡出（换场时用）。"""
    a = pg(t, t0, 0.6) * (1 - 0.55 * dim)
    if fade: a *= out(t, fade[0], fade[1] if len(fade) > 1 else 0.5)
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
    tc = t0 + cur_delay; ca = pg(t, tc, 0.5)
    if pts: marker(f, *pts[-1], GOLD, ca * a, 8)
    ix = x1 - 160
    if mode == 'vs':
        r = (ref if ref is not None else st['p50']) / st['cur'] - 1
        f.text((ix, y0 + 96), ref_label or ('中位数比现在' + ('高' if r >= 0 else '低')), 22, SUB, ca * a, 'b', 'lm')
        f.text((ix - 2, y0 + 152), f'{abs(r) * 100 * pg(t, tc, 1.0):.0f}%', 52, GOLD, ca * a, 'n', 'lm')
    else:
        f.text((ix, y0 + 96), '现值分位', 22, SUB, ca * a, 'b', 'lm')
        f.text((ix - 2, y0 + 152), f'{st["pct"] * pg(t, tc, 1.0):.1f}%', 52, GOLD, ca * a, 'n', 'lm')
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
