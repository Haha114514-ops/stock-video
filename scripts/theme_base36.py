# -*- coding: utf-8 -*-
"""theme_base36 —— 暗色拆解·全局样板间库（SKILL 2026-10-26·37号；43号加结论页组件）
来源：ep01s_slides.py v3（31/32号审计版式重排 + 36号诊断确认的用户满意基准），逐参数固化。
规则（SKILL 37号）：
  1) 暗色拆解所有新期默认 import 本库开工，画面与表达 = ep01s；
  2) 系列本地化默认关闭，用户明说才开，且头注须声明「全局层37号+本地化」；
  3) 硬标尺（gate G5）任何人不可破：标题≥32/结论带 y∈[0.155,0.26]且≥28号/
     图表底边≥0.24/卡片底边≥0.205/内容带 0.205-0.845/禁孤儿浮块/章节条≥13。
  4) 数字变动硬规则（38号）：实变动句状态帧必须由 blk4/panel_row 承载，行高亮不顶替；
  5) 结论页硬规则（42号/43号组件化）：结论页主体必须由 pillar_cards 承载
     （金框大卡+支柱卡），禁 rowlist/KPI 卡当结论页主体。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

import theme as T

T.setup()  # 导入即配置中文字体（样板间开箱即用，调用方无需记得 setup）

# ---- 全局版式常量（ep01s v3 逐参数固化；G5 以此为默认基准） ----
VY, VFS = 0.175, 30            # 结论带（标准带 0.155-0.26）
AX_CB = 0.24                   # 图表 axes 底边（刻度标签区 0.205-0.235）
CB = 0.205                     # 卡片/面板底边下限
TITLE_FS = 34                  # 页标题
CAP_FS = 13.5                  # 章节条字号
HEAD_Y = 0.884                 # 标题中心线
CONTENT_BAND = (0.205, 0.845)  # 内容带（必须填满）

# ---- 色板再输出（与 theme 一致，调用方免双导入） ----
BG, PANEL, BORDER = T.BG, T.PANEL, T.BORDER
TXT, MUT, DIM = T.TXT, T.MUT, T.DIM
RED, GREEN, GOLD, BLUE = T.RED, T.GREEN, T.GOLD, T.BLUE


def setup():
    T.setup()


# ---- 页骨架（ep01s frame_base 参数化：标题/章节/页码作入参） ----
def frame(title, chapter_idx, chapters, page_no, page_total,
          footer_l="数据：公司公告 · 官方口径 · 详见页脚溯源", footer_r_prefix="仅供研究，不构成投资建议"):
    """全局页骨架：章节胶囊条 + 金竖条大标题 + 双角页脚。
    chapters=[章节名,...]，chapter_idx=当前章下标。返回 figure。"""
    f = T.new()
    n = len(chapters)
    w = (0.955 - 0.045 - 0.004 * (n - 1)) / n
    for i, cname in enumerate(chapters):
        x = 0.045 + i * (w + 0.004)
        on = (i == chapter_idx)
        f.add_artist(FancyBboxPatch((x, 0.958), w, 0.028,
                     boxstyle="round,pad=0.001,rounding_size=0.006",
                     transform=f.transFigure,
                     fc="#2A2108" if on else PANEL, ec=GOLD if on else BORDER,
                     lw=1.4 if on else 1.0, zorder=2))
        f.text(x + w / 2, 0.972, cname, color=GOLD if on else DIM, fontsize=CAP_FS,
               ha="center", va="center", fontweight="bold" if on else "normal", zorder=3)
    f.add_artist(Rectangle((0.045, 0.862), 0.008, 0.044, transform=f.transFigure,
                           fc=GOLD, ec=GOLD, zorder=2))
    f.text(0.066, HEAD_Y, title, color=TXT, fontsize=TITLE_FS, va="center",
           fontweight="bold", zorder=3)
    f.text(0.045, 0.032, footer_l, color=DIM, fontsize=13, va="center")
    f.text(0.955, 0.032, "%s · %s/%s" % (footer_r_prefix, page_no, page_total),
           color=DIM, fontsize=13, va="center", ha="right")
    return f


def anchor_pair(f, x, y, w, cards, note="两锚取高 = 更保守的那条线"):
    """双锚卡（49号收编·G21估值三件套，原型=长和ep01s s13a「安全边际两个锚」）：
    cards=[(名称, 行1, 行2, 结果, 颜色, adopted)] 恰2张；adopted=True 金框+「采用」角标，
    False 降饱和+「弃用」角标；底部结论行 note。渐进披露：行文本由调用方按 states 控制。"""
    cw = (w - 0.04) / 2
    for i, (name, l1, l2, result, c, adopted) in enumerate(cards):
        cx = x + i * (cw + 0.04)
        f.add_artist(FancyBboxPatch((cx, y), cw, 0.34,
                     boxstyle="round,pad=0.0015,rounding_size=0.008",
                     transform=f.transFigure,
                     fc="#14100A" if adopted else "#101318",
                     ec=GOLD if adopted else BORDER, lw=2.6 if adopted else 1.2, zorder=3))
        f.text(cx + cw / 2, y + 0.295, name, color=TXT if adopted else MUT, fontsize=19,
               ha="center", va="center", fontweight="bold", zorder=4)
        f.text(cx + cw / 2, y + 0.205, l1, color=TXT if adopted else DIM, fontsize=17.5,
               ha="center", va="center", zorder=4)
        f.text(cx + cw / 2, y + 0.145, l2, color=TXT if adopted else DIM, fontsize=17.5,
               ha="center", va="center", zorder=4)
        f.text(cx + cw / 2, y + 0.055, result, color=c, fontsize=26,
               ha="center", va="center", fontweight="bold", zorder=4)
        tag, tagc = ("采用", GOLD) if adopted else ("弃用", MUT)
        f.add_artist(FancyBboxPatch((cx + 0.012, y + 0.296), 0.085, 0.036,
                     boxstyle="round,pad=0.001,rounding_size=0.005",
                     transform=f.transFigure, fc="#2A2108" if adopted else PANEL,
                     ec=tagc, lw=1.2, zorder=5))
        f.text(cx + 0.012 + 0.0425, y + 0.314, tag, color=tagc, fontsize=13.5,
               ha="center", va="center", fontweight="bold", zorder=6)
    f.text(x + w / 2, y - 0.035, note, color=MUT, fontsize=15.5,
           ha="center", va="center", zorder=4)


def verdict(f, parts):
    """结论带：全局常量 VY/VFS（0.175/30）。禁止改用 theme 默认 0.108/22。"""
    T.verdict(f, parts, y=VY, fs=VFS)


def blk4(f, x, y, w, subject, old, pct, new, up, fs=18, solid=False):
    _need(bool(str(subject).strip()), "blk4 缺科目名（29号：四要素块必须带科目名，禁裸数字）")
    _need(0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1, "blk4 坐标越界 x=%s y=%s w=%s" % (x, y, w))
    """数字变动四要素块（科目名 + 旧 → ↑/↓±% → 新）。"""
    h = 0.095
    f.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0015,rounding_size=0.008",
                 transform=f.transFigure, fc=GOLD if solid else "#10151F",
                 ec=GOLD, lw=1.8, zorder=4))
    arr = "↑" if up else "↓"
    c = "#0D1117" if solid else (RED if up else GREEN)
    f.text(x + 0.014, y + h - 0.028, subject, color="#5A4A10" if solid else MUT,
           fontsize=fs - 3, va="center", zorder=5)
    line = "%s → %s%s → %s" % (old, arr, pct, new)
    fs_eff = max(13.0, fs * (15.0 / len(line))) if len(line) > 15 else fs  # 52号修：长串自适应缩字号防溢出
    f.text(x + w / 2, y + 0.030, line, color=c,
           fontsize=fs_eff, va="center", fontweight="bold", zorder=5)


def rowlist(f, x, y, w, rows, hi=None, rh=0.10, fs=19, mask=False):
    """开放式大字行列表（名称 + 右对齐大数值；hi=高亮行下标，金框+色条）。
    mask=True（49号·G22渐进披露）：未点亮行数值显示「…」，口播提到才填真值；口径/常驻行请单独调用不传 mask。"""
    _need(bool(rows), "rowlist rows 为空")
    _need(0 < rh <= 0.25, "rowlist 行高 rh=%.3f 越界（0<rh≤0.25）" % rh)
    _need(fs >= 15, "rowlist fs=%.1f <15（44号字号下限：字要大要饱满）" % fs)
    for i, (name, val, c) in enumerate(rows):
        if mask and hi is not None and i != hi:
            val = "…"
        elif mask and hi is None:
            val = "…"
        yy = y - i * rh
        if hi is not None and i == hi:
            f.add_artist(FancyBboxPatch((x, yy - rh + 0.010), w, rh - 0.014,
                         boxstyle="round,pad=0.001,rounding_size=0.006",
                         transform=f.transFigure, fc="#1B2333", ec=GOLD, lw=2.4, zorder=3))
            f.add_artist(Rectangle((x + 0.005, yy - rh + 0.018), 0.005, rh - 0.030,
                         transform=f.transFigure, fc=c, ec=c, zorder=4))
        f.text(x + 0.018, yy - rh / 2 + 0.005, name, color=TXT if hi == i else MUT,
               fontsize=fs, va="center", zorder=5,
               fontweight="bold" if hi == i else "normal")
        f.text(x + w - 0.014, yy - rh / 2 + 0.005, val,
               color=c if (hi == i or c != TXT) else TXT,
               fontsize=fs + 3, va="center", ha="right", zorder=5, fontweight="bold")


def _need(cond, msg):
    """G23（51号立·64号诊断）：组件参数违规在生成时报错不上屏——病灶发现从 gate/成片前移到生成时。
    每条断言锚定一次真实病灶（61号七类截图教训）。"""
    if not cond:
        raise ValueError("theme_base36 参数违规：" + msg)


def caption_strip(f, label, text, lit=False):
    """口径条（蓝框信息条）：把口径说明印在标题下，不只靠口播。"""
    _need(len(str(label)) <= 4, "caption label %r 超4字（50号：caption≤4字，长标签叠印——61号截图5/8）" % label)
    f.add_artist(FancyBboxPatch((0.045, 0.790), 0.91, 0.052,
                 boxstyle="round,pad=0.001,rounding_size=0.006",
                 transform=f.transFigure, fc="#10151F" if lit else PANEL,
                 ec=GOLD if lit else BLUE, lw=2.2 if lit else 1.2, zorder=3))
    f.text(0.06, 0.816, label, color=GOLD if lit else BLUE, fontsize=16.5,
           va="center", fontweight="bold", zorder=4)
    f.text(0.115, 0.816, text, color=TXT if lit else MUT, fontsize=16.5,
           va="center", zorder=4)


def kpi_row(f, stats, y=0.73, h=0.115, w=0.2225, step=0.2325, x0=0.045):
    """顶部 KPI 卡行（钩子页/摘要页用）：stats=[(标签, 数值, 颜色), ...]。"""
    for i, (lab, val, c) in enumerate(stats):
        x = x0 + i * step
        f.add_artist(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.0015,rounding_size=0.008",
                     transform=f.transFigure, fc=PANEL, ec=BORDER, lw=1.2, zorder=3))
        f.text(x + 0.015, y + h - 0.032, lab, color=MUT, fontsize=15.5, va="center", zorder=4)
        f.text(x + 0.015, y + h * 0.5 - 0.030, val, color=c, fontsize=24, va="center",
               fontweight="bold", zorder=4)


def panel_row(f, x, y, w, name, val, lit=False, h=0.115, mask=False):
    """变动面板行（钩子页右半）：lit=该行随口播点亮。
    mask=True（49号·G22渐进披露）：未点亮时数值显示「…」，口播提到才填真值。"""
    _need(0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1, "panel_row 坐标越界 x=%s y=%s w=%s（须为画幅比例0~1）" % (x, y, w))
    _need(h >= 0.115, "panel_row 行高 h=%.3f <0.115（值22号字溢出盒底——61号截图2）" % h)
    _need(bool(str(name).strip()), "panel_row 缺科目名（29号：四要素块必须带科目名，禁裸数字）")
    if mask and not lit:
        val = "…"
    f.add_artist(FancyBboxPatch((x, y - h + 0.053), w, h,
                 boxstyle="round,pad=0.0015,rounding_size=0.008",
                 transform=f.transFigure,
                 fc="#10151F" if lit else PANEL, ec=GOLD if lit else BORDER,
                 lw=1.8 if lit else 1.2, zorder=3))
    f.text(x + 0.015, y - 0.014, name, color=GOLD if lit else MUT, fontsize=16.5,
           va="center", zorder=4, fontweight="bold" if lit else "normal")
    f.text(x + 0.015, y - 0.052, val, color=TXT if lit else DIM, fontsize=20,
           va="center", zorder=4, fontweight="bold")


def pillar_cards(f, items, hl=None, y0=0.715, step=0.145, h=0.125):
    """结论页金框大卡+支柱卡（42号立条文，43号组件化执法；原型=ep01s s16）。
    items=[(前缀, 标题, 副题), ...] 3~5卡；hl=点亮的卡下标（金框+暗金底）。
    结论页主体必须由本组件承载（gate G9），rowlist/KPI 卡当结论页主体=红。"""
    for i, (pre, t, sub) in enumerate(items):
        y = y0 - i * step
        on = (hl == i)
        f.add_artist(FancyBboxPatch((0.08, y - 0.055), 0.84, h,
                     boxstyle="round,pad=0.0015,rounding_size=0.008",
                     transform=f.transFigure, fc="#14100A" if on else PANEL,
                     ec=GOLD if on else BORDER, lw=2.4 if on else 1.2, zorder=3))
        f.text(0.11, y + 0.028, pre, color=GOLD if on else MUT, fontsize=19,
               va="center", fontweight="bold", zorder=4)
        f.text(0.18, y + 0.028, t, color=GOLD if on else TXT, fontsize=24,
               va="center", fontweight="bold", zorder=4)
        f.text(0.18, y - 0.024, sub, color=TXT if on else MUT, fontsize=16,
               va="center", zorder=4)


def trio_cards(f, cards, lit=None, y=CB, w=0.25, h=0.285, x0=0.055, step=0.305):
    """结论前三卡（44号组件化，原型=ep01s s2，逐参数固化）：
    cards=[(标题, 大值, 正文1, 正文2, 颜色)]；lit=点亮下标。
    字号下限（G13 执法基准）：标题17/值19.5/正文16——手搓卡字号<15=红。"""
    for i, (t, v, b1, b2, c) in enumerate(cards):
        x = x0 + i * step
        on = (lit == i)
        f.add_artist(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.002,rounding_size=0.010",
                     transform=f.transFigure, fc="#14100A" if on else PANEL,
                     ec=GOLD if on else BORDER, lw=2.4 if on else 1.4, zorder=3))
        f.text(x + 0.016, y + h - 0.039, t, color=GOLD if on else MUT, fontsize=17, zorder=4)
        f.text(x + 0.016, y + h - 0.109, v, color=GOLD if on else c, fontsize=19.5,
               fontweight="bold", zorder=4)
        f.text(x + 0.016, y + h - 0.190, b1, color=TXT if on else MUT, fontsize=16, zorder=4)
        f.text(x + 0.016, y + h - 0.243, b2, color=TXT if on else MUT, fontsize=16, zorder=4)


def timeline_ladder(f, nodes, lit=None, y0=CB, dh=0.075, h0=0.155):
    """公司史阶梯（44号组件化，原型=ep01s s3a）：nodes=[(年份, 标签)] 3~6节点，
    阶梯卡上行+金线相连；lit=点亮下标。公司史页必须由本组件承载（G14），
    禁细线+小点裸时间轴。4节点自动加宽（w0.20/step0.225），6节点用 ep01s 原密度。"""
    n = len(nodes)
    w, step = (0.20, 0.225) if n <= 4 else (0.135, 0.15)
    x0 = 0.055 if n <= 4 else 0.055
    tops = []
    for i, (yr, lab) in enumerate(nodes):
        x, y = x0 + i * step, y0 + i * dh
        on = (lit == i)
        f.add_artist(FancyBboxPatch((x, y), w, h0,
                     boxstyle="round,pad=0.0015,rounding_size=0.008",
                     transform=f.transFigure, fc="#2A2108" if on else PANEL,
                     ec=GOLD if on else BORDER, lw=2.4 if on else 1.2, zorder=3))
        f.text(x + w / 2, y + h0 * 0.63, yr, color=GOLD if on else TXT, fontsize=26,
               ha="center", fontweight="bold", zorder=4)
        f.text(x + w / 2, y + h0 * 0.25, lab, color=TXT if on else MUT, fontsize=14.5,
               ha="center", zorder=4)
        tops.append((x + w / 2, y + h0))
    for i in range(len(tops) - 1):
        f.add_artist(plt.Line2D([tops[i][0], tops[i + 1][0]],
                     [tops[i][1] + 0.012, tops[i + 1][1] + 0.012],
                     color=GOLD, lw=1.4, alpha=0.75, zorder=2))


def donut(f, rect, items, center_top=None, center_bot=None, label_fs=16.5,
          explode_idx=None, width=0.40):
    """环形图（45号收编进 B 库，透传 theme.donut 一体机；G3 两半构成图标准画法）：
    items=[(名称,数值,颜色)]，扇区标名称+占比，中心两行文字。rect=[l,b,w,h]，b 建议 AX_CB。
    explode_idx=强调扇区下标（状态切换用，最小可感知变化）。
    资产/负债构成两半对称必须各一张（G3）；分类≥4、「其他」≤25%且排末位（G7）。"""
    ax = T.axes_panel(f, rect)
    T.donut(ax, items, center_top=center_top, center_bot=center_bot, label_fs=label_fs,
            explode_idx=explode_idx, width=width)
    return ax


def chip_row(f, chips, hl=None, y=CB, w=0.25, h=0.10, x0=0.045, step=0.33):
    """底部信息芯片行（45号组件化，原型=ep01s s7a「三芯片常驻」，R3 底部浮块整合的产物）：
    chips=[(标签, 数值, 颜色)] 2~4枚，填满 0.205-0.305 带，禁孤儿浮块沉底；
    hl=点亮下标（金框+暗金底）。标签15.5/数值17.5（≥G13 下限）。"""
    for i, (lab, val, c) in enumerate(chips):
        x = x0 + i * step
        on = (hl == i)
        f.add_artist(FancyBboxPatch((x, y), w, h,
                     boxstyle="round,pad=0.0015,rounding_size=0.008",
                     transform=f.transFigure,
                     fc="#14100A" if on else PANEL,
                     ec=GOLD if on else BORDER,
                     lw=1.8 if on else 1.1, zorder=3))
        f.text(x + 0.013, y + h * 0.70, lab, color=TXT if on else MUT,
               fontsize=15.5, va="center", zorder=4)
        f.text(x + 0.013, y + h * 0.28, val, color=c if on else DIM,
               fontsize=17.5, va="center", fontweight="bold", zorder=4)


def band_panel(ax, series, years, cur, label, kind="PB"):
    """估值分位带（46号收编，原型=ep01s band_panel·用户钦定估值表达模式）：
    三区制——红虚线=80%分位/蓝点线=中位/绿虚线=20%分位+顶底底色分区，灰线=序列，红点=现值。
    series=pd.Series（数值序列），years=同序年份数组（横轴取序列自身日期，31号P0②教训），
    kind=PB/PE：PE 用普通刻度+固定 ylim 防亏损期极值拉爆。标题=调用方给（指标·窗口·分位%+区名）。"""
    import numpy as _np
    p20, p50, p80 = (float(series.quantile(q)) for q in (0.20, 0.50, 0.80))
    x = _np.arange(len(series))
    RED, GREEN, BLUE, TXT = "#E5484D", "#3F7A54", "#3D5A80", "#F0F6FC"
    ax.plot(x, series.values, color="#7A8699", lw=1.1)
    ax.axhline(p80, color=RED, lw=1.4, ls="--")
    ax.axhline(p50, color=BLUE, lw=1.2, ls=":")
    ax.axhline(p20, color=GREEN, lw=1.4, ls="--")
    ax.axhspan(p80, float(series.max()) * 1.02, color=RED, alpha=0.06)
    ax.axhspan(float(series.min()) * 0.98, p20, color=GREEN, alpha=0.07)
    step = max(1, len(x) // 5)
    loc = list(range(0, len(x), step))
    ax.set_xticks(loc)
    ax.set_xticklabels([str(years[i]) for i in loc], fontsize=13.5)
    med = float(series.median())
    if kind == "PE" and (series <= 0).any():
        from matplotlib.ticker import ScalarFormatter
        ax.yaxis.set_major_formatter(ScalarFormatter())
        ax.set_ylim(2.5, 40)
        cur_y = min(cur, 37.5)   # 52号修：亏损期负PE退回固定线性窗
    elif kind == "PE" or (kind == "PB" and float(series.max()) > 6 * med):
        # 48号修（57号6699案 PE 43-521/PB 2.3-156）：极值序列改对数轴——
        # 三区制分位线全部在视野内、现值红点真实位置、普通数字刻度（防科学计数法）；
        # 常规区间（长和/太古锚）走原路径不受影响
        import matplotlib.ticker as _mt
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(_mt.FuncFormatter(
            lambda v, _p: ("%g" % v) if v >= 1 else "%.1f" % v))
        ax.yaxis.set_minor_formatter(_mt.NullFormatter())
        pos = series[series > 0]
        ax.set_ylim(float(pos.min()) * 0.8, float(series.max()) * 1.25)
        cur_y = min(max(cur, float(pos.min()) * 1.02), float(series.max()))
    else:
        ax.set_ylim(float(series.min()) * 0.9, float(series.max()) * 1.05)
        cur_y = min(cur, float(series.max()) * 1.02)
    ax.plot([x[-1]], [cur_y], "o", color=RED, ms=8, zorder=5)
    ax.annotate(f"{cur:.2f}", (x[-1], cur_y), xytext=(4, 6), textcoords="offset points",
                color=RED, fontsize=15, fontweight="bold")
    ylims = ax.get_ylim()
    for yy, cc, lab in [(p80, RED, f"高估 {p80:.2f}"), (p50, BLUE, f"中位 {p50:.2f}"),
                        (p20, GREEN, f"低估 {p20:.2f}")]:
        if yy < ylims[0] or yy > ylims[1]:
            continue  # 52号修：分位线出界（亏损期负PE等）不印标签，防幽灵文字
        ax.text(x[2], yy, lab, color=cc, fontsize=14, va="bottom")
    ax.set_title(label, color=TXT, fontsize=18.5, pad=4, fontweight="bold")


def month_ohlc(df, date_col="日期", open_col="开盘", high_col="最高",
               low_col="最低", close_col="收盘", start="2024-01-01"):
    """日线 → 月K（红涨绿跌数据准备）。"""
    import pandas as pd
    d = df[df[date_col] >= start].copy()
    d["m"] = d[date_col].dt.to_period("M")
    g = d.groupby("m")
    out = pd.DataFrame({"open": g[open_col].first(), "high": g[high_col].max(),
                        "low": g[low_col].min(), "close": g[close_col].last()})
    out = out.dropna().reset_index()
    out["x"] = range(len(out))
    return out


def candles(f, rect, m, ticks=6, title=None):
    """月K蜡烛（红涨绿跌）。rect=[l,b,w,h]，b 建议 AX_CB。"""
    ax = T.axes_panel(f, rect)
    up = m["close"] >= m["open"]
    ax.vlines(m["x"], m["low"], m["high"], color=np.where(up, RED, GREEN), lw=1.2, alpha=0.9)
    ax.bar(m["x"], (m["close"] - m["open"]).abs().clip(lower=1e-9),
           bottom=np.minimum(m["open"], m["close"]), width=0.62,
           color=np.where(up, RED, GREEN), edgecolor=np.where(up, RED, GREEN), zorder=3)
    step = max(1, len(m) // ticks)
    ax.set_xticks(m["x"][::step])
    ax.set_xticklabels([str(p) for p in m["m"][::step]], fontsize=14)
    if title:
        ax.set_title(title, color=MUT, fontsize=15.5, pad=4)
    return ax


def save(f, outdir, name):
    T.save(f, outdir, name)
