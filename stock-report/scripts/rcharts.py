# -*- coding: utf-8 -*-
"""rcharts.py —— 报告用的静态图（matplotlib → SVG），画法照 stock-video 的默认画法（方法与口径 §0 §2）。

工程里的 charts.py 每个函数返回一张 fig，函数里只组织数据，画法用这里的：

    from rcharts import *
    def 利润表总览(FX):
        return waterfall([('收入', 100), ('营业成本', -78.1), ...], end='归母净利', focus='所得税', note='每 100 元收入；2025 年报')

视频的"强调"在纸面上的对应：focus= 点名的那一块保持亮色、加细亮边，其余压暗（不画圈、不另贴标签）。
颜色有含义：涨红跌绿（A 股习惯）；金色 = 重点 / 当前值；红绿表示对利润好坏时 legend= 加小图例。
每张图都可以写 note=（图角口径注：时间、口径、"推算""未经审计""示意""非目标价"）。

主题：theme('dark') 暗色，和视频一个样子（默认）；theme('paper') 白底，适合打印。build_report.py 按 --theme 设好再调 charts.py。
"""
import os
import re
import subprocess
from pathlib import Path

import logging
import matplotlib
matplotlib.use('Agg')
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
from rlib import pct_stats, get, label, fmt   # charts.py 里 from rcharts import * 就能用

# ---------- 主题 ----------
_DARK = dict(bg='#0b1124', card='#121e3a', ink='#ecf1fa', sub='#96a6c2', dim='#5c6c8c', grid='#3c4e73',
             gold='#f5b942', red='#ff5252', green='#22c578', blue='#38bdf8', indigo='#6e73f5', purple='#b08cff',
             orange='#f08264', grey='#4e5e80', edge='#fff4d6')
_PAPER = dict(bg='#ffffff', card='#f6f3ec', ink='#1f2430', sub='#5a6275', dim='#9aa1b0', grid='#d9dce3',
              gold='#c98a06', red='#d93636', green='#1f9d5c', blue='#2b7bbf', indigo='#5458d8', purple='#8a63d2',
              orange='#d9673f', grey='#a8afbd', edge='#1f2430')
T = dict(_DARK)
NAME = ['dark']
DIM_ALPHA = 0.28          # 其余压暗到多少（视频补丁二十一：压暗要明显）


def theme(name='dark'):
    T.clear(); T.update(_DARK if name == 'dark' else _PAPER); NAME[0] = name
    _font()
    plt.rcParams.update({
        'figure.facecolor': T['bg'], 'axes.facecolor': T['bg'], 'savefig.facecolor': T['bg'],
        'text.color': T['ink'], 'axes.labelcolor': T['sub'], 'xtick.color': T['sub'], 'ytick.color': T['sub'],
        'axes.edgecolor': T['grid'], 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': False, 'font.size': 11, 'axes.titlesize': 13, 'axes.titleweight': 'bold',
        'axes.titlecolor': T['ink'], 'axes.titlelocation': 'left', 'axes.unicode_minus': False,
        'svg.fonttype': 'path',
    })


_FONT_DONE = [False]


def _font_candidates():
    env = os.environ.get('STOCK_VIDEO_FONT_R')
    if env: yield env.partition('#')[0]
    try:                                       # stock-video 的 sysenv（macOS 苹方 / Windows 雅黑 / Linux 思源）
        import sysenv
        yield sysenv.font_file('r')[0]
        yield sysenv.font_file('b')[0]
    except Exception:
        pass
    try:                                       # 再问 fontconfig 要一个中文字体
        out = subprocess.run(['fc-match', '-f', '%{file}', 'sans-serif:lang=zh-cn'], capture_output=True, text=True, timeout=5)
        if out.stdout: yield out.stdout
        out = subprocess.run(['fc-list', ':lang=zh', 'file'], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            if re.search(r'(?i)noto.*cjk|sourcehan|wqy|pingfang|msyh|hei', line): yield line.split(':')[0]
    except Exception:
        pass


def _font():
    if _FONT_DONE[0]: return
    names = []
    for p in _font_candidates():
        if p and os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
                names.append(font_manager.FontProperties(fname=p).get_name())
            except Exception:
                continue
    names = list(dict.fromkeys(names))
    if not names: raise SystemExit('图表找不到中文字体：设 STOCK_VIDEO_FONT_R="字体路径"，或装 fonts-noto-cjk')
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = names + ['DejaVu Sans']
    _FONT_DONE[0] = True


def C(name):
    """颜色名（gold / red / green / blue …）或直接给 #hex"""
    return T.get(name, name)


# ---------- 小件 ----------
def _fig(w=8.6, h=4.2):
    if not _FONT_DONE[0]: theme(NAME[0])
    return plt.figure(figsize=(w, h))


def _hit(name, focus):
    if focus is None: return True
    fs = focus if isinstance(focus, (list, tuple, set)) else [focus]
    return any(f == name or (isinstance(f, str) and isinstance(name, str) and f in name) for f in fs)


def _a(name, focus):
    return 1.0 if _hit(name, focus) else DIM_ALPHA


def _edge(ax_patch, name, focus):
    if focus is not None and _hit(name, focus):
        ax_patch.set_edgecolor(T['edge']); ax_patch.set_linewidth(1.4)


def _note(fig, note, legend=None):
    """图角口径注（左下）+ 小图例（右下）"""
    if note:
        fig.text(0.01, 0.01, note, ha='left', va='bottom', fontsize=9, color=T['sub'])
    if legend:
        x = 0.99
        for col, lab in reversed(legend):
            t = fig.text(x, 0.01, lab, ha='right', va='bottom', fontsize=9, color=T['sub'])
            fig.canvas.draw(); bb = t.get_window_extent(); w = bb.width / fig.bbox.width
            fig.patches.append(plt.Rectangle((x - w - 0.022, 0.016), 0.016, 0.022, transform=fig.transFigure,
                                             color=C(col), figure=fig))
            x -= w + 0.04


def _title(ax, title, sub=None):
    if title: ax.set_title(title, pad=14 if sub else 8)
    if sub: ax.text(0, 1.01, sub, transform=ax.transAxes, fontsize=10, color=T['sub'], va='bottom')


def _num(v, fmt):
    return fmt.format(v) if isinstance(fmt, str) else fmt(v)


# ---------- 1. 瀑布图（利润表总览：每 100 元收入被哪几刀切走） ----------
def waterfall(steps, end=None, focus=None, note=None, title=None, sub=None, fmt='{:.1f}', legend=True, w=8.6, h=4.4):
    """steps = [('营业收入', 100), ('营业成本', -78.2), ('税金及附加', -1.1), ..., ('少数股东', -3.0)]
    第一项是起点（整根）；之后正数往上加（红 = 对利润好）、负数往下切（绿 = 对利润坏）；end 给最后一根的名字（金色，自动算）。
    focus='所得税' 只亮这一刀。"""
    fig = _fig(w, h); ax = fig.add_axes([0.06, 0.2, 0.92, 0.66])
    labels, bottoms, heights, cols, levels = [], [], [], [], []
    run = 0.0
    for i, (lab, v) in enumerate(steps):
        if i == 0:
            bottoms.append(0); heights.append(v); cols.append(T['blue']); run = v
        else:
            bottoms.append(run if v >= 0 else run + v); heights.append(abs(v))
            cols.append(T['red'] if v >= 0 else T['green']); run += v
        labels.append(lab); levels.append(run)          # levels = 这一步之后的累计，用来画连接虚线
    if end:
        labels.append(end); bottoms.append(0); heights.append(run); cols.append(T['gold']); levels.append(run)
    x = np.arange(len(labels)); top = max(b + hh for b, hh in zip(bottoms, heights))
    for i in range(len(labels)):
        a = _a(labels[i], focus)
        p = ax.bar(x[i], heights[i], bottom=bottoms[i], color=cols[i], alpha=a, width=0.62)[0]
        _edge(p, labels[i], focus)
        val = steps[i][1] if i < len(steps) else run
        s = _num(val, fmt) if i == 0 or i >= len(steps) else ('+' if val >= 0 else '-') + _num(abs(val), fmt)
        ax.text(x[i], bottoms[i] + heights[i] + top * 0.015, s, ha='center', va='bottom', fontsize=10,
                color=T['ink'], alpha=max(a, 0.45), fontweight='bold' if a == 1 and focus else None)
    for i in range(len(labels) - 1):
        ax.plot([x[i] + 0.31, x[i + 1] - 0.31], [levels[i], levels[i]], color=T['dim'], lw=0.8, ls=(0, (2, 2)))
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    for t, lab in zip(ax.get_xticklabels(), labels):
        t.set_alpha(max(_a(lab, focus), 0.45))
    ax.set_ylim(0, top * 1.12); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    _title(ax, title, sub)
    _note(fig, note, [('red', '加回 / 对利润好'), ('green', '切走 / 对利润坏')] if legend else None)
    return fig


# ---------- 2. 资产负债表总览：同一时点两根等高柱 ----------
def bs_two_bars(assets, funding, date, focus=None, note=None, title=None, sub=None, unit='亿元', fmt='{:.0f}',
                side=None, w=8.6, h=5.0):
    """assets = [('货币资金', 300), ('存货', 900), ...]  有什么
    funding = [('经营负债', 500), ('有息负债', 800), ('少数股东', 200), ('股东自己的钱', 500)]  钱是谁的
    同一时点 date（如 '2025-12-31'）；两根总数应相等（不等时图角提示）。side = [文字, ...] 右侧两三张读数卡。"""
    fig = _fig(w, h)
    ax = fig.add_axes([0.04, 0.1, 0.56 if side else 0.92, 0.76])
    pal_a = [T['blue'], T['indigo'], T['purple'], T['orange'], T['gold'], T['grey'], '#7b8bb0', '#5a9bd5']
    pal_f = [T['grey'], T['red'], '#c06070', T['purple'], T['gold'], '#7b8bb0']
    tot_a = sum(v for _, v in assets); tot_f = sum(v for _, v in funding)
    for xi, items, pal, head in ((0, assets, pal_a, '有什么'), (1, funding, pal_f, '钱是谁的')):
        b = 0.0; tot = sum(v for _, v in items)
        for k, (lab, v) in reversed(list(enumerate(items))):        # 列表第一项画在最上面
            if v <= 0: continue
            a = _a(lab, focus)
            p = ax.bar(xi, v, bottom=b, width=0.72, color=pal[k % len(pal)], alpha=a, edgecolor=T['bg'], linewidth=0.8)[0]
            _edge(p, lab, focus)
            if v / max(tot, 1e-9) >= 0.045:
                ax.text(xi, b + v / 2, f'{lab}  {_num(v, fmt)}  ({v / tot * 100:.0f}%)', ha='center', va='center',
                        fontsize=9.5, color='#ffffff' if NAME[0] == 'dark' else T['ink'], alpha=max(a, 0.6))
            b += v
        ax.text(xi, b * 1.015, f'{head}  合计 {_num(tot, fmt)}', ha='center', va='bottom', fontsize=11, color=T['ink'],
                fontweight='bold')
    ax.set_xlim(-0.45, 1.45); ax.set_ylim(0, max(tot_a, tot_f) * 1.1)
    ax.set_xticks([]); ax.set_yticks([]); ax.spines['left'].set_visible(False); ax.spines['bottom'].set_visible(False)
    _title(ax, title or f'{date} 资产负债表（{unit}）', sub)
    if side: _side_cards(fig, side, x0=0.64)
    gap = '' if abs(tot_a - tot_f) <= 0.01 * max(tot_a, 1) else f'  两边差 {abs(tot_a - tot_f):.1f}，核对科目'
    _note(fig, (note or f'同一时点：{date}') + gap)
    return fig


def _side_cards(fig, texts, x0=0.64, w=0.34):
    n = len(texts); hgt = min(0.24, 0.78 / max(n, 1) - 0.03)
    for i, s in enumerate(texts):
        y = 0.86 - (i + 1) * (hgt + 0.03)
        fig.patches.append(plt.Rectangle((x0, y), w, hgt, transform=fig.transFigure, color=T['card'], figure=fig))
        fig.patches.append(plt.Rectangle((x0, y), 0.006, hgt, transform=fig.transFigure, color=T['gold'], figure=fig))
        fig.text(x0 + 0.02, y + hgt - 0.02, _wrap(s, 17), ha='left', va='top', fontsize=10, color=T['ink'], linespacing=1.5)


def _wrap(s, n):
    out, line = [], ''
    for ch in s:
        if ch == '\n': out.append(line); line = ''; continue
        line += ch
        if len(re.sub(r'[\x00-\x7f]', '', line)) + len(re.sub(r'[^\x00-\x7f]', '', line)) * 0.55 >= n:
            out.append(line); line = ''
    if line: out.append(line)
    return '\n'.join(out)


# ---------- 3. 现金桥（现金流量表总览） ----------
def cash_bridge(start, items, end=None, focus=None, note=None, title=None, sub=None, fmt='{:.0f}', w=8.6, h=4.6):
    """start = ('年初现金', 300)
    items = [('经营', '经营净额', 120), ('投资', '资本开支', -80), ('投资', '其他投资', -10), ('筹资', '分红付息', -40), ('筹资', '借还债', 20)]
    上方按 经营 / 投资 / 筹资 分组；end 自动算（名字默认"年末现金"）。"""
    fig = _fig(w, h); ax = fig.add_axes([0.05, 0.2, 0.93, 0.6])
    labels = [start[0]] + [it[1] for it in items] + [end or '年末现金']
    run = start[1]; bars = [(0, start[1], T['blue'])]
    for g, lab, v in items:
        bars.append((run if v >= 0 else run + v, abs(v), T['red'] if v >= 0 else T['green'])); run += v
    bars.append((0, run, T['gold']))
    top = max(b + hh for b, hh, _ in bars)
    vals = [start[1]] + [it[2] for it in items] + [run]
    for i, (b, hh, col) in enumerate(bars):
        a = _a(labels[i], focus)
        p = ax.bar(i, hh, bottom=b, color=col, alpha=a, width=0.62)[0]; _edge(p, labels[i], focus)
        v = vals[i]
        s = _num(v, fmt) if i in (0, len(bars) - 1) else ('+' if v >= 0 else '-') + _num(abs(v), fmt)
        ax.text(i, b + hh + top * 0.015, s, ha='center', va='bottom', fontsize=10, color=T['ink'], alpha=max(a, 0.45))
    # 分组括号
    groups = {}
    for k, (g, _, _) in enumerate(items, start=1): groups.setdefault(g, []).append(k)
    for g, ks in groups.items():
        y = top * 1.12
        ax.plot([ks[0] - 0.3, ks[-1] + 0.3], [y, y], color=T['sub'], lw=1)
        ax.text((ks[0] + ks[-1]) / 2, y * 1.01, g, ha='center', va='bottom', fontsize=10.5, color=T['ink'])
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(min(0, min(b for b, _, _ in bars)), top * 1.25); ax.set_yticks([]); ax.spines['left'].set_visible(False)
    _title(ax, title, sub)
    _note(fig, note, [('red', '流入'), ('green', '流出')])
    return fig


# ---------- 4. 多年柱（可并排多组） ----------
def bars(cats, series, focus=None, note=None, title=None, sub=None, fmt='{:.1f}', colors=None, unit=None,
         zero_line=True, legend=None, w=8.6, h=3.8):
    """cats = ['2021', ..., '2025']；series = {'净利润': [...], '经营现金流': [...]}（一组也行）
    focus = '2025' 或某个序列名：只亮这一年 / 这一组。负数自动画到零线下。"""
    fig = _fig(w, h); ax = fig.add_axes([0.06, 0.16, 0.92, 0.68])
    names = list(series); n = len(names); width = 0.72 / n
    pal = colors or [T['gold'], T['blue'], T['indigo'], T['orange']]
    allv = [v for s in series.values() for v in s if v is not None]
    span = (max(allv + [0]) - min(allv + [0])) or 1
    for j, nm in enumerate(names):
        for i, (c, v) in enumerate(zip(cats, series[nm])):
            if v is None: continue
            hit = focus is None or _hit(c, focus) or _hit(nm, focus)
            a = 1.0 if hit else DIM_ALPHA
            xx = i + (j - (n - 1) / 2) * width
            p = ax.bar(xx, v, width=width * 0.9, color=C(pal[j % len(pal)]), alpha=a)[0]
            if focus is not None and hit: p.set_edgecolor(T['edge']); p.set_linewidth(1.2)
            ax.text(xx, v + (span * 0.02 if v >= 0 else -span * 0.02), _num(v, fmt), ha='center',
                    va='bottom' if v >= 0 else 'top', fontsize=9, color=T['ink'], alpha=max(a, 0.45))
    ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats)
    if zero_line: ax.axhline(0, color=T['grid'], lw=0.8)
    lo = min(allv + [0]); hi = max(allv + [0])
    ax.set_ylim(lo - span * 0.12 if lo < 0 else 0, hi + span * 0.15)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    _title(ax, title, sub or (f'单位：{unit}' if unit else None))
    lg = legend if legend is not None else ([(pal[j % len(pal)], nm) for j, nm in enumerate(names)] if n > 1 else None)
    _note(fig, note, lg)
    return fig


# ---------- 5. 业务构成：收入占比 vs 毛利占比 + 毛利率 ----------
def seg_share(segs, focus=None, note=None, title=None, sub=None, w=8.6, h=None):
    """segs = [('水泥', 收入占比%, 毛利占比%, 毛利率%), ...]  —— "收入大头"和"利润大头"常常不是同一块"""
    h = h or 1.2 + 0.55 * len(segs)
    fig = _fig(w, h); ax = fig.add_axes([0.2, 0.14, 0.62, 0.7])
    y = np.arange(len(segs))[::-1]
    for k, (nm, r, g, gm) in enumerate(segs):
        a = _a(nm, focus)
        p1 = ax.barh(y[k] + 0.18, r, height=0.34, color=T['blue'], alpha=a)[0]
        p2 = ax.barh(y[k] - 0.18, g, height=0.34, color=T['gold'], alpha=a)[0]
        _edge(p1, nm, focus); _edge(p2, nm, focus)
        ax.text(r + 0.8, y[k] + 0.18, f'{r:.0f}%', va='center', fontsize=9, color=T['ink'], alpha=max(a, .45))
        ax.text(g + 0.8 if g >= 0 else 0.8, y[k] - 0.18, f'{g:.0f}%', va='center', fontsize=9, color=T['ink'], alpha=max(a, .45))
        ax.text(1.02, y[k], f'毛利率 {gm:.1f}%' if gm is not None else '', transform=ax.get_yaxis_transform(),
                va='center', fontsize=9.5, color=T['sub'], alpha=max(a, .45))
    ax.set_yticks(y); ax.set_yticklabels([s[0] for s in segs])
    ax.set_xticks([]); ax.spines['bottom'].set_visible(False)
    ax.axvline(0, color=T['grid'], lw=0.8)
    _title(ax, title, sub)
    _note(fig, note, [('blue', '收入占比'), ('gold', '毛利占比')])
    return fig


# ---------- 6. 估值四宫格 ----------
def val_grid(panels, note=None, title=None, w=8.6, h=5.6):
    """panels = [dict(title='PB 近10年', dates=[...], vals=[...], st=pct_stats结果, log=False, unit='倍', na=None), ...] 四个
    每格：低 / 中 / 高三档分位带（20/50/80）+ 序列 + 现值点 + "现值分位 X%"。PE 亏损时 na='亏损，PE 不适用'。"""
    fig = _fig(w, h)
    for k, pnl in enumerate(panels[:4]):
        r, c = divmod(k, 2)
        ax = fig.add_axes([0.07 + c * 0.48, 0.55 - r * 0.44, 0.4, 0.3])
        ax.set_title(pnl['title'], fontsize=11.5)
        if pnl.get('na'):
            ax.text(0.5, 0.5, pnl['na'], ha='center', va='center', transform=ax.transAxes, color=T['sub'], fontsize=11)
            ax.set_xticks([]); ax.set_yticks([]); continue
        v = np.asarray(pnl['vals'], float); x = np.arange(len(v)); st = pnl['st']
        if pnl.get('log'): ax.set_yscale('log')
        ax.axhspan(min(np.nanmin(v), st['p20']) * 0.95, st['p20'], color=T['green'], alpha=0.10)
        ax.axhspan(st['p80'], max(np.nanmax(v), st['p80']) * 1.05, color=T['red'], alpha=0.10)
        for q, ls in (('p20', ':'), ('p50', '--'), ('p80', ':')):
            ax.axhline(st[q], color=T['sub'], lw=0.8, ls=ls)
            ax.text(len(v) * 1.01, st[q], f"{q[1:]}% {st[q]:.2f}", fontsize=8, color=T['sub'], va='center')
        ax.plot(x, v, color=T['blue'], lw=1.1)
        ax.plot([x[-1]], [st['cur']], 'o', color=T['gold'], ms=6, mec=T['edge'], mew=0.8)
        ax.text(0.02, 0.92, f"现值 {st['cur']:.2f}{pnl.get('unit', '倍')} · 分位 {st['pct']:.0f}%", transform=ax.transAxes,
                fontsize=10, color=T['gold'], fontweight='bold', va='top')
        d = pnl.get('dates')
        if d is not None and len(d):
            ax.set_xticks([0, len(v) - 1]); ax.set_xticklabels([str(d[0])[:7], str(d[-1])[:7]], fontsize=8.5)
        else:
            ax.set_xticks([])
        ax.tick_params(axis='y', labelsize=8.5)
        if pnl.get('log'):
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f'{y:g}'))
            ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    if title: fig.text(0.01, 0.97, title, fontsize=13, fontweight='bold', va='top', color=T['ink'])
    _note(fig, note or '分位带：20% / 50% / 80%；绿 = 低于 20% 分位，红 = 高于 80% 分位')
    return fig


# ---------- 7. 股价 + 参考价 ----------
def price_line(dates, px, ref=None, ref_label='只算利润的参考价', marks=None, note=None, title=None, sub=None,
               w=8.6, h=3.6):
    """近一年股价折线；ref = 参考价（虚线，标"非目标价"）；marks = [(下标, '最高 8.20'), ...]"""
    fig = _fig(w, h); ax = fig.add_axes([0.07, 0.16, 0.9, 0.68])
    x = np.arange(len(px)); ax.plot(x, px, color=T['blue'], lw=1.4)
    ax.fill_between(x, px, min(px) * 0.97, color=T['blue'], alpha=0.08)
    ax.plot([x[-1]], [px[-1]], 'o', color=T['gold'], ms=6)
    ax.text(x[-1], px[-1], f'  现价 {px[-1]:.2f}', color=T['gold'], fontsize=10, va='center', fontweight='bold')
    if ref is not None:
        ax.axhline(ref, color=T['gold'], lw=1, ls='--')
        ax.text(0, ref, f'{ref_label} {ref:.2f}（非目标价）', color=T['gold'], fontsize=9.5, va='bottom')
    for i, s in (marks or []):
        ax.plot([i], [px[i]], 'o', color=T['sub'], ms=4)
        ax.annotate(s, (i, px[i]), xytext=(0, 8 if px[i] >= np.median(px) else -14), textcoords='offset points',
                    ha='center', fontsize=9, color=T['sub'])
    if len(dates):
        idx = np.linspace(0, len(dates) - 1, 5).astype(int)
        ax.set_xticks(idx); ax.set_xticklabels([str(dates[i])[:10] for i in idx], fontsize=8.5)
    lo = min(min(px), ref if ref is not None else min(px)); hi = max(max(px), ref if ref is not None else max(px))
    ax.set_ylim(lo * 0.94, hi * 1.06)
    _title(ax, title, sub)
    _note(fig, note)
    return fig


# ---------- 8. 横条（排名 / 构成 / 测试结果） ----------
def hbars(items, focus=None, note=None, title=None, sub=None, fmt='{:.1f}', color='blue', w=8.6, h=None, ref=None,
          ref_label=None):
    """items = [('名字', 值), ...]；负数朝左（绿）。ref = 竖向参考线（如近五年中位 PE）"""
    h = h or 1.0 + 0.42 * len(items)
    fig = _fig(w, h); ax = fig.add_axes([0.22, 0.12, 0.7, 0.74])
    y = np.arange(len(items))[::-1]
    span = max(abs(v) for _, v in items) or 1
    for k, (nm, v) in enumerate(items):
        a = _a(nm, focus)
        col = C(color) if v >= 0 else T['green']
        p = ax.barh(y[k], v, height=0.6, color=col, alpha=a)[0]; _edge(p, nm, focus)
        ax.text(v + (span * 0.015 if v >= 0 else -span * 0.015), y[k], _num(v, fmt), va='center',
                ha='left' if v >= 0 else 'right', fontsize=9.5, color=T['ink'], alpha=max(a, .45))
    if ref is not None:
        ax.axvline(ref, color=T['gold'], ls='--', lw=1)
        if ref_label: ax.text(ref, len(items) - 0.4, ref_label, color=T['gold'], fontsize=9, ha='center')
    ax.set_yticks(y); ax.set_yticklabels([s[0] for s in items])
    for t, (nm, _) in zip(ax.get_yticklabels(), items): t.set_alpha(max(_a(nm, focus), .45))
    ax.set_xticks([]); ax.spines['bottom'].set_visible(False); ax.axvline(0, color=T['grid'], lw=0.8)
    _title(ax, title, sub)
    _note(fig, note)
    return fig


# ---------- 9. 折线（多年比率） ----------
def lines(cats, series, focus=None, note=None, title=None, sub=None, fmt='{:.1f}', unit=None, w=8.6, h=3.6):
    """cats = 年份；series = {'毛利率': [...], ...}。focus = 序列名：只亮这一条"""
    fig = _fig(w, h); ax = fig.add_axes([0.07, 0.16, 0.86, 0.66])
    pal = [T['gold'], T['blue'], T['indigo'], T['orange'], T['purple']]
    for j, (nm, vs) in enumerate(series.items()):
        a = _a(nm, focus); col = pal[j % len(pal)]
        xs = [i for i, v in enumerate(vs) if v is not None]; ys = [v for v in vs if v is not None]
        ax.plot(xs, ys, color=col, lw=2 if a == 1 else 1.2, alpha=a, marker='o', ms=4)
        if ys:
            ax.text(xs[-1] + 0.08, ys[-1], f'{nm} {_num(ys[-1], fmt)}', color=col, alpha=max(a, .5), fontsize=9.5, va='center')
    ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats)
    ax.set_xlim(-0.3, len(cats) - 0.3 + 0.9)
    ax.grid(axis='y', color=T['grid'], lw=0.5, alpha=0.6)
    _title(ax, title, sub or (f'单位：{unit}' if unit else None))
    _note(fig, note)
    return fig


def save(fig, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format='svg', bbox_inches='tight', pad_inches=0.12)
    plt.close(fig)
