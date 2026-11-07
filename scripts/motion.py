# -*- coding: utf-8 -*-
r"""motion.py —— 暗色个股片的逐帧动画引擎（52号起的唯一渲染管线）

源自「爱美客_自由版」的自写渲染器，抽成通用库。每期只写一个分镜脚本：

    import sys; sys.path.insert(0, '<skill>/scripts')
    import motion as M
    from motion import *          # 配色、Frame、缓动、图表原语

    def s0(f, t, B, T): ...       # 每个场景一个绘制函数：f=画布, t=场景内秒, B=每句开始时刻, T=场景总长
    M.setup(root=..., name='爱美客', code='300896.SZ', source='数据：…  |  截至 2026.10.28',
            scenes=[('开场', [句1, 句2, ...], s0), ...])   # 必须写在模块顶层（多进程渲染要重新 import）
    if __name__ == '__main__': M.cli()

命令：tts → preview → render → mux（all 一次跑完；render resume 断点续渲；render --jobs 4 指定并行数）
check（preview 末尾自动跑）：不渲染，列出"念到的数字画面上没有""除章标题外什么都没有""空框"
"数字滚动前先显示 0""滚动中露出长小数""video.py 写死 facts 里的数 / 手写算式"，写 output/check.txt
动画的基本写法：a = pg(t, B[2])  →  第 3 句开口时开始、0.7 秒内从 0 缓动到 1，用来控制透明度/长度/数字。
长句里的第二、三个意思挂到它被念到的那一刻：pg(t, B.at(2, '6.5%')) = 第 3 句念到"6.5%"时；
B.S[2][1] = 第 3 句第 2 条字幕开口时（字幕在逗号处切）。
引擎自动做的"讲到谁亮谁"：字幕念到的数字 / 短标签如果早已在画面上，它所在的那一块（色条的一段、柱子；
不在色块上就是字本身）整体提亮、带柔光，其余内容稍退；不加框、不贴标签。这条字幕念完淡出（setup(spotlight=False) 关掉）。
"""
import os, sys, json, math, re, asyncio, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sysenv

W, H, FPS = 1920, 1080, 30
SR = 24000

# ---------- 配色（A股习惯：涨红跌绿） ----------
TXT = (236, 241, 250); SUB = (150, 166, 194); DIM = (92, 108, 140)
GOLD = (245, 185, 66); TEAL = (56, 189, 248); INDIGO = (110, 115, 245)
RED = (255, 82, 82); GREEN = (34, 197, 120); PURPLE = (176, 140, 255); ORANGE = (240, 130, 100)
CARD = (18, 30, 58); EDGE = (52, 72, 112); GREY = (78, 94, 128); GRID = (60, 78, 115)

FR, FB, FN = sysenv.font_file('r'), sysenv.font_file('b'), sysenv.font_file('n')   # 本机字体，见 sysenv.py
_fc = {}
def font(size, kind='r'):
    """r=正文 b=粗体 n=数字字体（含中文时自动混排）；具体字体按本机取，见 sysenv.py"""
    k = (int(size), kind)
    if k not in _fc:
        fp, fi = {'r': FR, 'b': FB, 'n': FN}[kind]
        f = ImageFont.truetype(fp, int(size), index=fi)
        if kind == 'n':
            for nm in ('Bold', b'Bold', 'SemiBold'):
                try: f.set_variation_by_name(nm); break
                except Exception: pass
        _fc[k] = f
    return _fc[k]

# ---------- 缓动 ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def pg(t, t0, d=0.7):
    """进度：t0 时刻开始，d 秒内 0→1（ease-out）"""
    return eo((t - t0) / d)
def out(t, t0, d=0.4):
    """反向进度：t0 时刻开始淡出 1→0"""
    return 1 - eo((t - t0) / d)
def lerp(a, b, p): return a + (b - a) * p
def lerpc(c1, c2, p): return tuple(int(lerp(a, b, p)) for a, b in zip(c1, c2))
def sgn_col(v): return RED if v > 0 else GREEN

# ---------- 画布 ----------
class Frame:
    def __init__(self, im):
        self.im = im; self.d = ImageDraw.Draw(im, 'RGBA')
    def _runs(self, s, size):
        runs = re.findall(r'[\x00-\x7f]+|[^\x00-\x7f]+', s)
        fs = [font(size, 'n') if ord(r[0]) < 128 else font(int(size * 0.8), 'b') for r in runs]
        return runs, fs, [self.d.textlength(r, font=fn) for r, fn in zip(runs, fs)]
    rec = None          # 分镜绘制期间记下画了哪些字（给"讲到谁亮谁"用），其余时候为 None
    cover = 0           # overlay 压暗时，记下此前画的字已被盖住
    def text(self, xy, s, size=36, col=TXT, a=1.0, kind='r', anchor='la', stroke=0):
        """anchor 两个字母：水平 l/m/r + 垂直 a/m/s/d（同 PIL）"""
        if a <= 0.01 or s == '': return
        fill = col + (int(255 * clamp(a)),); sf = (0, 0, 0, int(200 * clamp(a)))
        if kind == 'n' and any(ord(ch) > 127 for ch in s):
            runs, fs, ws = self._runs(s, size); tot = sum(ws); x, y = xy
            x -= tot / 2 if anchor[0] == 'm' else tot if anchor[0] == 'r' else 0
            if self.rec is not None:
                bb = self.d.textbbox((x, y), runs[0], font=fs[0], anchor='l' + anchor[1])
                self.rec.append((s, (x, bb[1], x + tot, bb[3]), a, size))
                if self.recx is not None: self.recx.append((col, kind))
            for r, fn, w in zip(runs, fs, ws):
                self.d.text((x, y), r, font=fn, fill=fill, anchor='l' + anchor[1], stroke_width=stroke, stroke_fill=sf); x += w
            return
        if self.rec is not None:
            self.rec.append((s, self.d.textbbox(xy, s, font=font(size, kind), anchor=anchor), a, size))
            if self.recx is not None: self.recx.append((col, kind))
        self.d.text(xy, s, font=font(size, kind), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sf)
    def tw(self, s, size, kind='r'):
        if kind == 'n' and any(ord(ch) > 127 for ch in s): return sum(self._runs(s, size)[2])
        return self.d.textlength(s, font=font(size, kind))
    fills = None        # check 期间记下画过的红 / 绿色块（查"红绿同屏没图例"）
    legend = False      # components.legend 画过图例就置 True
    blocks = None       # 分镜绘制期间记下实心色块（给"讲到谁亮谁"找字所在的那一段）
    recx = None         # 和 rec 一一对应的 (颜色, 字体)：被讲到的那段重画时，字照原色放大加粗
    def rect(self, box, col, a=1.0, r=0, outline=None, ow=2, oa=None):
        if a <= 0.01 and not (outline and (oa or 0) > 0.01): return
        if self.blocks is not None and col and a > 0.5 and tuple(col[:3]) != CARD:
            self.blocks.append((tuple(box), len(self.rec or []), tuple(col[:3])))
        if self.fills is not None and col and a > 0.5:
            rr, gg, bb = col[:3]
            if rr > gg + 60 and rr > bb + 60: self.fills.add('红')
            elif gg > rr + 50 and gg > bb: self.fills.add('绿')
        box = [int(round(v)) for v in box]
        if box[2] <= box[0] or box[3] <= box[1]: return
        fill = col + (int(255 * clamp(a)),) if col else None
        oc = outline + (int(255 * clamp(a if oa is None else oa)),) if outline else None
        if r: self.d.rounded_rectangle(box, r, fill=fill, outline=oc, width=ow)
        else: self.d.rectangle(box, fill=fill, outline=oc, width=ow)
    def line(self, pts, col, w=1, a=1.0):
        if a > 0.01: self.d.line(pts, fill=col + (int(255 * clamp(a)),), width=int(w))
    def dash(self, x0, y0, x1, y1, col, w=2, a=1.0, on=10, off=8):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1 or a <= 0.01: return
        for i in range(int(L // (on + off)) + 1):
            s = i * (on + off) / L; e = min(1, (i * (on + off) + on) / L)
            if s >= 1: break
            self.line([(x0 + (x1 - x0) * s, y0 + (y1 - y0) * s), (x0 + (x1 - x0) * e, y0 + (y1 - y0) * e)], col, w, a)
    cards = None        # check 期间记下画了哪些卡片框（查"空框"）
    def card(self, box, a=1.0, edge=EDGE):
        if self.cards is not None: self.cards.append((tuple(box), a, len(self.rec or [])))
        self.rect(box, CARD, 0.82 * a, r=18, outline=edge, ow=2, oa=0.9 * a)
    def chip(self, xy, s, col, a=1.0, size=26, fill=True, anchor='l'):
        """胶囊标签；anchor l/c/r 指 xy 是左端/中心/右端，y 是顶边"""
        if a <= 0.01: return 0
        w = self.tw(s, size, 'b') + 32; h = size + 20; x, y = xy
        if anchor == 'c': x -= w / 2
        if anchor == 'r': x -= w
        self.rect((x, y, x + w, y + h), col if fill else None, 0.22 * a if fill else 0, r=h // 2, outline=col, ow=2, oa=a)
        self.text((x + w / 2, y + h / 2), s, size, col, a, 'b', 'mm')
        return w

class AA:
    """2 倍超采样图层：抗锯齿折线/圆弧/圆"""
    def __init__(self, f, box, s=2):
        self.f = f; self.b = [int(v) for v in box]; self.s = s
        self.im = Image.new('RGBA', ((self.b[2] - self.b[0]) * s, (self.b[3] - self.b[1]) * s), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im, 'RGBA')
    def p(self, x, y): return ((x - self.b[0]) * self.s, (y - self.b[1]) * self.s)
    def line(self, pts, col, w, a=1.0):
        if len(pts) > 1: self.d.line([self.p(*q) for q in pts], fill=col + (int(255 * a),), width=int(w * self.s), joint='curve')
    def poly(self, pts, col, a): self.d.polygon([self.p(*q) for q in pts], fill=col + (int(255 * a),))
    def circle(self, x, y, r, col, a=1.0, outline=None, w=0):
        (cx, cy) = self.p(x, y); r *= self.s
        self.d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col + (int(255 * a),) if col else None,
                       outline=outline + (int(255 * a),) if outline else None, width=int(w * self.s))
    def arc(self, x, y, r, a0, a1, col, w, a=1.0):
        if a1 - a0 < 0.2: return
        (cx, cy) = self.p(x, y); r *= self.s
        self.d.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=col + (int(255 * a),), width=int(w * self.s))
    def done(self):
        sm = self.im.resize((self.b[2] - self.b[0], self.b[3] - self.b[1]), Image.LANCZOS)
        self.f.im.paste(sm, (self.b[0], self.b[1]), sm)

# ---------- 图表原语 ----------
def to_xy(box, vals, vmin, vmax):
    x0, y0, x1, y1 = box; n = len(vals)
    return [(x0 + (x1 - x0) * i / max(1, n - 1), y1 - (y1 - y0) * (v - vmin) / (vmax - vmin)) for i, v in enumerate(vals)]
def ymap(box, v, vmin, vmax): return box[3] - (box[3] - box[1]) * (v - vmin) / (vmax - vmin)
def partial(pts, p):
    """折线按进度 p 画出前一部分（描线动画）"""
    if p <= 0: return pts[:1]
    k = p * (len(pts) - 1); i = int(k); fr = k - i
    o = list(pts[:i + 1])
    if i < len(pts) - 1:
        a, b = pts[i], pts[i + 1]; o.append((a[0] + (b[0] - a[0]) * fr, a[1] + (b[1] - a[1]) * fr))
    return o
def draw_line(f, box, pts, col, w=4, fill_a=0.0, base=None, a=1.0, dot=True):
    if len(pts) < 2 or a <= 0.01: return
    L = AA(f, (box[0] - 20, box[1] - 20, box[2] + 20, box[3] + 20))
    if fill_a > 0: L.poly(pts + [(pts[-1][0], base), (pts[0][0], base)], col, fill_a * a)
    L.line(pts, col, w, a)
    if dot: L.circle(pts[-1][0], pts[-1][1], w * 1.6, col, a)
    L.done()
def grid(f, box, vmin, vmax, ticks, fmt='{:g}', a=1.0, size=20):
    x0, y0, x1, y1 = box
    for v in ticks:
        y = ymap(box, v, vmin, vmax)
        f.line([(x0, y), (x1, y)], GRID, 1, 0.6 * a)
        f.text((x0 - 12, y), fmt.format(v), size, DIM, a, 'n', 'rm')
NOW = [0.0]             # 当前帧的场景内时刻（render_frame 写入），给"静止时的余韵"用
def breath(period=2.4, t0=0.0):
    """0~1 的慢呼吸（正弦），用于已经到位、正被讲到的元素；不要用在没讲到的东西上"""
    return 0.5 - 0.5 * math.cos(2 * math.pi * max(0.0, NOW[0] - t0) / period)
def marker(f, x, y, col, a=1.0, r=9):
    """标记点（当前值、高点）：外圈光晕慢呼吸，停住的图上也看得出“这里是现在”"""
    if a <= 0.01: return
    L = AA(f, (x - 40, y - 40, x + 40, y + 40)); b = breath(2.4)
    L.circle(x, y, r * (1.9 + 0.7 * b), col, (0.30 - 0.14 * b) * a); L.circle(x, y, r, col, a); L.circle(x, y, r * 0.45, (255, 255, 255), a)
    L.done()
def callout(f, x, y, lines, col, a=1.0, side='up', w=None, align='c', dy=90):
    """从点 (x,y) 拉引线 + 文字框；align='r' 文字框放在点的左侧，'l' 放右侧"""
    if a <= 0.01: return
    size = [34, 24]
    tw = max(f.tw(s, size[min(i, 1)], 'b' if i == 0 else 'r') for i, s in enumerate(lines)) + 36
    w = w or tw; h = 30 + 44 * len(lines) - 6
    dy = -dy if side == 'up' else dy
    by = y + dy - (h if side == 'up' else 0)
    bx = x - w / 2 if align == 'c' else (x - w + 30 if align == 'r' else x - 30)
    bx = clamp(bx, 140, 1780 - w)
    f.line([(x, y), (x, y + dy * 0.7)], col, 2, a)
    f.rect((bx, by, bx + w, by + h), (12, 20, 40), 0.92 * a, r=12, outline=col, ow=2, oa=a)
    for i, s in enumerate(lines):
        f.text((bx + 18, by + 16 + i * 44), s, size[min(i, 1)], col if i == 0 else TXT, a, 'b' if i == 0 else 'r')
def donut(f, cx, cy, r, items, p=1.0, a=1.0, w=34, hl=None, hla=0.0):
    """环形图：items=[(值, 颜色)]，p=扫出进度；hl=要放大的项序号，hla=放大程度"""
    if a <= 0.01: return
    tot = sum(v for v, _ in items); ang = -90
    L = AA(f, (cx - r - 50, cy - r - 50, cx + r + 50, cy + r + 50))
    L.arc(cx, cy, r, 0, 360, (36, 50, 82), w, a * 0.8)
    for i, (v, c) in enumerate(items):
        sw = 360 * v / tot * p
        ww = w + (14 * hla if i == hl else 0)
        dim = 1 - 0.5 * hla if (hl is not None and i != hl) else 1
        L.arc(cx, cy, r, ang + 0.8, ang + sw - 0.8, c, ww, a * dim); ang += sw
    L.done()
def hbar(f, x, y, h, length, col, a=1.0, label=None, size=28, lcol=TXT, r=6):
    """横条 + 末端数值"""
    f.rect((x, y, x + max(length, 0), y + h), col, a, r=r)
    if label: f.text((x + max(length, 0) + 12, y + h / 2), label, size, lcol, a, 'n', 'lm')
def headline(f, t, num, title):
    """场景大标题：编号 + 标题 + 金色下划线生长"""
    p = pg(t, 0.15, 0.6); x = 130 - 40 * (1 - p)
    f.text((x, 182), num, 56, GOLD, p, 'n', 'lm')
    f.text((x + 92, 182), title, 46, TXT, p, 'b', 'lm')
    if f.rec is not None: f.cover = max(f.cover, len(f.rec))     # 章节标题不参与"讲到谁亮谁"
    f.rect((130, 222, 130 + 260 * pg(t, 0.4, 0.8), 226), GOLD, 0.9 * p)
def overlay(f, q, alpha=0.85):
    """压暗全幅内容区，用于金句/转场卡"""
    if q > 0: f.rect((0, 120, W, 920), (6, 10, 22), alpha * q)
    if q > 0.3 and f.rec is not None: f.cover = len(f.rec)

def glow(f, box, k, col=None, r=10, pad=28, grow=0.0, edge=False):
    """让一块已经画好的元素本身亮起来（57号补丁二十一）：box 内像素提亮 + 外面一圈柔光。不加框、不贴标签。
    k = 强度 0~1；col 给了就在 box 内薄铺一层这个色（box 底下是深色背景时也看得出亮）；
    grow = 这块放大的比例（0.05 = 放大 5%），edge = 沿这块边缘描一圈细亮边。在这块元素画完之后调用。
    样子见 docs/强调_用户认可样式.png：整段亮起、略放大、细亮边，其余压暗。"""
    if k <= 0.01: return
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    if X1 - X0 < 2 or Y1 - Y0 < 2 or x1 <= x0 or y1 <= y0: return
    reg = f.im.crop((X0, Y0, X1, Y1)); a = np.asarray(reg, np.float32)
    m = Image.new('L', reg.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((x0 - X0, y0 - Y0, x1 - X0 - 1, y1 - Y0 - 1), max(0, min(r, (y1 - y0) // 2, (x1 - x0) // 2)), fill=255)
    mi = np.asarray(m, np.float32)[..., None] / 255
    lum = a.mean(axis=2, keepdims=True) / 255         # 按亮度加权：色块变亮，压在上面的深色字不变灰
    w = np.clip((lum - 0.2) / 0.3, 0, 1) * lum       # 深色底几乎不动，免得提出一个灰框
    lit = a * (1 + 0.12 * k * w); lit = lit + (255 - np.minimum(lit, 255)) * 0.16 * k * w
    if col: lit = lit + np.array(col, np.float32) * 0.10 * k
    elif (lum * mi).sum() / max(1, mi.sum()) < 0.3:     # 深色底上的字（不在色块上）：字本身转成金色，金色 = 重点
        g = np.clip((lum - 0.35) / 0.4, 0, 1); lit = lit + (np.array(GOLD, np.float32) - lit) * 0.75 * k * g
    a2 = a * (1 - mi) + lit * mi
    src = a2 * mi * np.clip((lum - 0.25) / 0.3, 0, 1)   # 柔光只从亮的像素（色块、字）发出，深色底不发灰
    halo = np.asarray(Image.fromarray(np.clip(src, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(12)), np.float32)
    a2 = a2 + halo * 0.6 * k * (1 - 0.7 * mi)
    f.im.paste(Image.fromarray(np.clip(a2, 0, 255).astype(np.uint8)), (X0, Y0))
    if grow > 0 or edge:
        s_ = 1 + grow * k; cw, ch = x1 - x0, y1 - y0; nw, nh = max(1, round(cw * s_)), max(1, round(ch * s_))
        bx = (x0 - (nw - cw) // 2, y0 - (nh - ch) // 2); rr = max(0, min(r, nh // 2, nw // 2))
        if nw != cw or nh != ch:
            mk = Image.new('L', (nw, nh), 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, nw - 1, nh - 1), rr, fill=255)
            f.im.paste(f.im.crop((x0, y0, x1, y1)).resize((nw, nh), Image.LANCZOS), bx, mk)
        if edge: f.rect((bx[0], bx[1], bx[0] + nw - 1, bx[1] + nh - 1), None, 0, r=rr, outline=(255, 244, 214), ow=2, oa=0.85 * k)

# ---------- 背景 ----------
_BG = None
def background():
    global _BG
    if _BG is None:
        y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
        top = np.array([9, 14, 30]); bot = np.array([13, 22, 44])
        img = top + (bot - top) * y[..., None]
        g1 = np.exp(-(((x - 0.86) / 0.32) ** 2 + ((y - 0.08) / 0.35) ** 2))[..., None] * np.array([20, 60, 90])
        g2 = np.exp(-(((x - 0.08) / 0.30) ** 2 + ((y - 0.95) / 0.30) ** 2))[..., None] * np.array([60, 40, 10])
        img = np.clip(img + g1 * 0.55 + g2 * 0.45, 0, 255).astype(np.uint8)
        im = Image.fromarray(img, 'RGB'); d = ImageDraw.Draw(im, 'RGBA')
        for gx in range(0, W, 48):
            for gy in range(0, H, 48): d.point((gx, gy), fill=(120, 140, 190, 40))
        _BG = im
    return _BG.copy()

# ---------- 工程配置 ----------
C = dict(root=None, name='', code='', source='', voice='zh-CN-YunyangNeural', rate='+6%',
         lead=0.7, gap=0.35, tail=1.0, scenes=[], out_name='final.mp4', music=0.075, sub_size=44, spotlight=True, spot_dim=0.7,
         crf=18, preset='medium', x264_threads=3,      # 编码参数：要更快出片可在 setup 里传 preset='veryfast'
         edge_fade=0.3)                                # 每章首尾淡入淡出黑场的秒数；0 = 不淡，章节自己做进出场（如 fxplus.transition）
def setup(**kw):
    C.update(kw)
    if not C['root']: raise ValueError('M.setup 要传 root=工程目录（骨架里是 ROOT）')
    for d in ('audio', 'chunks', 'output'): os.makedirs(os.path.join(C['root'], d), exist_ok=True)
def P(*a): return os.path.join(C['root'], *a)

# ---------- 片头条 / 字幕 ----------
def chrome(f, si, gt, total, offs):
    f.rect((60, 48, 66, 92), GOLD)
    f.text((84, 70), C['name'], 34, TXT, 1, 'b', 'lm')
    x = 84 + f.tw(C['name'], 34, 'b') + 14
    f.text((x, 72), C['code'], 28, SUB, 1, 'n', 'lm')
    x += f.tw(C['code'], 28, 'n') + 24
    f.chip((x, 52), C['scenes'][si][0], GOLD, 1, 22)
    f.text((1860, 70), C['source'], 22, DIM, 1, 'r', 'rm')
    f.line([(60, 116), (1860, 116)], GRID, 1, 0.6)
    progress_bar(f, si, gt, total, offs)

def progress_bar(f, si, gt, total, offs):
    """底部章节进度条：每章一格，格里写章节名；当前章金色高亮，讲过的章偏亮，没讲的偏暗"""
    y0, y1 = 1034, 1080; bar = 1074
    ends = list(offs[1:]) + [total]
    for k, (o, e) in enumerate(zip(offs, ends)):
        x0, x1 = W * o / total + 2, W * e / total - 2
        cur, done = k == si, k < si
        if cur: f.rect((x0, y0, x1, bar), GOLD, 0.16)
        f.rect((x0, bar, x1, y1), (28, 38, 64))
        fill = x1 if done else (x0 + (x1 - x0) * clamp((gt - o) / (e - o)) if cur else x0)
        f.rect((x0, bar, fill, y1), GOLD if cur else (150, 116, 50))
        lab = C['scenes'][k][0]
        col, kind = (GOLD, 'b') if cur else ((SUB, 'r') if done else (DIM, 'r'))
        sz = 20
        while sz > 14 and f.tw(lab, sz, kind) > x1 - x0 - 10: sz -= 1
        if f.tw(lab, sz, kind) <= x1 - x0 - 6 or cur:
            f.text(((x0 + x1) / 2, (y0 + bar) / 2 + 1), lab, sz, col, 1, kind, 'mm')

def subtitle(f, t, subs):
    for s0, e, txt in subs:
        if s0 <= t < e:
            a = clamp((t - s0) / 0.12) * clamp((e - t) / 0.08); sz = C['sub_size']
            w = f.tw(txt, sz, 'b') + 64
            f.rect((W / 2 - w / 2, 938, W / 2 + w / 2, 1012), (0, 0, 0), 0.55 * a, r=12)
            f.text((W / 2, 975), txt, sz, (255, 255, 255), a, 'b', 'mm', stroke=2)
            break

def split_sub(s):
    """字幕切句：标点处切，单条 12~24 字；数字串不拆"""
    parts = [p for p in re.split(r'(?<=[，。；：？！])', s) if p]
    o, cur = [], ''
    for p in parts:
        if cur and len(cur) + len(p) > 24: o.append(cur); cur = p
        else: cur += p
        if len(cur) >= 12: o.append(cur); cur = ''
    if cur: o.append(cur)
    return [re.sub(r'[，。；：]$', '', c) for c in o]

# ---------- 音频 ----------
def decode(path):
    raw = subprocess.run(sysenv.ffmpeg('-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'),
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768

def _apath(si, li): return P('audio', f's{si:02d}_{li:02d}.mp3')
_TXT_LOG = 'audio_text.json'

async def _tts():
    import edge_tts
    sem = asyncio.Semaphore(6)
    old = {}
    if os.path.exists(P('audio', _TXT_LOG)):
        with open(P('audio', _TXT_LOG), encoding='utf-8') as fp: old = json.load(fp)
    new = {}
    async def one(si, li, s):
        p = _apath(si, li); k = os.path.basename(p); new[k] = s
        if os.path.exists(p) and os.path.getsize(p) > 1000 and old.get(k) == s: return   # 文本没变才复用
        async with sem:
            for i in range(5):
                try: await edge_tts.Communicate(s, C['voice'], rate=C['rate']).save(p); return
                except Exception as e: print('retry', k, e); await asyncio.sleep(2 + 2 * i)
            raise RuntimeError('TTS 失败: ' + k)
    await asyncio.gather(*[one(si, li, s) for si, (_, ls, _) in enumerate(C['scenes']) for li, s in enumerate(ls)])
    with open(P('audio', _TXT_LOG), 'w', encoding='utf-8') as fp: json.dump(new, fp, ensure_ascii=False, indent=0)

def build_timeline():
    tl = []; off = 0.0; n = len(C['scenes'])
    for si, (_, lines, _) in enumerate(C['scenes']):
        t = C['lead']; beats = []; subs = []; durs = []
        for li, s in enumerate(lines):
            d = len(decode(_apath(si, li))) / SR
            beats.append(t); durs.append(d)
            ch = split_sub(s); tot = sum(len(c) for c in ch); ct = t
            for c in ch:
                cd = d * len(c) / tot; subs.append([ct, ct + cd, c]); ct += cd
            t += d + C['gap']
        T = t - C['gap'] + C['tail'] + (2.0 if si == n - 1 else 0)
        nf = int(round(T * FPS)); T = nf / FPS
        for i in range(len(subs) - 1): subs[i][1] = max(subs[i][1], min(subs[i + 1][0], subs[i][1] + C['gap']))
        tl.append(dict(beats=beats, durs=durs, subs=subs, T=T, frames=nf, off=off)); off += T
    with open(P('timeline.json'), 'w', encoding='utf-8') as fp: json.dump(dict(scenes=tl, total=off), fp, ensure_ascii=False, indent=1)
    return tl, off

def load_tl():
    if not os.path.exists(P('timeline.json')): sys.exit('还没有 timeline.json：先跑 python video.py tts')
    with open(P('timeline.json'), encoding='utf-8') as fp: j = json.load(fp)
    return j['scenes'], j['total']

def music(n):
    """自生成的柔和铺底和弦（无版权问题）"""
    t = np.arange(n) / SR
    chords = [[110, 164.81, 220, 261.63, 329.63], [87.31, 130.81, 174.61, 220, 261.63],
              [130.81, 196, 261.63, 329.63, 392], [98, 146.83, 196, 246.94, 293.66]]
    L = 8.0; o = np.zeros(n, np.float32); k = 0
    while k * L < n / SR + L:
        st = k * L - 1.5; idx = (t >= st) & (t < st + L + 3); tt = t[idx] - st
        env = np.clip(tt / 2.0, 0, 1) * np.clip((L + 3 - tt) / 2.0, 0, 1)
        sig = np.zeros(idx.sum(), np.float32)
        for j, fr in enumerate(chords[k % 4]):
            sig += (np.sin(2 * np.pi * fr * tt) + 0.6 * np.sin(2 * np.pi * (fr * 1.003) * tt + j) + 0.15 * np.sin(4 * np.pi * fr * tt)) / (1 + j * 0.35)
        o[idx] += sig * env; k += 1
    o *= (1 + 0.15 * np.sin(2 * np.pi * 0.11 * t))
    return o / (np.abs(o).max() + 1e-9)

def mix_audio(tl, total):
    n = int(round(total * SR)) + SR; voice = np.zeros(n, np.float32)
    for si, sc in enumerate(tl):
        for li, b in enumerate(sc['beats']):
            x = decode(_apath(si, li)); st = int((sc['off'] + b) * SR); voice[st:st + len(x)] += x[:n - st]
    voice *= 0.92 / (np.abs(voice).max() + 1e-9)
    bg = music(n) * C['music']
    rng = np.random.default_rng(1)
    for sc in tl[1:]:                                   # 转场 whoosh
        st = int(sc['off'] * SR) - int(0.25 * SR); m = int(0.6 * SR)
        nz = np.convolve(rng.standard_normal(m).astype(np.float32), np.ones(24) / 24, 'same')
        if st > 0: bg[st:st + m] += nz * np.sin(np.linspace(0, np.pi, m)) ** 2 * 0.18
    envv = np.convolve(np.abs(voice), np.ones(SR // 5) / (SR // 5), 'same')
    mix = voice + bg * (1 - 0.45 * np.clip(envv / 0.05, 0, 1))      # 人声时压低背景
    fo = int(2.5 * SR); mix[-fo:] *= np.linspace(1, 0, fo)
    p = P('output', 'mix.wav')
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    return p

# ---------- 子节拍 ----------
def _say_w(ch):
    """估一个字念多久（相对单位）：汉字 / 数字 1，% 念"百分之"算 3，标点是停顿"""
    if ch in '，、；：': return 1.6
    if ch in '。？！': return 2.2
    if ch == '%': return 3.0
    if ch in '“”"（）() ': return 0.2
    return 1.0
class Beats(list):
    """B[i] = 第 i 句开口时刻；B.S[i][k] = 第 i 句第 k 个字幕子句开口时刻（逗号处切的那一段）；
    B.at(i, '6.5%') = 第 i 句念到"6.5%"的时刻（按字数估，误差约 0.3 秒）。
    长句别让整句只有开口那 0.7 秒在动：句中的第二、第三个意思，挂到它被念到的那一刻。"""
    S = (); D = (); L = ()
    def at(self, i, phrase, k=0):
        """第 i 句里第 k+1 次出现 phrase 的开口时刻；找不到就报错（旁白改了，分镜要跟着改）"""
        s = self.L[i]; pos = -1
        for _ in range(k + 1):
            pos = s.find(phrase, pos + 1)
            if pos < 0: raise ValueError(f'第 {i + 1} 句里找不到「{phrase}」：{s}')
        w = [_say_w(c) for c in s]
        return self[i] + self.D[i] * sum(w[:pos]) / sum(w)
def beats_of(sc, si=None):
    if '_B' not in sc:
        b = Beats(sc['beats']); ends = list(sc['beats'][1:]) + [1e9]
        b.S = [[s0 for s0, _, _ in sc['subs'] if b0 - 1e-6 <= s0 < e - 1e-6] or [b0] for b0, e in zip(b, ends)]
        b.D = sc.get('durs') or [e - b0 for b0, e in zip(b, ends)]
        if si is not None: b.L = list(C['scenes'][si][1])
        sc['_B'] = b
    return sc['_B']

# ---------- 讲到谁亮谁 ----------
# 字幕切到下一个子句时，如果这句念到的数字已经在画面上（之前就画好了），它所在的那一块整体提亮、带柔光并慢呼吸，
# 直到这条字幕念完。新出现的元素不加（它自己的出场动画就是强调）。观众的眼睛跟着声音走，长句也不会整段僵住。
_NUM = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])')
def _spoken_nums(s):
    o = []
    for m in _NUM.finditer(s):
        n = m.group(1); tail = s[m.end():m.end() + 1]
        if re.fullmatch(r'(19|20)\d\d', n) or tail in ('月', '日', '号', '年'): continue
        o.append(n)
    return o
def _cjk(s): return sum(1 for ch in s if '一' <= ch <= '鿿')
def _num_hit(txt, nums):
    if _cjk(txt) > 4: return False                       # 只认"数字本身"的元素，不认带数字的长说明
    for e in _NUM.findall(txt):
        if len(e) > 1 and e[0] == '0' and '.' not in e: continue   # 章节编号 01 02
        ev = float(e)
        for n in nums:
            c = float(n); dc = len(n.split('.')[1]) if '.' in n else 0
            if ev == c or (dc >= 1 and round(ev, dc) == c) or (dc == 0 and c >= 10 and abs(ev - c) <= 0.5): return True
    return False
def _lab_hit(txt, said):
    """短标签（4~8 个汉字、不含数字）被原样念到，例如“学生文具”；三个字以下太容易撞到别处的同名标签"""
    s = txt.strip()
    return 4 <= _cjk(s) <= 8 and _cjk(s) == len(s) and s in said
def _cands(rec, cover, said):
    """画面上（未被压暗盖住、已到位）的、被念到的字：先数字、后标签，各自按字号从大到小"""
    nums = _spoken_nums(said)
    ok = [(s, box, size) for i, (s, box, a, size) in enumerate(rec) if i >= cover and a > 0.9 and size >= 24]
    n = sorted([x for x in ok if nums and _num_hit(x[0], nums)], key=lambda x: -x[2])
    l = sorted([x for x in ok if _lab_hit(x[0], said)], key=lambda x: -x[2])
    return n + l
_SPOT = {}
def _spot_keys(si, k, sc):
    """第 k 条字幕要点亮的字（字符串集合）：念到了，且在这条字幕开口前就已经在画面上"""
    key = (si, k)
    if key not in _SPOT:
        s0, _, txt = sc['subs'][k]; keep = []
        if s0 > 0.1:
            f = Frame(Image.new('RGB', (W, H))); f.rec = []; NOW[0] = s0 - 0.05
            C['scenes'][si][2](f, s0 - 0.05, beats_of(sc, si), sc['T'])
            for s, _, _ in _cands(f.rec, f.cover, txt):
                if s not in keep: keep.append(s)
        _SPOT[key] = keep[:2]
    return _SPOT[key]
def relabel(f, blk, k):
    """被讲到的那一段重画成"亮起来"的样子（docs/强调_用户认可样式.png）：底色提亮提饱和、左右各放大约 6 px、
    浅色细描边，段上的字照原色放大加粗写在段上（不另加标签框）。blk = f.blocks 里的一项 (box, 字序号, 颜色)；k 0~1，
    跟着 0.5 秒渐变。先 glow 出光晕，再调它。"""
    if k <= 0.01 or f.rec is None: return
    (x0, y0, x1, y1), j, col = blk
    c = np.array(col, np.float32); g = c.mean(); c = g + (c - g) * (1 + 0.2 * k)           # 提饱和
    c = c * (1 + 0.06 * k)                                                               # 提亮：GOLD → 约 (255,200,50) 暖金，不推成柠檬黄
    c = tuple(int(v) for v in np.clip(c, 0, 255)); gx = 6 * k
    E = (x0 - gx, y0, x1 + gx, y1); rr = int(min(6, (y1 - y0) / 2))
    keep = [(s, tb, a, size, cx) for i, ((s, tb, a, size), cx) in enumerate(zip(f.rec, f.recx or []))
            if i >= j and a > 0.5 and x0 <= (tb[0] + tb[2]) / 2 <= x1 and y0 <= (tb[1] + tb[3]) / 2 <= y1]
    rec, f.rec = f.rec, None                              # 重画的字不再记进 rec
    f.rect(E, c, 1.0, r=rr, outline=(255, 244, 214), ow=2, oa=0.85 * k)
    for s, tb, a, size, (tc, kind) in keep:
        sz = size * (1 + 0.3 * k)
        while sz > size and f.tw(s, sz, 'n' if kind == 'n' else 'b') > (E[2] - E[0]) - 16: sz -= 1   # 放大后别出段
        f.text(((tb[0] + tb[2]) / 2, (tb[1] + tb[3]) / 2), s, sz, tc, a, 'n' if kind == 'n' else 'b', 'mm')
    f.rec = rec
def _home(f, box, i):
    """字所在的那一块：在它之前画的、包住字中心的最小实心色块（色条的一段、柱子）；不在色块上就是字本身"""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2; best = None
    for b, j, _ in f.blocks or []:
        if j > i or not (b[0] <= cx <= b[2] and b[1] <= cy <= b[3]): continue
        ar = (b[2] - b[0]) * (b[3] - b[1])
        if ar <= W * 800 * 0.25 and (best is None or ar < best[0]): best = (ar, b)
    return best[1] if best else (box[0] - 6, box[1] - 4, box[2] + 6, box[3] + 4)
def spotlight(f, si, t, sc):
    subs = sc['subs']
    k = max((i for i, (s0, _, _) in enumerate(subs) if s0 <= t), default=None)
    if k is None: return
    cur = _spot_keys(si, k, sc); prev = _spot_keys(si, k - 1, sc) if k > 0 else []
    boxes = {}
    for i, (s, box, a, size) in enumerate(f.rec):
        if i >= f.cover and a > 0.9 and s not in boxes: boxes[s] = _home(f, box, i)
    lit = []
    for s in set(cur) | set(prev):
        if s not in boxes: continue
        if s in cur:
            j = k                                         # 连续几条字幕都讲它：从第一次点亮算起，不闪
            while j > 0 and s in _spot_keys(si, j - 1, sc): j -= 1
            st = subs[j][0]; env = pg(t, st + 0.1, 0.45) * (out(t, subs[k][1], 0.4) if k == len(subs) - 1 or s not in _spot_keys(si, k + 1, sc) else 1)
        else:
            st = subs[k - 1][0]; env = out(t, subs[k][0], 0.35)
        if env > 0.01: lit.append((boxes[s], st, env))
    if not lit: return
    # 其余内容稍微退向背景，被念到的留亮：观众一眼知道"现在说的是这个"（退向背景而不是盖黑块，没有边缘）
    dim = max(e for _, _, e in lit) * C['spot_dim']
    if dim > 0.01:
        box = (0, 120, W, 920); m = Image.new('L', (W, 800), int(255 * dim)); md = ImageDraw.Draw(m)
        for (x0, y0, x1, y1), _, e in lit: md.rounded_rectangle((x0 - 8, y0 - 128, x1 + 8, y1 - 112), 12, fill=int(255 * dim * (1 - e)))
        f.im.paste(background().crop(box), box, m)
    # 57号补丁二十一：不再在字外面套金色底框（金色条上会变成"更亮的金色小标签"，用户说很 low），
    # 改成字所在的那一块整体提亮 + 柔光，慢呼吸
    for bx, st, env in lit:
        b = 0.5 - 0.5 * math.cos(2 * math.pi * max(0, t - st - 0.55) / 2.4)
        blk = next((x for x in f.blocks or [] if x[0] == bx), None)
        glow(f, bx, env * (0.8 + 0.2 * b))
        if blk: relabel(f, blk, env)

# ---------- 对口型检查：念到的东西，画面上有没有 ----------
# 不渲染，按每条字幕念完前的时刻跑一遍分镜函数，看画面上记下的字。
# freezedetect 量的是整帧像素，字幕一直在换，"只有章标题、旁白已经念了十几秒"量不出来（紫金 R1 结论章 17 秒）。
def _vals(s): return [float(e) for e in _NUM.findall(s) if not (len(e) > 1 and e[0] == '0' and '.' not in e)]
def _shown(n, vals):
    c = float(n); dc = len(n.split('.')[1]) if '.' in n else 0
    return any(v == c or (dc >= 1 and round(v, dc) == c) or (dc == 0 and c >= 10 and abs(v - c) <= 0.5) for v in vals)
_SCHEMA = re.compile(r'(公司|项目|子公司|门店|业务)\s?[A-Z甲乙丙](?![A-Za-z])')
def check_scenes():
    """返回 [(章, 字幕序号, 章内秒, 类别, 说明)]。类别：只有标题 / 数字没上画面 / 空框 / 字太小 / 红绿没图例 / 示意没标 / 滚动前显示0 / 滚动露长小数 / 写死的数（章为 None）"""
    tl, total = load_tl(); out_ = []
    for si, sc in enumerate(tl):
        B = beats_of(sc, si); fn = C['scenes'][si][2]; seen = set()
        for k, (s0, e, txt) in enumerate(sc['subs']):
            tt = max(s0 + 0.1, e - 0.15)
            f = Frame(background()); f.rec = []; f.cards = []; f.fills = set(); NOW[0] = tt
            fn(f, tt, B, sc['T'])
            con = [(s, box) for s, box, a, _ in f.rec[f.cover:] if a > 0.5]
            # 同一章里同一处只报一次（一段字一直在画面上，不逐条字幕重复报）
            for s, _, a, size in f.rec[f.cover:]:
                if a > 0.5 and size < 20 and _cjk(s) >= 6 and ('小', s) not in seen:
                    seen.add(('小', s)); out_.append((si, k, s0, '字太小', f'{size} 号「{s[:30]}」（正文 ≥22、图角口径注 ≥20）'))
            if {'红', '绿'} <= f.fills and not f.legend and '红绿' not in seen:
                seen.add('红绿'); out_.append((si, k, s0, '红绿没图例', '同屏有红色块和绿色块，红绿不是涨跌时加 components.legend 说明红 / 绿各指什么'))
            texts = [s for s, _ in con]
            sch = [s for s in texts if _SCHEMA.search(s)]
            if sch and not any('示意' in s for s in texts) and '示意' not in seen:
                seen.add('示意'); out_.append((si, k, s0, '示意没标', f'「{sch[0][:20]}」像机制示意，不是报表数字的话图角写"示意"'))
            if not con and e - s0 >= 1.2: out_.append((si, k, s0, '只有标题', txt))
            vals = [v for s, _ in con for v in _vals(s)]
            miss = [n for n in _spoken_nums(txt) if not _shown(n, vals)]
            if miss: out_.append((si, k, s0, '数字没上画面', '、'.join(miss) + '｜' + txt))
            for box, a, ri in f.cards:
                if a < 0.5 or ri < f.cover: continue          # 被压暗卡盖住的框不算
                x0, y0, x1, y1 = box
                if not any(x0 <= (b[0] + b[2]) / 2 <= x1 and y0 <= (b[1] + b[3]) / 2 <= y1 for _, b in con):
                    out_.append((si, k, s0, '空框', f'框 {int(x0)},{int(y0)}–{int(x1)},{int(y1)} 里还没有字｜{txt}')); break
    NOW[0] = 0
    return out_ + check_zero() + check_source()

# ---------- 数字滚动前先显示 0 / 滚动中露出长小数（57号补丁二十一） ----------
# 晨光那期出了 9 处：业务卡在前三句一直是"0.00亿"、"最低 0.00 / 现价 0.00"，观众会当成真实数字；另有"0.76058元"。
# 按 ZERO_STEP 秒的网格跑分镜函数（不渲染），同一位置、同一格式的字先是 0、后来变成非 0 的，就是滚动前露了 0。
ZERO_STEP = 0.5
def _zero_scene(si):
    tl, _ = load_tl(); sc = tl[si]; B = beats_of(sc, si); fn = C['scenes'][si][2]; occ = []
    for n in range(int(sc['T'] / ZERO_STEP) + 1):
        t = n * ZERO_STEP; f = Frame(background()); f.rec = []; NOW[0] = t
        fn(f, t, B, sc['T'])
        for s, (x0, y0, x1, y1), a, _ in f.rec[f.cover:]:
            if a < 0.5 or _cjk(s) > 6: continue
            ns = [e for e in _NUM.findall(s) if not (len(e) > 1 and e[0] == '0' and '.' not in e)]
            if ns: occ.append((t, _NUM.sub('#', s), (x0 + x1) / 2, (y0 + y1) / 2, s, ns, x0, x1))
    NOW[0] = 0
    # 同一个元素：格式一样、同一行，中心 / 左端 / 右端之一对得上（滚数时宽度会变）
    same = lambda p, q: p[1] == q[1] and abs(p[3] - q[3]) < 10 and (abs(p[2] - q[2]) < 40 or abs(p[6] - q[6]) < 6 or abs(p[7] - q[7]) < 6)
    isz = lambda o: all(float(e) == 0 for e in o[5])
    zero, longd = {}, {}
    for i, o in enumerate(occ):
        later = [q for q in occ[i + 1:] if q[0] > o[0] and same(o, q)]
        if isz(o):
            # 变成非 0 的那一刻，原位置上的 0 已经不在了（还在的话是两个不同的字，比如坐标轴的 0 和年份）
            nz = next((q for q in later if not isz(q) and not any(z[0] == q[0] and isz(z) and same(o, z) for z in occ)), None)
            if nz: zero.setdefault((o[1], round(o[3] / 16), round(o[2] / 60)), []).append((o[0], o[4], nz))
        if any('.' in e and len(e.split('.')[1]) >= 4 for e in o[5]) and (o[1], round(o[3] / 16)) not in longd:
            fin = later[-1] if later else None
            if fin and fin[4] != o[4]: longd[(o[1], round(o[3] / 16))] = (o[0], o[4], fin)
    li = lambda t: max([i for i, b in enumerate(B) if b <= t + 1e-6] or [0]) + 1
    rows = []
    for v in zero.values():
        if len(v) < 2: continue                          # 只闪一下（滚动起步那一帧）不报，露 0 超过半秒才报
        t0, s, nz = v[0]
        rows.append((si, li(t0) - 1, t0, '滚动前显示0', f'第 {li(t0)} 句起「{s}」露 0 约 {len(v) * ZERO_STEP:.1f} 秒，'
                     f'{nz[0]:.1f} 秒后才是非 0——没念到前先别画（fx.count 从 0 起滚时 t<t0 自动不画），或出现时就是终值'))
    for t0, s, fin in longd.values():
        rows.append((si, li(t0) - 1, t0, '滚动露长小数', f'第 {li(t0)} 句「{s}」，停下来是「{fin[4]}」——fmt 写定小数位，不用 {{:g}}'))
    return rows
def check_zero():
    """各章按 ZERO_STEP 网格查"数字滚动前先显示 0""滚动中露出长小数"（多进程，不渲染）"""
    from multiprocessing import Pool
    tl, _ = load_tl(); mf = getattr(sys.modules.get('__main__'), '__file__', '') or ''
    if os.path.abspath(mf) == os.path.abspath(P('video.py')):      # video.py 直接跑：子进程能重新 import 分镜
        with Pool(min(sysenv.jobs(), len(tl))) as pool: res = pool.map(_zero_scene, range(len(tl)))
    else: res = [_zero_scene(si) for si in range(len(tl))]          # review_pack 用 runpy 读进来的：单进程
    return [r for rs in res for r in rs]

# ---------- video.py 写死的数（57号补丁二十一） ----------
# 晨光那期：瀑布图累计值写成一串 [100, 18.36, 10.94, …]、角注写成"推算：278 − 前三季度 180.1"。值都对，但改 facts 不会跟着变。
_OPS = re.compile(r'\d\s*(?:[−×÷=≈]|\s[-+/]\s)\s*[^\d{}]{0,8}?\d')
def _facts_nums(d, path=''):
    if isinstance(d, bool): return []
    if isinstance(d, (int, float)): return [(float(d), path)]
    if isinstance(d, dict): return [x for k, v in d.items() for x in _facts_nums(v, f'{path}.{k}' if path else str(k))]
    if isinstance(d, list) and len(d) <= 12: return [x for i, v in enumerate(d) for x in _facts_nums(v, f'{path}[{i}]')]
    return []
def _fact_of(txt, fnums):
    """txt 是一个数的写法，按它写出的小数位和 facts 比；找到返回 facts 里的键"""
    v = float(txt); dc = len(txt.split('.')[1]) if '.' in txt else 0
    for fv, k in fnums:
        if fv == v or (dc and round(fv, dc) == v): return k
def check_source(path=None):
    """静态扫 video.py：facts.json 里已有的数写成字面量、一串手写数、手写算式角注（旁白原句和 B.at 触发词不算）"""
    import ast
    path = path or P('video.py')
    try: src = open(path, encoding='utf-8').read(); tree = ast.parse(src)
    except Exception: return []
    try: fnums = _facts_nums(json.load(open(P('facts.json'), encoding='utf-8')))
    except Exception: fnums = []
    skip = set()                                          # 旁白原句、B.at(句, '0.85亿元') 的触发词、文档字符串：本来就要念数，不算写死
    narr = {ln.strip() for sc in C['scenes'] for ln in sc[1]}
    for nd in ast.walk(tree):
        # 旁白里原样有的片段（多半是先放进列表、再传给 B.at 的触发词）也跳过；画面上的标题、角注一般不和旁白逐字相同
        if isinstance(nd, ast.Constant) and isinstance(nd.value, str) and nd.value.strip() and any(nd.value.strip() in x for x in narr): skip.add(id(nd))
        if isinstance(nd, ast.Call) and isinstance(nd.func, ast.Attribute) and nd.func.attr == 'at':
            skip |= {id(x) for x in nd.args}
        if isinstance(nd, (ast.Module, ast.FunctionDef)) and nd.body and isinstance(nd.body[0], ast.Expr) and isinstance(nd.body[0].value, ast.Constant):
            skip.add(id(nd.body[0].value))
    def sig(e):                                           # 像财务数字的写法：两位以上小数、或 ≥10 带小数、或 ≥3 位小数
        dc = len(e.split('.')[1]) if '.' in e else 0
        return dc >= 3 or (dc >= 2 and abs(float(e)) >= 1) or (dc >= 1 and abs(float(e)) >= 10)
    rows = []; seen = set()
    for nd in ast.walk(tree):
        if id(nd) in skip or not hasattr(nd, 'lineno'): continue
        ln = nd.lineno
        if isinstance(nd, (ast.List, ast.Tuple)):
            fl = [ast.get_source_segment(src, x) for x in nd.elts if isinstance(x, ast.Constant) and isinstance(x.value, float)]
            fl = [e for e in fl if e and sig(e)]
            if len(fl) >= 3 and ln not in seen:
                seen.add(ln); rows.append((None, ln, 0, '写死的数', f'video.py 第 {ln} 行一串手写数 [{", ".join(fl[:6])}…]——放进 facts.py 算好，用 V(…) 取'))
        elif isinstance(nd, ast.Constant) and isinstance(nd.value, float) and ln not in seen:
            e = ast.get_source_segment(src, nd) or ''
            k = sig(e) and _fact_of(e, fnums) if re.fullmatch(r'\d+\.\d+', e) else None
            if k: seen.add(ln); rows.append((None, ln, 0, '写死的数', f'video.py 第 {ln} 行 {e} = facts 的 {k}——用 V("{k}")'))
        elif isinstance(nd, ast.Constant) and isinstance(nd.value, str) and ln not in seen:
            s = nd.value
            if _OPS.search(s) and len(_NUM.findall(s)) >= 2:
                seen.add(ln); rows.append((None, ln, 0, '写死的数', f'video.py 第 {ln} 行手写算式「{s[:40]}」——算式里的数用 V(…) 拼'))
                continue
            for e in _NUM.findall(s):
                if re.fullmatch(r'(19|20)\d\d', e) or not (sig(e) or (len(e) >= 3 and '.' not in e)): continue
                k = _fact_of(e, fnums)
                if k: seen.add(ln); rows.append((None, ln, 0, '写死的数', f'video.py 第 {ln} 行「{s[:30]}」里的 {e} = facts 的 {k}——用 V("{k}") 拼')); break
    return sorted(rows, key=lambda r: r[1])
def check_report(rows):
    """把 check_scenes 的结果合并成人读的几行：同一章连续几条字幕的"只有标题"并成一段"""
    L = []; i = 0
    while i < len(rows):
        si, k, s0, kind, d = rows[i]
        if si is None: L.append(f'{kind}：{d}'); i += 1; continue
        if kind == '只有标题':
            j = i
            while j + 1 < len(rows) and rows[j + 1][0] == si and rows[j + 1][3] == '只有标题' and rows[j + 1][1] == rows[j][1] + 1: j += 1
            sub = load_tl()[0][si]['subs']; e = sub[rows[j][1]][1]
            L.append(f'第 {si:02d} 章 {s0:.1f}~{e:.1f} 秒（{e - s0:.1f} 秒）只有章标题：「{d}」…'); i = j + 1; continue
        L.append(f'第 {si:02d} 章 {s0:.1f} 秒 {kind}：{d}'); i += 1
    return L
def cmd_check():
    L = check_report(check_scenes())
    open(P('output', 'check.txt'), 'w', encoding='utf-8').write('\n'.join(L) or '无')
    print(f'对口型检查（念到的数字画面上有没有、除章标题外有没有内容、有没有空框、字太小、红绿没图例、示意没标、滚动前显示 0、写死的数）：{len(L)} 处 → output/check.txt')
    for x in L[:12]: print('  ' + x)
    if len(L) > 12: print(f'  …还有 {len(L) - 12} 处，见 output/check.txt')

# ---------- 静止段（57号）：preview 阶段就按分镜函数抽帧查"3 秒以上不动" ----------
# 判定和 review_pack 的 ffmpeg freezedetect 一致：只量内容区 y 120~920（字幕、进度条在换不算动），
# 相邻两帧平均像素差 < STILL_N 算没动，连续 ≥ STILL_D 秒算一段。区别是不用等成片，而且能说出卡在哪一句、念到哪。
# 57号补丁七：不再设总占比目标（30% 逼着反复补节拍，观众看不出差别）；单段超过 STILL_MAX 秒才必须补，总占比只报数。
# plan_check.py 从这里读 STILL_MAX，文字方案阶段用同一个线查"两个触发词隔太久"。
STILL_STEP, STILL_D, STILL_N, STILL_MAX = 0.5, 3.0, 0.001, 7.0
def _still_scene(si):
    tl, total = load_tl(); sc = tl[si]; offs = [s['off'] for s in tl]
    ts = [k * STILL_STEP for k in range(int(sc['T'] / STILL_STEP) + 1)]
    prev = None; diffs = []
    for t in ts:
        im = render_frame(si, t, sc, total, offs).crop((0, 120, W, 920)).convert('L').resize((480, 200), Image.BILINEAR)
        a = np.asarray(im, np.float32) / 255
        if prev is not None: diffs.append(float(np.abs(a - prev).mean()))
        prev = a
    segs = []; k = 0
    while k < len(diffs):
        if diffs[k] < STILL_N:
            j = k
            while j + 1 < len(diffs) and diffs[j + 1] < STILL_N: j += 1
            s0, s1 = ts[k], ts[j + 1]
            if s1 - s0 >= STILL_D: segs.append((s0, s1))
            k = j + 1
        else: k += 1
    return si, segs
def _still_where(si, s0, s1):
    """静止段落在哪一句、这几秒在念什么——改法：把这段话里的数 / 词挂到 B.at(句, '…')"""
    tl, _ = load_tl(); sc = tl[si]; B = beats_of(sc, si)
    li = max(i for i, b in enumerate(B) if b <= s0 + 1e-6) if B[0] <= s0 + 1e-6 else 0
    said = ''.join(txt for a, b, txt in sc['subs'] if b > s0 and a < s1)
    return li, said
def cmd_still():
    from multiprocessing import Pool
    tl, total = load_tl()
    with Pool(min(sysenv.jobs(), len(tl))) as pool: res = sorted(pool.map(_still_scene, range(len(tl))))
    L = []; tot = 0.0; per = []
    for si, segs in res:
        st = sum(b - a for a, b in segs); tot += st; per.append(f'{si:02d}:{st / tl[si]["T"] * 100:.0f}%')
        for a, b in segs:
            li, said = _still_where(si, a, b)
            L.append(f'第 {si:02d} 章 {a:.1f}~{b:.1f} 秒（{b - a:.1f} 秒）不动，第 {li + 1} 句在念：「{said[:60]}」')
    pct = tot / total * 100
    dur = lambda s: float(re.search(r'（([\d.]+) 秒）', s).group(1))
    must = sorted([x for x in L if dur(x) > STILL_MAX], key=lambda s: -dur(s))
    head = (f'静止段：超过 {STILL_MAX:.0f} 秒不动的 {len(must)} 段（必须补）；'
            f'参考：≥{STILL_D:.0f} 秒的共 {len(L)} 段，占全片 {pct:.0f}%（只报数，不设目标；各章 {" ".join(per)}）')
    tip = (f'改法：只补超过 {STILL_MAX:.0f} 秒的段——把这几秒念到的数 / 词挂一个变化到 B.at(句, "…")：亮起、滚数（fx.count）、飞进算式（fx.fly）、拆开（fx.split）。'
           '3~7 秒的停顿是让观众看图，不用补。')
    open(P('output', 'still.txt'), 'w', encoding='utf-8').write(
        '\n'.join([head, tip, '', f'## 必须补（>{STILL_MAX:.0f} 秒）'] + (must or ['无']) + ['', '## 全部 ≥3 秒的段（参考）'] + L))
    print(head + ' → output/still.txt')
    if must:
        print('  ' + tip)
        for x in must[:12]: print('  ' + x)

# ---------- 单帧抽查（57号补丁四）：看动效中间态，不用全片渲染 ----------
def cmd_frames(specs):
    """python video.py frames 2:5:1.5 4:6 …  每项 = 章:句[:句内偏移秒]（句从 1 数，和 still.txt、审片包一致；偏移默认 1.0）。
    两列拼图 → output/frames.png。preview 每章只抽 3 帧，飞入 / 拆条 / 滚数的中途状态看不到，压没压住别的东西用这个查。"""
    tl, total = load_tl(); offs = [s['off'] for s in tl]; ims = []; labs = []
    for sp in specs:
        p = sp.split(':'); si, li = int(p[0]), int(p[1]) - 1; dt = float(p[2]) if len(p) > 2 else 1.0
        B = beats_of(tl[si], si)
        if not 0 <= li < len(B): raise ValueError(f'{sp}：第 {si:02d} 章只有 {len(B)} 句')
        t = min(B[li] + dt, tl[si]['T'] - 0.05)
        ims.append(render_frame(si, t, tl[si], total, offs)); labs.append(f'{si:02d}章 第{li + 1}句 +{dt:g}s（章内 {t:.1f}s）')
    if not ims: print('用法：python video.py frames 章:句[:偏移秒] …'); return
    tw_, th_ = 960, 540; rows = (len(ims) + 1) // 2
    sheet = Image.new('RGB', (2 * tw_, rows * th_)); d = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(zip(ims, labs)):
        x, y = (i % 2) * tw_, (i // 2) * th_
        sheet.paste(im.resize((tw_, th_), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + 420, y + 34), fill=(0, 0, 0)); d.text((x + 8, y + 6), lab, font=font(20, 'b'), fill=GOLD)
    sheet.save(P('output', 'frames.png')); print('frames', P('output', 'frames.png'), '；'.join(labs))

# ---------- 渲染 ----------
def render_frame(si, t, sc, total, offs):
    im = background(); f = Frame(im); NOW[0] = t
    f.rec = []; f.blocks = []; f.recx = []
    C['scenes'][si][2](f, t, beats_of(sc, si), sc['T'])
    if C['spotlight']: spotlight(f, si, t, sc)
    NOW[0] = t; f.rec = None; f.blocks = None; f.recx = None
    chrome(f, si, sc['off'] + t, total, offs)
    subtitle(f, t, sc['subs'])
    ef = C['edge_fade']; fade = min(clamp(t / ef), clamp((sc['T'] - t) / ef)) if ef > 0 else 1
    if fade < 1: im = Image.blend(Image.new('RGB', (W, H), (0, 0, 0)), im, eio(fade))
    return im

def render_chunk(job):
    si, a, b, path, resume = job
    if resume and os.path.exists(path) and os.path.getsize(path) > 10000: return path
    tl, total = load_tl(); sc = tl[si]; offs = [s['off'] for s in tl]
    tmp = path[:-4] + '.part.mp4'          # 先写临时文件，渲完再改名：中途打断不会留下"看着完整"的坏块给 resume 跳过
    cmd = sysenv.ffmpeg('-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                        '-c:v', 'libx264', '-threads', str(C['x264_threads']), '-preset', C['preset'], '-crf', str(C['crf']),
                        '-pix_fmt', 'yuv420p', '-r', str(FPS), tmp)
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fi in range(a, b): pr.stdin.write(render_frame(si, fi / FPS, sc, total, offs).tobytes())
    finally:
        pr.stdin.close(); pr.wait()
    if pr.returncode: raise RuntimeError('ffmpeg 失败: ' + path)
    os.replace(tmp, path)
    return path

# ---------- 命令 ----------
def cmd_tts():
    asyncio.run(_tts()); tl, total = build_timeline()
    print('总长 %.1fs（%d:%02d）' % (total, total // 60, total % 60), [round(s['T'], 1) for s in tl])

def cmd_preview(only=None):
    """每个场景取 3 个时刻（开头 1/3、2/3、末尾）拼成验收图"""
    tl, total = load_tl(); offs = [s['off'] for s in tl]; rows = []
    for si, sc in enumerate(tl):
        if only is not None and si not in only: continue
        ts = [sc['T'] * 0.35, sc['T'] * 0.7, sc['T'] - 0.6]
        ims = [render_frame(si, t, sc, total, offs) for t in ts]
        for i, im in enumerate(ims): im.save(P('output', f'pv_{si:02d}_{i}.png'))
        rows.append(ims)
    tw_, th_ = 640, 360
    sheet = Image.new('RGB', (3 * tw_, len(rows) * th_))
    for r, ims in enumerate(rows):
        for c, im in enumerate(ims): sheet.paste(im.resize((tw_, th_), Image.LANCZOS), (c * tw_, r * th_))
    sheet.save(P('output', 'preview_sheet.png')); print('preview', P('output', 'preview_sheet.png'))
    cmd_check()
    if only is None: cmd_still()          # 57号：静止段在 preview 就报，不等成片

def cmd_render(resume=False, only=None, jobs=None):
    from multiprocessing import Pool
    tl, total = load_tl(); jobs_ = []
    for si, sc in enumerate(tl):
        for a in range(0, sc['frames'], 240):
            p = P('chunks', f'c{si:02d}_{a:05d}.mp4')
            skip_ok = (resume or only is not None) and (only is None or si not in only)   # --only 只重渲点名场景
            jobs_.append((si, a, min(sc['frames'], a + 240), p, skip_ok))
    with Pool(jobs or sysenv.jobs()) as pool:
        for i, p in enumerate(pool.imap(render_chunk, jobs_)):   # 每 10 片报一次进度，不逐片刷屏
            if (i + 1) % 10 == 0 or i + 1 == len(jobs_): print(f'{i + 1}/{len(jobs_)}', os.path.basename(p), flush=True)
    keep = {j[3] for j in jobs_}
    for fn in os.listdir(P('chunks')):                     # 清掉时间轴变动后多余的旧块
        fp = P('chunks', fn)
        if fn.endswith('.mp4') and fp not in keep: os.remove(fp)        # 也清掉打断留下的 .part.mp4
    with open(P('chunks', 'list.txt'), 'w', encoding='utf-8') as fl:
        for j in jobs_: fl.write("file '" + j[3].replace("'", "'\\''") + "'\n")   # concat 列表里路径的单引号要转义

def cmd_mux():
    if not os.path.exists(P('chunks', 'list.txt')): sys.exit('还没有渲染好的画面：先跑 python video.py render')
    tl, total = load_tl(); wav = mix_audio(tl, total); o = P('output', C['out_name'])
    subprocess.run(sysenv.ffmpeg('-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', P('chunks', 'list.txt'), '-i', wav,
                    '-c:v', 'copy', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                    '-shortest', '-movflags', '+faststart', o), check=True)
    def ts(x): ms = int(round(x * 1000)); return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'
    k = 1
    with open(o[:-4] + '.srt', 'w', encoding='utf-8') as fs:
        for sc in tl:
            for a, b, txt in sc['subs']:
                fs.write(f"{k}\n{ts(sc['off'] + a)} --> {ts(sc['off'] + b)}\n{txt}\n\n"); k += 1
    print('done', o)

USAGE = """用法：python video.py <命令>
  tts                     逐句配音 + 时间轴
  preview [--only 3,5]    每章 3 帧拼图 + 对口型检查 + 静止段
  check | still           只跑对口型检查 / 静止段
  frames 章:句[:秒] …     单帧抽查拼图
  render [resume] [--only 3,5] [--jobs N]   并行渲染（N 默认 CPU 核数，最多 8；也可设 STOCK_VIDEO_JOBS）
  mux                     混音 + 响度归一 → 成片 + .srt
  all                     tts → render → mux"""

def cli():
    a = sys.argv[1:] or ['all']; c = a[0]
    def opt(k):
        if k not in a: return None
        i = a.index(k)
        if i + 1 >= len(a): sys.exit(f'{k} 后面要跟值\n' + USAGE)
        return a[i + 1]
    only = [int(x) for x in opt('--only').split(',')] if opt('--only') else None
    jobs = int(opt('--jobs')) if opt('--jobs') else None
    if c not in ('tts', 'preview', 'check', 'still', 'frames', 'render', 'mux', 'all'): sys.exit(USAGE)
    if c in ('tts', 'all'): cmd_tts()
    if c == 'preview': cmd_preview(only)
    if c == 'check': cmd_check()
    if c == 'still': cmd_still()
    if c == 'frames': cmd_frames([x for x in a[1:] if ':' in x])
    if c in ('render', 'all'): cmd_render(resume='resume' in a, only=only, jobs=jobs)
    if c in ('mux', 'all'): cmd_mux()
