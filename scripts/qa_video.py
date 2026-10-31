# -*- coding: utf-8 -*-
"""成片 QA 门禁（暗色拆解线）

用法：python qa_video.py "<工程目录>"

检查项（2026-10-24 定，源自长和 ep01 复盘）：
  1. 字幕覆盖率 ≥ 90%：观众听到的话必须有字
  2. 过短字幕（<0.45s）占比 ≤ 5%：否则闪屏
  3. 段内字幕空窗 ≤ 1.2s
  4. 字幕字号 ≥ 3.0% 画面高
  5. 状态切换改动面积 ≥ 3% 画面（低于视为"假动效"）
  6. 单段时长 > 35s 且切换不足 → 静态长段告警
"""
import json
import os
import subprocess
import sys

FAIL, WARN = [], []


def fail(msg):
    FAIL.append(msg)


def warn(msg):
    WARN.append(msg)


def dur_of(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return float(json.loads(out)["format"]["duration"])


def t2s(x):
    h, m, sec = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def main(workdir):
    os.chdir(workdir)
    cfg = json.load(open("segments.json", encoding="utf-8-sig"))
    segs = cfg["segments"]
    PAD = 0.5

    from PIL import Image
    sw, sh = Image.open(os.path.join("slides", segs[0]["slide"])).size
    print(f"画布 {sw}x{sh}  段数 {len(segs)}")

    # ---- 段时长（优先用音频，缺了用分段视频）
    durs = []
    for s in segs:
        p = f"tts/seg{s['id']}.mp3"
        if not os.path.exists(p):
            p = f"segs/seg{s['id']}.mp4"
        durs.append(dur_of(p) if os.path.exists(p) else 0.0)
    t0s, t = [], 0.0
    for d in durs:
        t0s.append(t)
        t += d + PAD
    total = t

    # ---- 字幕
    ass = open("subs.ass", encoding="utf-8-sig").read()
    ev = []
    fs = None
    for ln in ass.splitlines():
        if ln.startswith("Style: Default"):
            fs = float(ln.split(",")[2])
        if ln.startswith("Dialogue:") and ",Default," in ln:
            p = ln.split(",", 9)
            ev.append((t2s(p[1]), t2s(p[2]), p[9]))
    ev.sort()
    on = sum(b - a for a, b, _ in ev)
    cov = on / total if total else 0
    short = [e for e in ev if e[1] - e[0] < 0.45]
    print(f"\n[字幕] {len(ev)} 条  亮屏 {on:.1f}s / 语音 {total:.1f}s  覆盖率 {cov*100:.1f}%")
    if cov < 0.85:
        fail(f"字幕覆盖率 {cov*100:.1f}% < 85%：大段'只有声音没有字'")
    elif cov < 0.90:
        warn(f"字幕覆盖率 {cov*100:.1f}% < 90%")
    if len(short) > len(ev) * 0.05:
        fail(f"过短字幕 {len(short)}/{len(ev)} 条（<0.45s）：会闪屏")
    if fs and fs < sh * 0.030:
        warn(f"字幕字号 {fs:.0f}px = 画面高 {fs/sh*100:.1f}%，偏小（横屏建议 ≥3.5%）")

    # 段内空窗
    for i, (s, d) in enumerate(zip(segs, durs)):
        a, b = t0s[i], t0s[i] + d
        inside = [(x, y) for x, y, _ in ev if x >= a - 0.01 and y <= b + 0.01]
        if not inside:
            fail(f"seg{s['id']} 整段无字幕")
            continue
        gaps = [inside[j + 1][0] - inside[j][1] for j in range(len(inside) - 1)]
        head = inside[0][0] - a
        tail = b - max(y for _, y in inside)
        worst = max(gaps + [head, tail])
        if worst > 1.2:
            warn(f"seg{s['id']} 段内空窗 {worst:.1f}s（>{1.2}s）")

    # ---- 动效（状态切换改动面积）
    small, changes = 0, 0
    rows = []
    for s in segs:
        imgs = [s["slide"]] + [x["img"] for x in (s.get("states") or [])]
        prev = None
        for im in imgs:
            a = __import__("numpy").asarray(Image.open(os.path.join("slides", im)).convert("RGB"), dtype="int16")
            if prev is not None:
                ch = int((__import__("numpy").abs(a - prev).sum(2) > 40).sum())
                pct = ch / (sw * sh) * 100
                changes += 1
                if pct < 3.0:
                    small += 1
                    rows.append((s["id"], im, round(pct, 2)))
            prev = a
    print(f"\n[动效] 状态切换 {changes} 次，其中 {small} 次改动 <3% 画面")
    if changes and small / changes > 0.5:
        fail(f"{small}/{changes} 次切换改动 <3%：观感等于静态画片")
    elif small:
        warn(f"{small} 次切换改动 <3%：局部数字替换可接受，但别整段全靠它")
    for r in rows[:8]:
        print(f"    seg{r[0]:<3} {r[1]:<22} 仅改 {r[2]}%")

    # ---- 段长
    long_seg = [(s["id"], d, len(s.get("states") or [])) for s, d in zip(segs, durs) if d > 35]
    if long_seg:
        msg = "、".join(f"seg{i}({d:.0f}s/{n}切)" for i, d, n in long_seg)
        if any(n < 4 for _, _, n in long_seg):
            warn(f"长段切换偏少：{msg}")
        print(f"\n[节奏] 超 35s 的段：{msg}")

    # ---- 结论
    print("\n===== QA 结论 =====")
    for m in FAIL:
        print("  [FAIL]", m)
    for m in WARN:
        print("  [WARN]", m)
    if not FAIL and not WARN:
        print("  PASS：全部达标")
    elif not FAIL:
        print("  PASS（有告警）")
    return 1 if FAIL else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("用法: python qa_video.py <workdir>")
    sys.exit(main(sys.argv[1]))
