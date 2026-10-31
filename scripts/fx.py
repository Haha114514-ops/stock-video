# -*- coding: utf-8 -*-
"""fx.py —— 有含义的动效（56号补丁起）。from fx import *

motion.py 原有的动效几乎都是"在原地出现"（淡入、柱子长高、描线）。这里补的是"动作本身就在讲话"的几种：
每个动效对应一种财务上的意思，用到时旁白正好在说这件事；不做与内容无关的装饰（粒子、转场特效）。

    count   数字变成另一个数       "市盈率从 4.1 倍变成 7.9 倍"
    fly     一个数从图上飞进算式   "拿这个数来算"
    equation 算式一项一项拼出来    推算过程看得见：4.16 − 0.92 = 3.25，÷ 2.71 ≈ 1.2 年
    split   一根条拆成几段 / 掉出去 "拆开看"、"这部分已经不在了"（已付股息）
    drain   一笔钱按年被花掉       "现金能撑几年"
    zoom    把画面一小块放大出来   "看这一段"（一天跌 13.8% 那一天）
    strike  划掉                   "这件事不成立了"（17.6 亿认购终止）

全部是纯函数：在分镜里传 t 和开始时刻 t0，不改 motion.py，旧工程不受影响。
"""
import math
from PIL import Image
from motion import *


def _bump(p):
    """到位时轻轻一顿：0→1 过程中末段放大一点再回落，用来表示「落定」"""
    return math.sin(math.pi * clamp((p - 0.7) / 0.3)) if p < 1 else 0.0


def count(f, t, t0, xy, v0, v1, fmt='{:.1f}', size=64, c0=GOLD, c1=GOLD, d=1.2, a=1.0, anchor='mm', ghost=True):
    """数字从 v0 滚到 v1，颜色从 c0 渐到 c1；ghost=True 时滚动开始后，旧值缩小移到左边、带一个箭头，
    表示"原来是这个数"（xy 是新值的中心，anchor 只支持 'mm'）。t < t0 时显示 v0。返回进度 p。"""
    if a <= 0.01: return 0.0
    p = eio(pg(t, t0, d)) if t >= t0 else 0.0
    v = lerp(v0, v1, p); s = size * (1 + 0.10 * _bump(p))
    if ghost and p > 0:
        g = min(1.0, p * 2); gs = int(size * 0.45); half = f.tw(fmt.format(v1), size, 'n') / 2
        gx = xy[0] - half - 40 - 30 * g
        f.text((gx, xy[1]), '→', int(gs * 0.9), SUB, a * 0.7 * g, 'r', 'rm')
        f.text((gx - gs * 1.1, xy[1]), fmt.format(v0), gs, SUB, a * 0.7 * g, 'n', 'rm')
    f.text(xy, fmt.format(v), int(s), lerpc(c0, c1, p), a, 'n', anchor)
    return p


def fly(f, t, t0, src, dst, s, size0=40, size1=40, col=GOLD, d=0.9, arc=60, a=1.0, trail=True):
    """文字 s 从 src 飞到 dst（略带弧线），字号 size0→size1；t < t0 时停在 src。
    用来把图上的某个数"拿到"算式里——观众看得见这个数是从哪来的。返回进度 p（落定后为 1）。"""
    if a <= 0.01: return 0.0
    p = eio(pg(t, t0, d)) if t >= t0 else 0.0
    def at(q):
        return (lerp(src[0], dst[0], q), lerp(src[1], dst[1], q) - arc * math.sin(math.pi * q))
    if trail and 0 < p < 1:
        for k, back in enumerate((0.18, 0.12, 0.06)):
            q = max(0.0, p - back); x, y = at(q)
            f.text((x, y), s, int(lerp(size0, size1, q)), col, a * (0.12 + 0.06 * k), 'n', 'mm')
    x, y = at(p)
    f.text((x, y), s, int(lerp(size0, size1, p) * (1 + 0.08 * _bump(p))), col, a, 'n', 'mm')
    return p


def equation(f, t, xy, items, size=44, gap=18, a=1.0, d=0.45, anchor='l'):
    """算式一项一项拼出来：items = [(文字, 出现时刻, 颜色), ...]，运算符也作为一项。
    位置一开始就按全部项排好（不会因为后来的项而挪动），每项从下方 30px 滑上来。
    文字可以是函数 p→str（例如结果项边出现边滚数）；颜色为 None 的项只占位置不画（留给 fly 飞进来的数）。
    返回最后一项的进度。"""
    if a <= 0.01: return 0.0
    txt = [s(1.0) if callable(s) else s for s, _, _ in items]
    ws = [f.tw(s, size, 'n') for s in txt]; tot = sum(ws) + gap * (len(ws) - 1)
    x = xy[0] - (tot / 2 if anchor == 'm' else tot if anchor == 'r' else 0); p = 0.0
    for (s, t0, col), w in zip(items, ws):
        p = pg(t, t0, d)
        if p > 0 and col is not None:
            ss = s(eio(pg(t, t0, 0.9))) if callable(s) else s
            f.text((x, xy[1] + 30 * (1 - p)), ss, size, col, a * p, 'n', 'lm')
        x += w + gap
    return p


def split(f, t, t0, box, parts, d=1.0, gap=16, a=1.0, drop=(), t_drop=None, label_size=22, val_fmt='{:.2f}'):
    """一根整条拆成几段：parts = [(值, 颜色, 标签), ...]。t0 前是一整根灰条（总数），
    t0 起各段上色、彼此拉开 gap；drop 里的段在 t_drop 时往下掉出去、变暗——"这部分已经不在了"。
    返回 (各段中心 x 列表, 拆分进度)。"""
    if a <= 0.01: return [], 0.0
    x0, y0, x1, y1 = box; tot = sum(v for v, _, _ in parts)
    p = eio(pg(t, t0, d)) if t >= t0 else 0.0
    pd = eio(pg(t, t_drop, 0.8)) if (t_drop is not None and t >= t_drop) else 0.0
    usable = (x1 - x0) - gap * (len(parts) - 1) * p
    x = x0; cs = []
    for i, (v, col, lab) in enumerate(parts):
        w = usable * v / tot; dy = 0; aa = a
        if i in drop: dy = 90 * pd; aa = a * (1 - 0.6 * pd)
        c = lerpc(GREY, col, p)
        f.rect((x, y0 + dy, x + w, y1 + dy), c, aa, r=6)
        if w > 50: f.text((x + w / 2, (y0 + y1) / 2 + dy), val_fmt.format(v), int(min(32, (y1 - y0) * 0.5)), TXT, aa * p, 'n', 'mm')
        if lab: f.text((x + w / 2, y1 + 24 + dy), lab, label_size, col, aa * p, 'b', 'mm')
        cs.append(x + w / 2); x += w + gap * p
    return cs, p


def drain(f, t, t0, box, total, per_year, d=3.0, a=1.0, unit='亿', col=GOLD, end_col=RED, years_max=None):
    """一笔钱按年被花掉：条从 total 缩到 0，下方时间轴上的指针走到"花完"那一年。
    per_year = 每年净流出。d = 动画时长（秒）。返回 (花完要几年, 进度)。"""
    if a <= 0.01: return 0.0, 0.0
    x0, y0, x1, y1 = box; yrs = total / per_year
    ymax = years_max or max(1, math.ceil(yrs + 0.2))
    p = eio(pg(t, t0, d)) if t >= t0 else 0.0
    cur = yrs * p; rem = max(0.0, total - per_year * cur)
    bh = (y1 - y0) * 0.45
    f.rect((x0, y0, x1, y0 + bh), (36, 50, 82), 0.8 * a, r=8)
    f.rect((x0, y0, x0 + (x1 - x0) * rem / total, y0 + bh), lerpc(col, end_col, p), a, r=8)
    f.text((x0 + (x1 - x0) * rem / total + 14 if rem > 0 else x0 + 14, y0 + bh / 2), f'剩 {rem:.2f}{unit}', 30, TXT, a, 'n', 'lm')
    ty = y1 - 18
    f.line([(x0, ty), (x1, ty)], GRID, 2, a)
    for k in range(ymax + 1):
        xx = x0 + (x1 - x0) * k / ymax
        f.line([(xx, ty - 8), (xx, ty + 8)], GRID, 2, a); f.text((xx, ty + 26), f'{k} 年', 20, DIM, a, 'n', 'mm')
    xp = x0 + (x1 - x0) * cur / ymax
    marker(f, xp, ty, lerpc(col, end_col, p), a * (1 if p > 0 else 0.4), 8)
    if p >= 1:
        q = pg(t, t0 + d, 0.5)
        f.text((xp, ty - 40), f'≈ {yrs:.1f} 年花完', 34, end_col, a * q, 'n', 'mm')
    return yrs, p


def zoom(f, t, t0, src, dst, d=0.8, a=1.0, edge=GOLD, label=None, t_out=None):
    """把画面上 src 这一小块"拎出来"放大到 dst：从原位置长大飞过去，两角连线指回原处。
    必须在分镜函数最后调用（它取的是已经画好的像素）。t_out 起收回。"""
    if a <= 0.01 or t < t0: return 0.0
    p = eio(pg(t, t0, d)) * (out(t, t_out, 0.5) if t_out is not None else 1)
    if p <= 0.01: return 0.0
    patch = f.im.crop(tuple(int(v) for v in src))
    box = [lerp(s, e, p) for s, e in zip(src, dst)]
    w, h = int(box[2] - box[0]), int(box[3] - box[1])
    if w < 4 or h < 4: return p
    im = patch.resize((w, h), Image.LANCZOS)
    f.rect(src, None, 0, outline=edge, ow=2, oa=a * p)
    for (sx, sy), (dx, dy) in (((src[0], src[1]), (box[0], box[1])), ((src[2], src[3]), (box[2], box[3]))):
        f.line([(sx, sy), (dx, dy)], edge, 1, a * 0.6 * p)
    mask = Image.new('L', (w, h), int(255 * a * clamp(p * 1.4)))
    f.im.paste(im, (int(box[0]), int(box[1])), mask)
    f.rect(box, None, 0, r=6, outline=edge, ow=3, oa=a * p)
    if label: f.text((box[0], box[1] - 18), label, 24, edge, a * p, 'b', 'ls')
    return p


def strike(f, t, t0, x0, y, x1, col=RED, w=5, d=0.5, a=1.0):
    """从左往右划掉一行：协议终止、假设不成立。返回进度。"""
    p = eo(pg(t, t0, d)) if t >= t0 else 0.0
    if p > 0: f.line([(x0, y), (lerp(x0, x1, p), y)], col, w, a)
    return p
