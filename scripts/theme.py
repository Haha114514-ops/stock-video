# -*- coding: utf-8 -*-
"""stock-video 公共样式库：暗色财经风 1920x1080 幻灯片设计系统。
用法：import theme as T; T.setup(); f = T.new(); ... T.save(f, outdir, "slideN.png")
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 配色
BG, PANEL, PANEL2 = "#0D1117", "#161B22", "#10151F"
BORDER = "#30363D"
TXT, MUT, DIM = "#F0F6FC", "#9DA6B2", "#7D8894"
RED, GREEN, GOLD, BLUE = "#F85149", "#3DBA63", "#F0B429", "#58A6FF"
W, H = 19.2, 10.8  # 1920x1080 @100dpi


def setup():
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False


def new():
    f = plt.figure(figsize=(W, H), dpi=100)
    f.patch.set_facecolor(BG)
    return f


def chrome(f, show, tag, n, total, footer, accent=None):
    """页眉（栏目名+章节标签）+ 页脚（来源+页码）+ 分隔线"""
    f.text(0.045, 0.955, show, color=MUT, fontsize=17, va="center", fontweight="bold")
    f.text(0.955, 0.955, tag, color=accent or GOLD, fontsize=17, va="center",
           ha="right", fontweight="bold")
    f.text(0.045, 0.035, footer, color=DIM, fontsize=13, va="center")
    f.text(0.955, 0.035, f"{n} / {total}", color=DIM, fontsize=13, va="center", ha="right")
    f.add_artist(plt.Line2D([0.045, 0.955], [0.928, 0.928], color=BORDER, lw=1.2))


def card(f, x, y, w, h, fc=PANEL, ec=BORDER, lw=1.4):
    f.add_artist(plt.Rectangle((x, y), w, h, transform=f.transFigure,
                 facecolor=fc, edgecolor=ec, linewidth=lw, zorder=1))


def title(f, text, size=34, y=0.85):
    f.text(0.045, y, text, color=TXT, fontsize=size, fontweight="bold", va="center")


def stat(f, x, y, label, value, color, ls=16.5, vs=24, ha="left"):
    """竖排：灰标签 + 彩色大数字"""
    f.text(x, y, label, color=MUT, fontsize=ls, ha=ha, va="center")
    f.text(x, y - 0.055, value, color=color, fontsize=vs, ha=ha, va="center",
           fontweight="bold")


def axes_panel(f, rect, yticks=True, xticks=True, grid_axis="y"):
    """带样式的图表区；rect=[l,b,w,h]"""
    ax = f.add_axes(rect)
    ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_color(BORDER)
    ax.tick_params(colors=MUT, labelsize=13)
    if grid_axis:
        ax.grid(axis=grid_axis, color=BORDER, lw=0.6, alpha=0.6)
    return ax


def img_panel(f, path, x, y, w, label=None, lab_color=None):
    """贴图片面板。注意：16:9 图在 16:9 画布上图元坐标 h 应等于 w，且需 aspect=auto"""
    h = w
    ax = f.add_axes([x, y, w, h])
    ax.imshow(plt.imread(path), aspect="auto")
    ax.axis("off")
    for s in ax.spines.values():
        s.set_color(lab_color or BORDER)
        s.set_linewidth(2)
    if label:
        f.text(x, y + h + 0.018, label, color=lab_color or MUT, fontsize=16,
               fontweight="bold")
    return h


def terminal(f, x, y, w, h, lines, step=0.040, fs=13.5):
    """仿终端窗口。lines=[(文本, 颜色), ...]"""
    card(f, x, y, w, h, fc="#010409")
    axc = f.add_axes([0, 0, 1, 1])
    axc.set_axis_off()
    axc.set_xlim(0, 1)
    axc.set_ylim(0, 1)
    axc.scatter([x + 0.014 + i * 0.016 for i in range(3)], [y + h - 0.022] * 3,
                s=55, c=["#FF5F56", "#FFBD2E", "#27C93F"], zorder=3)
    yy = y + h - 0.062
    for txt, c in lines:
        f.text(x + 0.018, yy, txt, color=c, fontsize=fs, va="center",
               family=["Consolas", "Microsoft YaHei"], zorder=3)
        yy -= step


def save(f, outdir, name):
    f.savefig(f"{outdir}\\{name}", facecolor=BG)
    plt.close(f)
    print("ok", name)


def slice_labels(ax, wedges, labels, fracs, r_inside=0.72, r_outside=1.16,
                 fs=13.5, min_inside=0.14):
    """在扇区上/旁直接标 名称+占比：大扇区(≥min_inside)标环内(按底色自动黑/白)，
    小扇区标环外(用扇区同色)。labels 与 wedges 一一对应，fracs 为占比(0~1)。"""
    import numpy as np
    for w, lab, fr in zip(wedges, labels, fracs):
        ang = np.deg2rad((w.theta1 + w.theta2) / 2)
        x, y = np.cos(ang), np.sin(ang)
        if fr >= min_inside:
            from matplotlib import patheffects as pe
            ax.text(x * r_inside, y * r_inside, lab, ha="center", va="center",
                    color="#FFFFFF", fontsize=fs, fontweight="bold", zorder=5,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="#0D1117")])
        else:
            ax.text(x * r_outside, y * r_outside, lab, ha="center", va="center",
                    color=w.get_facecolor(), fontsize=fs, fontweight="bold", zorder=5)


def donut(ax, items, center_top=None, center_bot=None, width=0.40, start_angle=90,
          explode_idx=None, label_fs=13, r_inside=0.72, r_outside=1.16,
          min_inside=0.14, center_top_fs=15, center_bot_fs=26, counterclock=False,
          center_vcolor=TXT):
    """环形图一体机：items=[(名称,数值,颜色)]。画图+扇区标注（名称+占比）绑死，
    大扇区(≥min_inside)标环内(按底色自动黑/白)，小扇区标环外(扇区同色)。
    中心两行文字可选（center_top 灰小字 / center_bot 白大字）。返回 (wedges, fracs)。"""
    import numpy as np
    names = [i[0] for i in items]
    vals = [float(i[1]) for i in items]
    cols = [i[2] for i in items]
    total = sum(vals)
    fracs = [v / total for v in vals]
    ex = None
    if explode_idx is not None:
        ex = [0.05 if i == explode_idx else 0 for i in range(len(items))]
    wedges, _ = ax.pie(vals, colors=cols, startangle=start_angle, counterclock=counterclock,
                       explode=ex, wedgeprops=dict(width=width, edgecolor=BG, lw=2))
    slice_labels(ax, wedges, [f"{n}\n{fr*100:.0f}%" for n, fr in zip(names, fracs)], fracs,
                 r_inside=r_inside, r_outside=r_outside, fs=label_fs, min_inside=min_inside)
    if center_top:
        ax.text(0, 0.13, center_top, color=MUT, fontsize=center_top_fs, ha="center")
    if center_bot:
        ax.text(0, -0.11, center_bot, color=center_vcolor, fontsize=center_bot_fs,
                ha="center", fontweight="bold")
    ax.set_aspect("equal")
    return wedges, fracs


def _est_w(s, fs):
    w = 0.0
    for c in s:
        w += fs * 7.234e-4 if ord(c) > 0x2E80 else fs * 3.98e-4
    return w


def verdict(f, parts, y=0.108, fs=22):
    """底部大字结论（plain 无卡版）：parts=[(text,color)] 居中排；位于 ASS 字幕区(0.05-0.095)上方。"""
    total = sum(_est_w(t, fs) for t, _ in parts)
    x = 0.5 - total / 2
    for t, c in parts:
        f.text(x, y, t, color=c, fontsize=fs, va="center", fontweight="bold", zorder=3)
        x += _est_w(t, fs)


def card_fit(f, x, y, w, h, title, value, vcolor, body_lines, body_color=TXT,
             title_fs=17, value_fs=22, body_fs=16, ls=2.0, body_top=0.62):
    """结论三卡防溢出：正文按行数从 body_top 起排，行高自动算，保证收在卡内。"""
    from matplotlib.patches import FancyBboxPatch
    f.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0015,rounding_size=0.010",
                 transform=f.transFigure, fc=PANEL, ec=BORDER, lw=1.4, zorder=2))
    f.text(x + 0.018, y + h - 0.055, title, color=MUT, fontsize=title_fs)
    f.text(x + 0.018, y + h - 0.135, value, color=vcolor, fontsize=value_fs,
           fontweight="bold")
    line_h = body_fs / 72 * 100 / 1080 * ls
    y0 = y + h * body_top
    f.text(x + 0.018, y0, "\n".join(body_lines), color=body_color, fontsize=body_fs,
           va="top", linespacing=ls)
    end = y0 - line_h * len(body_lines)
    if end < y + 0.012:
        print(f"⚠️ card_fit 溢出警告: 卡底 {y+0.012:.3f} > 正文尾 {end:.3f}")
    return end
