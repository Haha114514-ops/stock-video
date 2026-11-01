# -*- coding: utf-8 -*-
"""<公司>(<代码>) —— 分镜脚本骨架。复制到 <工程>/video.py 后改。
主线：<故事.md 第一行，一句话>

用法：python video.py tts | preview [--only 3,5] | render [resume] [--only 3] [--jobs N] | mux

这份骨架故意不带任何一期的章节：章节、顺序、每章构图从这一期的 故事.md 推出来，不看别期的分镜代码。
"""
import os, sys, json


def _find_skill():
    """skill 目录（SKILL.md 所在目录）：环境变量 STOCK_VIDEO_SKILL → 下面 <skill> 填的路径 →
    从工程目录往上找 .claude/skills/stock-video → ~/.claude/skills/stock-video。工程放在装了 skill 的工作区里就不用改路径。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.environ.get('STOCK_VIDEO_SKILL'), r'<skill>']
    d = here
    while True:
        cands.append(os.path.join(d, '.claude', 'skills', 'stock-video'))
        if os.path.dirname(d) == d: break
        d = os.path.dirname(d)
    cands.append(os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'stock-video'))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, 'scripts', 'motion.py')): return c
    sys.exit('找不到 skill 脚本 scripts/motion.py：设环境变量 STOCK_VIDEO_SKILL=<skill 目录>，或把 video.py 里的 <skill> 换成 skill 目录')


SKILL = _find_skill()
sys.path.insert(0, os.path.join(SKILL, 'scripts'))
import numpy as np, pandas as pd
import motion as M
from motion import *          # 配色、Frame、缓动 pg/out/eo/eio、图表原语
from components import *      # tile / vbars / line_chart / hline / val_panel / pct_stats / quote / xfade
from fx import *              # count / fly / equation / split / drain / zoom / strike
from fxplus import *          # camera / versus / timeline / ring / arrow / highlight / underline / waterfall / sankey / transition

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------- 数据：全片数字只从 facts.json 来（facts.py 生成），不在这里手写 ----------
FX = json.load(open(os.path.join(ROOT, 'facts.json'), encoding='utf-8'))


# ---------- 分镜：每章一个函数 sN(f, t, B, T) ----------
# f 画布；t 本章内秒数；B[i] 第 i 句开口时刻；T 本章总长。
# 写法：a = pg(t, B[2]) —— 第 3 句开口时开始、0.7 秒内 0→1，用它控制透明度 / 长度 / 数字。
#       句中后面的意思：pg(t, B.at(2, '6.5%')) —— 第 3 句念到"6.5%"时出场（别手写 B[2] + 2.4）。
# 讲到什么才画什么；没讲到的位置空着，卡片框跟着内容一起出现，不先画一个大框再往里填。
# 节拍：长句里每 3 秒要有一样东西跟着话变（亮起 / fx.count 滚数 / fx.fly 飞进算式 / fx.split 拆开）。
#       preview 会按审片包同一判定列出"第几章第几句、念到哪几个字时不动"（output/still.txt），超过 7 秒不动的段先补再渲染（3~7 秒是让人看图，不用补；总占比只报数）。

def s0(f, t, B, T):
    # 开场：报表上最值得解释的一件事 + 一个数据能回答的问题（故事.md 第四节）；数字的说法照 facts 的 labels
    a = pg(t, B[0])
    f.text((W / 2, 520), '<开场：最值得解释的事实>', 72, GOLD, a, 'b', 'mm')


def s1(f, t, B, T):
    headline(f, t, '01', '<章名：2~5 个字，朝主线说话>')
    a = pg(t, B[0])
    f.text((130, 400), '<这一章在主线上回答什么>', 40, TXT, a, 'b', 'lm')


# ---------- 旁白：一句一个动画节拍；想让元素在哪一刻出现，就在哪里断句 ----------
M.setup(root=ROOT, name='<公司简称>', code='<代码>.SH',
        source='数据：公司定期报告 · 公告 · 东方财富  |  截至 <日期>',
        out_name='<公司>_<代码>.mp4',
        scenes=[
            ('开场', ['<第一句>', '<第二句>'], s0),
            ('<章名>', ['<第一句>', '<第二句>'], s1),
            # ……结尾：回到开场的问题，按 故事.md 推理表回答（答不出就说"还说不准，看哪几个数"）；结论只说一遍 + 免责声明
        ])

if __name__ == '__main__':
    M.cli()
