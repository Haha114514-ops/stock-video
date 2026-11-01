# -*- coding: utf-8 -*-
"""字幕事件生成（build_all.py / --subs-only 共用）

2026-10-24 根因修复（长和 ep01 复盘）：
  1) 分句终点取「下一个 token 的起点」，不再用「最后一字的 token 起点 +0.12」
     —— 旧法在整句=单 token（如"357亿"）时坍缩成 0.3s 闪屏。
  2) 语音连续处不留空窗：与下一句间隔 <= PAUSE 就接到下一句起点；
     只有真实停顿（> PAUSE）才让字幕消失。
  3) tail_text（画面尾句带）最多让掉最后 1 句且 <= TAIL_KEEP 字，
     不再把整段 3-5 秒的分句全 pop 掉。
  4) 生成后自报覆盖率；低于 COV_WARN 直接告警。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sysenv import SUB_FONT   # 字幕字体（libass 按名字找），按本机取

PAD = 0.5          # 与 build_all 的段间静音一致
PAUSE = 0.55       # 超过这个间隔才认为是"说话停顿"，允许字幕空窗
MIN_DUR = 0.55     # 单条字幕最短停留
TAIL_KEEP = 14     # tail_text 让位最多让掉的字数（约 1 句）
COV_WARN = 0.90    # 覆盖率告警线


def norm_spoken(s):
    return "".join(ch for ch in s if (ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
                   and ch not in "·—…")


def split_lines(text, maxlen):
    parts = re.split(r"(?<=[，。；：？！、])", text)
    lines = []
    for p in parts:
        p = p.strip()
        while len(p) > maxlen:
            cut = maxlen

            def in_num(s, i):
                if i <= 0 or i >= len(s):
                    return False
                a, b = s[i - 1], s[i]
                if a.isdigit() and (b.isdigit() or b in ".%"):
                    return True
                if a in ".," and b.isdigit() and i >= 2 and s[i - 2].isdigit():
                    return True
                return False

            while cut > 1 and in_num(p, cut):
                cut -= 1
            lines.append(p[:cut])
            p = p[cut:].strip("，。；：？！、 ")
        if p:
            lines.append(p)
    return lines


def speak_weight(s):
    """发音权重：数字/百分号读出来音节远多于字符数，纯字数分配会让字幕漂移"""
    w = 0.0
    for i, c in enumerate(s):
        if c.isdigit():
            w += 1.8
        elif c == "%":
            w += 3.0
        elif c in "+-−":
            w += 1.5
        elif c in ".,:":
            w += 1.0 if i + 1 < len(s) and s[i + 1].isdigit() else 0.2
        elif c in "。！？":
            w += 2.0
        elif c in "，、；：":
            w += 1.2
        elif ord(c) > 0x2E80:
            w += 1.0
        elif c.isalpha():
            w += 0.9
        else:
            w += 0.25
    return w


def _load_bounds(seg_id):
    p = f"tts/seg{seg_id}.bounds.json"
    if not os.path.exists(p):
        return []
    try:
        return json.load(open(p, encoding="utf-8-sig"))
    except Exception:
        return []


def _spans_for_segment(s, d, maxlen):
    """返回 [[start, end, text], ...]（相对本段起点）"""
    lines = split_lines(s["text"], maxlen)
    if not lines:
        return []
    bnds = _load_bounds(s["id"])
    spans = []

    if bnds:
        toks = [(norm_spoken(b.get("text", "")), float(b.get("t", 0.0))) for b in bnds]
        toks = [(t_, tt) for t_, tt in toks if t_]
        tok_spans, pos = [], 0
        for t_, tt in toks:
            tok_spans.append((pos, pos + len(t_), tt))
            pos += len(t_)

        def t_at(p):
            """p 位置所在 token 的起点"""
            for a, b_, tt in tok_spans:
                if a <= p < b_:
                    return tt
            return d

        def t_after(p):
            """p 之后的第一个 token 起点 = 这句话的自然终点"""
            for a, b_, tt in tok_spans:
                if a >= p:
                    return tt
            return d

        norm_all = norm_spoken(s["text"])
        weights = {l: speak_weight(l) for l in lines}
        w_total = sum(weights.values()) or 1.0
        cursor = 0.0
        last_end = 0.0
        for l in lines:
            nl = norm_spoken(l)
            if not nl:
                continue
            idx = norm_all.find(nl, int(cursor))
            if idx < 0:
                idx = norm_all.find(nl)
            if idx >= 0:
                st = max(t_at(idx), last_end)
                en = max(t_after(idx + len(nl)), st + MIN_DUR)
                spans.append([st, min(en, d), l])
                last_end = min(en, d)
                cursor = idx + len(nl)
            else:
                dur = d * weights[l] / w_total
                spans.append([last_end, min(last_end + dur, d), l])
                last_end = min(last_end + dur, d)
    else:
        w_total = sum(speak_weight(l) for l in lines) or 1.0
        t = 0.0
        for l in lines:
            seg_len = d * speak_weight(l) / w_total
            spans.append([t, min(t + seg_len, d), l])
            t += seg_len

    # 单调 + 不重叠
    for i in range(len(spans)):
        if i:
            spans[i][0] = max(spans[i][0], spans[i - 1][0] + 0.05)
        spans[i][1] = max(spans[i][1], spans[i][0] + 0.20)

    # 语音连续处补满：与下一句的间隙 <= PAUSE 就接到下一句起点
    for i in range(len(spans) - 1):
        gap = spans[i + 1][0] - spans[i][1]
        if gap <= PAUSE:
            spans[i][1] = max(spans[i][1], spans[i + 1][0])
        elif spans[i][1] > spans[i + 1][0]:
            spans[i][1] = spans[i + 1][0]

    # 末句：至少 MIN_DUR，且尽量咬住段尾（段尾静音前的语音不该裸奔）
    if spans:
        spans[-1][1] = max(spans[-1][1], min(d, spans[-1][0] + MIN_DUR))
        if spans[-1][1] < d - PAUSE:
            spans[-1][1] = d

    # tail_text 让位：只让最后 1 句，且 <= TAIL_KEEP 字
    tt = s.get("tail_text")
    if tt and spans:
        last = norm_spoken(spans[-1][2])
        if last and last in norm_spoken(tt) and len(last) <= TAIL_KEEP:
            spans.pop()
            if spans:
                spans[-1][1] = d   # 让位后由前一句咬住段尾（2026-10-24 修：tail_text 不再造成覆盖率缺口）

    # 终局保底：起点单调衔接、单条时长下限（杜绝负时长/零时长事件）
    for i in range(len(spans)):
        if i:
            spans[i][0] = max(spans[i][0], spans[i - 1][1])
        spans[i][1] = max(spans[i][1], spans[i][0] + 0.30)
    negs = [(round(a, 2), round(b, 2), l[:14]) for a, b, l in spans if b - a < 0.2]
    if negs:
        print(f"   [dbg {s['id']}] d={d:.2f} NEG:", negs)

    return spans


def build_events(segs, durs, maxlen=22):
    """返回 (events, stats)；events=[(abs_start, abs_end, text)]"""
    events, stats = [], []
    t0 = 0.0
    for s, d in zip(segs, durs):
        spans = _spans_for_segment(s, d, maxlen)
        for st, en, l in spans:
            events.append((t0 + st, t0 + en, l))
        cov = sum(b - a for a, b, _ in spans) / d if d > 0 else 0
        stats.append({"id": s["id"], "dur": d, "cov": cov, "n": len(spans),
                      "longest_gap": _longest_gap(spans)})
        t0 += d + PAD
    return events, stats


def _longest_gap(spans):
    g = 0.0
    for i in range(len(spans) - 1):
        g = max(g, spans[i + 1][0] - spans[i][1])
    return g


def header(sw, sh, cfg, sub_fs=None):
    if sub_fs is None:
        ratio = 0.038 if sw > sh else 0.026      # 横屏 1080p≈41px，竖屏 1920≈50px
        sub_fs = max(30, round(sh * ratio))
    sub_mv = round(sh * 0.059)
    sub_mlr = round(sw * 0.05)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {sw}
PlayResY: {sh}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUB_FONT},{sub_fs},&H00FFFFFF,&H00FFFFFF,&HA0000000,&H60000000,0,0,0,0,100,100,0,0,1,2.2,1,2,{sub_mlr},{sub_mlr},{sub_mv},1
Style: Pop,{SUB_FONT},30,&H0017110D,&H00FFFFFF,&H0029B4F0,&H000D1117,1,0,0,0,100,100,0,0,3,3.5,0,2,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(sec):
    """整数厘秒制格式化，杜绝浮点 %60 取整的进位丢失（499.00 曾被格式化成 18.00）"""
    total = int(round(max(sec, 0.0) * 100))
    h, rem = divmod(total, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def lines(events):
    return "".join(f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{l}\n" for a, b, l in events)


def report(stats, events):
    """打印覆盖率，低于阈值大声告警；返回总覆盖率"""
    print("SUBSV3-MARKER")  # 临时：确认烧录用的是新版引擎
    total_audio = sum(x["dur"] for x in stats)
    on = sum(b - a for a, b, _ in events)
    cov = on / total_audio if total_audio else 0
    short = [e for e in events if e[1] - e[0] < 0.45]
    print("\n===== 字幕自检 =====")
    for x in stats:
        flag = "OK " if x["cov"] >= COV_WARN else "低!"
        print(f"  seg{x['id']:<3} {x['dur']:5.1f}s  {x['n']:2d}条  覆盖 {x['cov']*100:5.1f}%  "
              f"最长空窗 {x['longest_gap']:4.2f}s  {flag}")
    print(f"  合计 语音 {total_audio:.1f}s  字幕 {on:.1f}s  覆盖率 {cov*100:.1f}%  "
          f"过短(<0.45s) {len(short)} 条")
    if cov < COV_WARN:
        print(f"  [WARN] 字幕覆盖率 {cov*100:.1f}% < {COV_WARN*100:.0f}%：观众会听到没字的句子")
    if len(short) > len(events) * 0.05:
        print(f"  [WARN] 过短字幕 {len(short)} 条（>5%）：会有闪屏感")
    return cov
