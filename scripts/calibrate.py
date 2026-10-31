# -*- coding: utf-8 -*-
"""声称-实际校准（修4）：核对 SKILL 声称的数字 vs 视频产物实际。

用法：
    python calibrate.py            # 全量核对，红=exit 1
核对项：
    A. SKILL 中「EP.N 名称（X 帧/Y 段）」声称 vs 对应 epNN/segments.json 实际
    B. 「全局语速 +20%」声称 vs 各期 rate（带「按旧版制作」标注的期自动豁免）
"""
import json
import os
import re
import sys

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SKILL.md")
# 旧管线的成片目录（51号前），可用环境变量 STOCK_VIDEO_OLD_VIDEOS 指定
VIDEOS = os.environ.get("STOCK_VIDEO_OLD_VIDEOS", r"D:\AI\videos")


def load_ep(ep_no):
    epnn = "ep%02d" % int(ep_no)
    for ws in sorted(os.listdir(VIDEOS)):
        p = os.path.join(VIDEOS, ws, epnn, "segments.json")
        if os.path.exists(p):
            cfg = json.load(open(p, encoding="utf-8-sig"))
            return os.path.join(VIDEOS, ws, epnn), cfg
    return None, None


def main():
    skill = open(SKILL, encoding="utf-8").read()
    reds, notes = [], []
    # A. 帧/段声称
    for m in re.finditer(r"EP\.(\d+)\s*([^\s（(]+)（(\d+)\s*帧/(\d+)\s*段）", skill):
        ep, name, f_claim, s_claim = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        path, cfg = load_ep(ep)
        if cfg is None:
            notes.append("EP.%s %s：未找到 ep 目录，跳过" % (ep, name))
            continue
        segs = cfg.get("segments", [])
        n_seg = len(segs)
        n_states = sum(len(s.get("states") or []) for s in segs)
        ok = (n_states == f_claim and n_seg == s_claim)
        line = "EP.%s %s：声称 %d帧/%d段，实际 %d状态/%d段" % (ep, name, f_claim, s_claim, n_states, n_seg)
        (notes if ok else reds).append(("PASS " if ok else "RED  ") + line)
    # B. 语速声称
    if "+20%" in skill and ("全局统一" in skill or "两条线全局统一" in skill):
        for ws in sorted(os.listdir(VIDEOS)):
            for root, dirs, files in os.walk(os.path.join(VIDEOS, ws)):
                dirs[:] = [d for d in dirs if d not in ("frames", "tts", "segs", "slides")]
                if "segments.json" not in files:
                    continue
                p = os.path.join(root, "segments.json")
                cfg = json.load(open(p, encoding="utf-8-sig"))
                spec = str(cfg.get("spec") or "")
                rel = os.path.relpath(p, VIDEOS)
                if "旧版" in spec:
                    notes.append("PASS 豁免 %s（标注：%s）" % (rel, spec[:30]))
                elif cfg.get("rate") != "+20%":
                    reds.append("RED   %s：rate=%s 与全局 +20% 声称不符且无旧版标注" % (rel, cfg.get("rate")))
    for n in notes:
        print("  ", n)
    for r in reds:
        print("  ", r)
    print("=== 校准: %d 红, %d 项通过/豁免 ===" % (len(reds), len(notes)))
    if reds:
        sys.exit(1)


if __name__ == "__main__":
    main()
