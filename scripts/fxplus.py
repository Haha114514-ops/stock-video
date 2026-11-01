# -*- coding: utf-8 -*-
"""fxplus.py —— 第二组动效工具（57号补丁十六）。from fxplus import *

和 fx.py 一样是纯函数（传 t 和开始时刻 t0，返回进度），不改 motion.py 的默认行为。
这里只提供工具，不规定用法：用不用、用在哪、怎么组合、参数怎么调，由分镜按这一期的内容自己决定；
觉得不合适可以只借一部分，或者照着写自己的效果。

    镜头   camera / cam_keys        推近、平移、拉远（作用在已画好的内容区像素上）
    对比   versus                   两个数并排长出来 / 从两边对撞，差额弹出
    时间轴 timeline                 轴从左扫过去，事件逐个落点
    强调   ring / arrow / highlight / underline   手绘感的圈、箭头、荧光笔、下划线
    图表   waterfall / sankey       瀑布图（一级一级加减）、桑基图（钱从哪来到哪去，可多列）
    转场   transition               同一块画面从状态 A 换到 B：fade / wipe / slide / flip / iris / blinds
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from motion import *

CONTENT = (0, 120, W, 920)     # 内容区：片头条以下、字幕以上


def _bump(p):
    return math.sin(math.pi * clamp((p - 0.7) / 0.3)) if p < 1 else 0.0


def _delta(im, base):
    """画上去的内容 = 画完的像素 − 底图（int16，可正可负）：移动 / 缩放内容时背景不跟着动"""
    return np.asarray(im, np.int16) - np.asarray(base, np.int16)


def _add(out, d, ox=0, oy=0):
    """把内容层 d 平移 (ox, oy) 叠到 out 上（超出部分裁掉）"""
    h, w = out.shape[:2]; dh, dw = d.shape[:2]
    xa, ya = max(0, ox), max(0, oy); xb, yb = min(w, ox + dw), min(h, oy + dh)
    if xb > xa and yb > ya: out[ya:yb, xa:xb] += d[ya - oy:yb - oy, xa - ox:xb - ox]


def _img(a): return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGB')


def _wob(q, seed, amp):
    """手绘抖动：确定性的低频噪声（同一 seed 每帧一样，不会闪）"""
    return amp * (math.sin(3.1 * q + seed) + 0.6 * math.sin(7.3 * q + 2.1 * seed) + 0.3 * math.sin(13.7 * q + 0.7 * seed))


# ---------- 镜头 ----------
def cam_keys(t, keys, ease=None):
    """镜头关键帧插值：keys = [(时刻, z, cx, cy), ...]（按时刻排好），返回当前 (z, cx, cy)。
    时刻可以直接写 B[2]、B.at(3, '6.5%')；两帧之间默认 eio 缓动，ease 可换成别的 0~1 函数。"""
    ease = ease or eio
    if t <= keys[0][0]: return keys[0][1:]
    for (ta, *va), (tb, *vb) in zip(keys, keys[1:]):
        if t < tb:
            q = ease((t - ta) / max(1e-6, tb - ta))
            return tuple(lerp(x, y, q) for x, y in zip(va, vb))
    return keys[-1][1:]


def camera(f, z=1.0, cx=W / 2, cy=520, box=CONTENT):
    """镜头：把内容区放大 z 倍、视野中心对准 (cx, cy)（原画面坐标）；z、cx、cy 随 t 变就是推近 / 平移 / 拉远。
    在分镜函数最后调用（作用在已经画好的像素上；片头条、字幕、进度条不受影响）。
    画面上记下的字的位置会一起换算，所以"讲到谁亮谁"和对口型检查照常工作。
    box 是镜头作用的范围，默认整个内容区（含章节标题）；不想让标题跟着动就传 box=(0, 240, W, 920) 之类。
    只有画上去的内容在动，背景（渐变和点阵）不动。像素放大会变软：z 在 1.0~1.25 之间看不出来，再大字会糊。返回实际视野框。"""
    if z <= 1.0005: return box
    bx0, by0, bx1, by1 = box; bw, bh = bx1 - bx0, by1 - by0
    vw, vh = bw / z, bh / z
    x0 = clamp(cx - vw / 2, bx0, bx1 - vw); y0 = clamp(cy - vh / 2, by0, by1 - vh)
    view = (x0, y0, x0 + vw, y0 + vh)
    vb = tuple(int(round(v)) for v in view); bg = background()
    d = _delta(f.im.crop(vb).resize((bw, bh), Image.BICUBIC), bg.crop(vb).resize((bw, bh), Image.BICUBIC))
    f.im.paste(_img(np.asarray(bg.crop(box), np.int16) + d), (bx0, by0))
    sx, sy = bw / vw, bh / vh
    mp = lambda b: (bx0 + (b[0] - x0) * sx, by0 + (b[1] - y0) * sy, bx0 + (b[2] - x0) * sx, by0 + (b[3] - y0) * sy)
    if f.rec is not None:
        f.rec[:] = [(s, mp(b), aa, size * z) for s, b, aa, size in f.rec]
    if f.cards is not None:
        f.cards[:] = [(mp(b), aa, ri) for b, aa, ri in f.cards]
    return view


# ---------- 对比 ----------
def versus(f, t, t0, box, left, right, mode='bars', d=0.9, fmt='{:.1f}', unit='', diff=True, diff_fmt=None,
           vmax=None, a=1.0, size=30, lsize=24, chip_col=GOLD):
    """两个数放在一起比：left / right = (标签, 值, 颜色)。
    mode='bars'  两根横条上下排，从左边一起长出来，到位后两端拉虚线、中间弹出差额；
    mode='clash' 两块从左右两边相向推过来，在按比例分好的位置撞上，撞点闪一下，再弹出差额。
    diff：True 显示差值（右 − 左），'ratio' 显示倍数（右 ÷ 左），'pct' 显示变化率，False 不显示；
    diff_fmt 可自己写，接收一个数返回字符串。返回进度 p。"""
    if a <= 0.01 or t < t0: return 0.0
    (la, va, ca), (lb, vb, cb) = left, right
    x0, y0, x1, y1 = box; p = eio(pg(t, t0, d))
    if diff is True: dv = vb - va; txt = (diff_fmt or (lambda v: ('+' if v >= 0 else '') + fmt.format(v) + unit))(dv)
    elif diff == 'ratio': dv = vb / va if va else 0; txt = (diff_fmt or (lambda v: f'{v:.1f} 倍'))(dv)
    elif diff == 'pct': dv = (vb / va - 1) * 100 if va else 0; txt = (diff_fmt or (lambda v: ('+' if v >= 0 else '') + f'{v:.0f}%'))(dv)
    else: txt = None
    q = pg(t, t0 + d, 0.5)
    if mode == 'clash':
        m = x0 + (x1 - x0) * va / max(1e-9, va + vb); h = y1 - y0
        xa = lerp(x0, m, p); xb = lerp(x1, m, p)
        f.rect((x0, y0, xa - 3, y1), ca, a, r=10); f.rect((xb + 3, y0, x1, y1), cb, a, r=10)
        f.text((x0 + 24, y0 + h * 0.34), la, lsize, TXT, a * p, 'b', 'lm')
        f.text((x0 + 24, y0 + h * 0.66), fmt.format(va) + unit, size, TXT, a * p, 'n', 'lm')
        f.text((x1 - 24, y0 + h * 0.34), lb, lsize, TXT, a * p, 'b', 'rm')
        f.text((x1 - 24, y0 + h * 0.66), fmt.format(vb) + unit, size, TXT, a * p, 'n', 'rm')
        if p >= 1:
            fl = out(t, t0 + d, 0.45)
            if fl > 0.01:
                L = AA(f, (m - 80, y0 - 60, m + 80, y1 + 60))
                L.circle(m, (y0 + y1) / 2, 30 + 50 * (1 - fl), (255, 255, 255), 0.5 * fl * a); L.done()
        if txt and q > 0:
            f.chip((m, y1 + 18 + 10 * (1 - q)), txt, chip_col, a * q, int(size * 0.85), anchor='c')
        return p
    vmax = vmax or max(va, vb) * 1.1
    rh = (y1 - y0) / 2; bh = rh * 0.42; ends = []
    for k, (lab, v, c) in enumerate(((la, va, ca), (lb, vb, cb))):
        ry = y0 + rh * k; L = (x1 - x0) * max(v, 0) / vmax * p; by = ry + rh * 0.42
        f.text((x0, ry + rh * 0.22), lab, lsize, SUB, a, 'b', 'lm')
        f.rect((x0, by, x0 + L, by + bh), c, a, r=6)
        f.text((x0 + L + 14, by + bh / 2), fmt.format(v * p if p < 1 else v) + unit, size, TXT, a * clamp(p * 2 - 0.4), 'n', 'lm')
        ends.append((x0 + L, by, by + bh))
    if txt and q > 0:
        (ea, ta, ba), (eb, tb, bb) = ends
        for ex in (ea, eb): f.dash(ex, ta - 6, ex, bb + 6, chip_col, 2, a * q * 0.8, 6, 5)
        f.line([(ea, (ta + bb) / 2), (eb, (ta + bb) / 2)], chip_col, 2, a * q)
        cx = (ea + eb) / 2 if abs(eb - ea) > 140 else max(ea, eb) + 90
        f.chip((cx, (ba + tb) / 2 - (size * 0.85 + 20) / 2), txt, chip_col, a * q, int(size * 0.85), anchor='c')
    return p


# ---------- 时间轴 ----------
def _inv_eio(y):
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if eio(mid) < y: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def timeline(f, t, t0, box, events, d=1.6, col=GOLD, a=1.0, ticks=None, size=24, sub_size=20, stem=70, alt=True,
             axis_col=SUB):
    """时间轴：轴在 t0 起 d 秒从左扫到右，扫到哪个事件就在那里落一个点、拉出文字。
    events = [(位置 0~1, 标签, 说明 或 None, 落点时刻 或 None, 颜色 或 None), ...]（后三项可省）；
    指定了落点时刻的事件按那个时刻出现（可以挂到 B.at(...)），没指定的跟着扫描线。
    alt=True 文字上下交替，False 全在上方；ticks = [(位置, 文字)] 轴下刻度。返回各事件 x。"""
    if a <= 0.01 or t < t0: return []
    x0, y0, x1, y1 = box; y = (y0 + y1) / 2
    p = eio(pg(t, t0, d)); xe = lerp(x0, x1, p)
    f.line([(x0, y), (xe, y)], axis_col, 3, a * 0.8)
    if 0 < p < 1: marker(f, xe, y, col, a, 6)
    for pos, lab in (ticks or []):
        tx = lerp(x0, x1, pos)
        if tx <= xe: f.line([(tx, y - 7), (tx, y + 7)], axis_col, 2, a * 0.8); f.text((tx, y + 26), lab, 18, DIM, a, 'n', 'mm')
    xs = []
    for k, ev in enumerate(events):
        pos, lab = ev[0], ev[1]; sub = ev[2] if len(ev) > 2 else None
        te = ev[3] if len(ev) > 3 and ev[3] is not None else t0 + d * _inv_eio(pos)
        c = ev[4] if len(ev) > 4 and ev[4] else col
        x = lerp(x0, x1, pos); xs.append(x); q = pg(t, te, 0.5)
        if q <= 0: continue
        up = (k % 2 == 0) or not alt; sg = -1 if up else 1
        drop = 26 * (1 - eo(q))
        L = AA(f, (x - 30, y - 30 - drop, x + 30, y + 30)); L.circle(x, y - drop, 8 * (1 + 0.3 * _bump(q)), c, a * q); L.done()
        ys = y + sg * 14; ye = y + sg * (14 + stem * eo(q))
        f.line([(x, ys), (x, ye)], c, 2, a * q)
        f.text((x, ye + sg * 20), lab, size, c, a * q, 'b', 'mm')
        if sub: f.text((x, ye + sg * (20 + size + 4)), sub, sub_size, TXT, a * q, 'r', 'mm')
    return xs


# ---------- 强调 ----------
def ring(f, t, t0, box, col=GOLD, w=4, d=0.6, a=1.0, pad=14, turns=1.12, wobble=0.03, seed=1, start=200):
    """手绘圈：绕 box 画一个略歪的椭圆，收尾多绕一点、和起笔错开（像笔圈出来的）。seed 换一个就是另一种歪法。返回进度。"""
    if a <= 0.01 or t < t0: return 0.0
    p = eo(pg(t, t0, d))
    x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2 + pad, (y1 - y0) / 2 + pad
    n = max(16, int(140 * turns * p)); pts = []
    for k in range(n + 1):
        q = turns * p * k / n; ang = math.radians(start) + 2 * math.pi * q
        r = 1 + _wob(ang, seed, wobble) + 0.06 * q
        pts.append((cx + rx * r * math.cos(ang), cy + ry * r * math.sin(ang)))
    m = max(rx, ry) * 0.4 + w + 10
    L = AA(f, (cx - rx - m, cy - ry - m, cx + rx + m, cy + ry + m)); L.line(pts, col, w, a); L.done()
    return p


def arrow(f, t, t0, p0, p1, col=GOLD, w=4, d=0.5, bend=0.2, head=20, a=1.0, wobble=0.0, seed=2, dash=False):
    """箭头：从 p0 画到 p1，bend 控制弯曲（正负换方向，0 是直线），画到头再长出箭头。
    wobble > 0 有手绘抖动；dash=True 画成虚线。返回进度。"""
    if a <= 0.01 or t < t0: return 0.0
    p = eo(pg(t, t0, d))
    (ax, ay), (bx, by) = p0, p1; L_ = math.hypot(bx - ax, by - ay) or 1
    nx, ny = -(by - ay) / L_, (bx - ax) / L_
    cx, cy = (ax + bx) / 2 + nx * bend * L_, (ay + by) / 2 + ny * bend * L_
    def at(q):
        x = (1 - q) ** 2 * ax + 2 * (1 - q) * q * cx + q * q * bx
        y = (1 - q) ** 2 * ay + 2 * (1 - q) * q * cy + q * q * by
        o = _wob(q * 6, seed, wobble * L_ * 0.05) if wobble else 0
        return x + nx * o, y + ny * o
    n = max(8, int(60 * p)); pts = [at(p * k / n) for k in range(n + 1)]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    L = AA(f, (min(xs) - head - 10, min(ys) - head - 10, max(xs) + head + 10, max(ys) + head + 10))
    if dash:
        for k in range(0, len(pts) - 1, 2): L.line(pts[k:k + 2], col, w, a)
    else:
        L.line(pts, col, w, a)
    if p > 0.85:
        hq = clamp((p - 0.85) / 0.15); (px, py), (qx, qy) = pts[-2], pts[-1]
        ang = math.atan2(qy - py, qx - px); hl = head * hq
        L.poly([(qx, qy), (qx - hl * math.cos(ang - 0.45), qy - hl * math.sin(ang - 0.45)),
                (qx - hl * math.cos(ang + 0.45), qy - hl * math.sin(ang + 0.45))], col, a)
    L.done()
    return p


def highlight(f, t, t0, box, col=GOLD, d=0.4, a=0.3, pad=(10, 4), skew=8):
    """荧光笔从左往右划过 box（略斜、两头不齐）。要在画字之前调用，字才会压在色块上面。返回进度。"""
    if a <= 0.01 or t < t0: return 0.0
    p = eo(pg(t, t0, d))
    x0, y0, x1, y1 = box; px, py = pad
    x0 -= px; x1 = lerp(x0, x1 + px, p); y0 -= py; y1 += py
    L = AA(f, (x0 - skew - 4, y0 - 4, x1 + skew + 4, y1 + 4))
    L.poly([(x0 + skew, y0), (x1 + skew * 0.4, y0 + 2), (x1, y1), (x0, y1 - 2)], col, a); L.done()
    return p


def underline(f, t, t0, x0, x1, y, col=GOLD, w=4, d=0.45, a=1.0, wobble=3.0, seed=3, double=False):
    """手绘下划线（带一点起伏，double=True 画两道）。返回进度。"""
    if a <= 0.01 or t < t0: return 0.0
    p = eo(pg(t, t0, d))
    L = AA(f, (x0 - 10, y - 30, x1 + 10, y + 30))
    for k in range(2 if double else 1):
        pk = clamp(p * (1.25 if double else 1) - 0.25 * k)
        if pk <= 0: continue
        n = 40; pts = []
        for i in range(int(n * pk) + 1):
            q = i / n; pts.append((lerp(x0, x1, q), y + 9 * k + _wob(q * 5, seed + k, wobble / 2) - 3 * q * (1 - k)))
        if len(pts) > 1: L.line(pts, col, w - k, a)
    L.done()
    return p


# ---------- 瀑布图 ----------
def waterfall(f, t, t0, box, steps, stagger=0.55, d=0.6, vmax=None, vmin=None, fmt='{:.0f}', a=1.0, total_col=GOLD,
              up_col=RED, down_col=GREEN, connectors=True, lsize=22, vsize=26, bar=0.58, signed=True):
    """瀑布图：steps = [(标签, 值, 种类), ...]，种类 'total' 从 0 画到值（值写 None 就取前面累计的结果），
    'delta'（默认，可省）从当前累计往上加 / 往下减——减项从上一根的水平线往下长。第 i 根在 t0 + i*stagger 开始。
    颜色：总量 total_col，加项 up_col，减项 down_col（默认红加绿减；红绿表示好坏时记得配 components.legend）。
    signed=True 增减项数字带 +/−。返回 [(柱中心 x, 柱顶 y, 柱底 y), ...]。"""
    if a <= 0.01: return []
    rows, cur = [], 0.0
    for st in steps:
        lab, v = st[0], st[1]; kind = st[2] if len(st) > 2 else 'delta'
        if kind == 'total':
            v = cur if v is None else v; rows.append((lab, 0.0, v, v, kind)); cur = v
        else:
            rows.append((lab, cur, cur + v, v, kind)); cur += v
    lv = [r[1] for r in rows] + [r[2] for r in rows]
    vmax = vmax if vmax is not None else max(lv) * 1.12
    vmin = vmin if vmin is not None else min(0.0, min(lv) * 1.12)
    x0, y0, x1, y1 = box; n = len(rows); slot = (x1 - x0) / n; bw = slot * bar
    Y = lambda v: ymap(box, v, vmin, vmax); out_ = []
    if vmin < 0: f.line([(x0, Y(0)), (x1, Y(0))], GRID, 1, 0.6 * a)
    for i, (lab, frm, to, v, kind) in enumerate(rows):
        cx = x0 + slot * (i + 0.5); p = eio(pg(t, t0 + i * stagger, d)) if t >= t0 + i * stagger else 0.0
        c = total_col if kind == 'total' else (up_col if v >= 0 else down_col)
        end = lerp(frm, to, p); ya, yb = Y(frm), Y(end)
        top, bot = min(ya, yb), max(ya, yb); out_.append((cx, min(Y(frm), Y(to)), max(Y(frm), Y(to))))
        f.text((cx, y1 + 24), str(lab), lsize, DIM, a, 'b', 'mm')
        if p <= 0: continue
        f.rect((cx - bw / 2, top, cx + bw / 2, bot), c, a, r=5)
        s = (('+' if v > 0 else '−' if v < 0 else '') if (signed and kind != 'total') else '') + fmt.format(abs(v) if signed and kind != 'total' else v)
        ty = (top - 20) if (kind == 'total' or v >= 0) else (bot + 22)
        f.text((cx, ty), s, vsize, TXT if kind == 'total' else c, a * clamp(p * 2 - 0.6), 'n', 'mm')
        if connectors and i + 1 < n and p >= 1:
            q = pg(t, t0 + i * stagger + d, 0.3); yc = Y(to)
            f.dash(cx + bw / 2, yc, cx + bw / 2 + (slot - bw) * q, yc, SUB, 2, 0.7 * a, 6, 5)
    return out_


# ---------- 桑基图 ----------
def sankey(f, t, t0, box, cols, flows, d=1.4, stagger=0.12, a=1.0, node_w=16, gap=18, fmt='{:.0f}', lsize=22,
           band_a=0.38, hl=None, hla=0.0, label_vals=True, unit='', color_by='source'):
    """桑基图：cols = [[(标签, 颜色), ...], ...] 从左到右每列一组节点；flows = [((列, 序号), (列, 序号), 值), ...]，
    可以跨多列（收入 → 成本 / 费用 / 利润 → 分红 / 留存 ……）。节点高度按流量（流入、流出取大者）。
    t0 起一列一列往右流出去（整体 d 秒，同列的带子错开 stagger）；hl = 要突出的那条流的序号，其余按 hla 变暗。
    color_by='source' 带子用起点节点的颜色，'target' 用终点的颜色。
    返回 {(列, 序号): 节点框}，方便在旁边再标注。"""
    if a <= 0.01 or t < t0: return {}
    x0, y0, x1, y1 = box; nc = len(cols)
    val = {}
    for (s, e, v) in flows:
        val.setdefault(s, [0, 0]); val.setdefault(e, [0, 0]); val[s][1] += v; val[e][0] += v
    nv = {(c, i): max(val.get((c, i), [0, 0])) for c in range(nc) for i in range(len(cols[c]))}
    colsum = [sum(nv[(c, i)] for i in range(len(cols[c]))) for c in range(nc)]
    sc = min((y1 - y0 - gap * (len(cols[c]) - 1)) / max(1e-9, colsum[c]) for c in range(nc))
    nodes = {}
    for c in range(nc):
        hsum = colsum[c] * sc + gap * (len(cols[c]) - 1); yy = (y0 + y1) / 2 - hsum / 2
        nx = x0 + (x1 - x0 - node_w) * c / max(1, nc - 1)
        for i in range(len(cols[c])):
            h = nv[(c, i)] * sc; nodes[(c, i)] = (nx, yy, nx + node_w, yy + h); yy += h + gap
    dcol = d / max(1, nc - 1)
    off_out = {k: 0.0 for k in nodes}; off_in = {k: 0.0 for k in nodes}
    order = sorted(range(len(flows)), key=lambda k: (flows[k][0], flows[k][1]))
    geo = {}
    for k in order:
        s, e, v = flows[k]; h = v * sc; geo[k] = (nodes[s][1] + off_out[s], nodes[e][1] + off_in[e], h)
        off_out[s] += h
    for k in sorted(range(len(flows)), key=lambda k: (flows[k][1], flows[k][0])):
        s, e, v = flows[k]; h = v * sc; geo[k] = (geo[k][0], nodes[e][1] + off_in[e], h); off_in[e] += h
    arrive = {k: t0 for k in nodes if k[0] == 0}
    seq = {}
    for k in sorted(range(len(flows)), key=lambda k: flows[k][0]):
        seq.setdefault(flows[k][0][0], []).append(k)
    L = AA(f, (x0 - 4, y0 - 4, x1 + 4, y1 + 4))
    for c in sorted(seq):
        for j, k in enumerate(seq[c]):
            s, e, v = flows[k]; ts = t0 + dcol * s[0] + stagger * j; span = (e[0] - s[0]) * dcol
            p = eio(pg(t, ts, span)) if t >= ts else 0.0
            arrive[e] = min(arrive.get(e, 1e9), ts + span * 0.85)
            if p <= 0: continue
            sy, ey, h = geo[k]; sx, ex = nodes[s][2], nodes[e][0]
            dim = (1 - hla) if (hl is not None and k != hl) else 1
            n = 40; top, bot = [], []
            for i in range(int(n * p) + 1):
                q = i / n; u = q * q * (3 - 2 * q)
                x = lerp(sx, ex, q); top.append((x, lerp(sy, ey, u))); bot.append((x, lerp(sy, ey, u) + h))
            if len(top) > 1:
                bc = cols[e[0]][e[1]][1] if color_by == 'target' else cols[s[0]][s[1]][1]
                L.poly(top + bot[::-1], bc, band_a * a * dim)
    L.done()
    for (c, i), (nx0, ny0, nx1, ny1) in nodes.items():
        q = pg(t, arrive.get((c, i), t0), 0.4)
        if q <= 0: continue
        lab, col = cols[c][i]; f.rect((nx0, ny0, nx1, ny1), col, a * q, r=3)
        s = f'{lab} {fmt.format(nv[(c, i)])}{unit}' if label_vals else lab
        if c == 0: f.text((nx0 - 12, (ny0 + ny1) / 2), s, lsize, TXT, a * q, 'b', 'rm')       # 第一列标在左边
        elif c == nc - 1: f.text((nx1 + 12, (ny0 + ny1) / 2), s, lsize, TXT, a * q, 'b', 'lm')  # 最后一列标在右边
        else: f.text((nx1 + 10, ny0 - 4), s, lsize, TXT, a * q, 'b', 'ls')                     # 中间列标在节点右上
    return nodes


# ---------- 转场 ----------
def _sub(f, im):
    fr = Frame(im)
    fr.rec = [] if f.rec is not None else None
    fr.cards = [] if f.cards is not None else None
    fr.fills = set() if f.fills is not None else None
    return fr


def _merge(f, fr):
    if f.rec is not None:
        base = len(f.rec); f.rec.extend(fr.rec)
        if fr.cover: f.cover = max(f.cover, base + fr.cover)
        if f.cards is not None: f.cards.extend((b, aa, ri + base) for b, aa, ri in fr.cards)
    if f.fills is not None: f.fills |= fr.fills
    f.legend = f.legend or fr.legend


def transition(f, t, t0, draw_a, draw_b, d=0.6, mode='wipe', direction='right', box=CONTENT, center=None,
               edge=GOLD, strips=8):
    """同一块画面从状态 A 换到 B：draw_a(fr)、draw_b(fr) 各画一个状态，fr 是临时画布，用法和 f 一样。
    mode：'fade' 交叉淡化；'wipe' 擦除（direction = right / left / down / up，擦除线往那边走，带一道亮边）；
          'slide' 整块推走（direction 同上，是内容移动的方向）；'flip' 翻牌；'iris' 圆形展开（center 指定圆心）；
          'blinds' 百叶窗（strips 条）。t < t0 只画 A，t ≥ t0 + d 只画 B，中间只合成 box 这一块。返回进度。"""
    p = eio(clamp((t - t0) / d)) if t >= t0 else 0.0
    if p <= 0: draw_a(f); return 0.0
    if p >= 1: draw_b(f); return 1.0
    base = f.im.copy(); fa, fb = _sub(f, base.copy()), _sub(f, base.copy())
    draw_a(fa); draw_b(fb)
    bx0, by0, bx1, by1 = [int(v) for v in box]; w, h = bx1 - bx0, by1 - by0
    A, B, G = fa.im.crop((bx0, by0, bx1, by1)), fb.im.crop((bx0, by0, bx1, by1)), base.crop((bx0, by0, bx1, by1))
    if mode == 'fade':
        R = Image.blend(A, B, p)
    elif mode in ('wipe', 'iris', 'blinds'):
        if mode == 'wipe':
            soft = 60; L_ = w if direction in ('right', 'left') else h
            ax = np.arange(L_, dtype=np.float32)
            if direction in ('left', 'up'): ax = ax[::-1]
            e = p * (L_ + soft); m = np.clip((e - ax) / soft, 0, 1)
            m = np.tile(m, (h, 1)) if direction in ('right', 'left') else np.tile(m[:, None], (1, w))
        elif mode == 'iris':
            cx, cy = (center[0] - bx0, center[1] - by0) if center else (w / 2, h / 2)
            yy, xx = np.mgrid[0:h, 0:w]; dist = np.hypot(xx - cx, yy - cy)
            rmax = max(math.hypot(cx - x, cy - y) for x in (0, w) for y in (0, h)); soft = 40
            m = np.clip((p * (rmax + soft) - dist) / soft, 0, 1)
        else:
            sw = w / strips; xx = np.arange(w, dtype=np.float32); k = np.floor(xx / sw)
            pk = np.clip(p * 1.6 - k / strips * 0.6, 0, 1); m = np.tile(((xx - k * sw) < pk * sw).astype(np.float32), (h, 1))
        R = Image.composite(B, A, Image.fromarray((m * 255).astype(np.uint8), 'L'))
        if mode == 'wipe':
            dr = ImageDraw.Draw(R, 'RGBA'); ea = int(220 * math.sin(math.pi * p))
            ep = int(p * (L_ + soft) - soft / 2)
            if direction in ('left', 'up'): ep = L_ - ep
            if direction in ('right', 'left'): dr.line([(ep, 0), (ep, h)], fill=edge + (ea,), width=3)
            else: dr.line([(0, ep), (w, ep)], fill=edge + (ea,), width=3)
    elif mode == 'slide':       # 只推内容，背景不动
        dx, dy = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[direction]
        ox, oy = int(dx * w * p), int(dy * h * p); o = np.asarray(G, np.int16).copy()
        _add(o, _delta(A, G), ox, oy); _add(o, _delta(B, G), ox - dx * w, oy - dy * h); R = _img(o)
    elif mode == 'flip':        # 内容横向压扁再展开，翻到一半换成 B
        s = abs(math.cos(math.pi * p)); src = A if p < 0.5 else B; sw_ = max(1, int(w * s))
        dd = _delta(src.resize((sw_, h), Image.BILINEAR), G.resize((sw_, h), Image.BILINEAR)) * (1 - 0.35 * (1 - s))
        o = np.asarray(G, np.int16).copy(); _add(o, dd.astype(np.int16), (w - sw_) // 2, 0); R = _img(o)
    else:
        raise ValueError(f'transition 不认识 mode={mode}')
    f.im.paste(R, (bx0, by0))
    _merge(f, fa if p < 0.5 else fb)
    return p
