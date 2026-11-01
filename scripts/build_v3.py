# -*- coding: utf-8 -*-
"""build v3：元素生长版合成管线（参考黑贝贝实验室图文流）
每段多张状态图（slide{i}_{k}.png），段内按解说时长均分硬切（元素逐个出现），
段间 xfade 转场。无连续缩放 = 零抖动。字幕：深墨字+白描边（浅底）。
用法：python build_v3.py <工程目录>
"""
import asyncio, glob, json, os, re, subprocess, sys, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sysenv import SUB_FONT

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

import edge_tts
from PIL import Image

PAD = 0.25
FADE = 0.25
TRANSITIONS = ["fade", "smoothleft"]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        sys.exit(f"CMD FAILED: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout

def dur_of(path):
    out = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
               path])
    return float(json.loads(out)["format"]["duration"])

# ---------- 1. TTS ----------
cfg = json.load(open("segments.json", encoding="utf-8-sig"))
segs = cfg["segments"]
os.makedirs("tts", exist_ok=True)

async def tts_all():
    for s in segs:
        mp3 = f"tts/seg{s['id']}.mp3"
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1000:
            print("skip tts", mp3); continue
        rate = s.get("rate", cfg["rate"])
        await edge_tts.Communicate(s["text"], cfg["voice"], rate=rate).save(mp3)
        print("tts ok", mp3, f"rate={rate}")

asyncio.run(tts_all())

SW, SH = Image.open(glob.glob("slides/slide1_*.png")[0]).size
print(f"canvas: {SW}x{SH}")

# ---------- 2. 分段视频（状态图硬切） ----------
os.makedirs("segs", exist_ok=True)
durs, mp3durs = [], []
for idx, s in enumerate(segs):
    mp3, mp4 = f"tts/seg{s['id']}.mp3", f"segs/seg{s['id']}.mp4"
    d = dur_of(mp3)
    states = sorted(glob.glob(f"slides/slide{s['id']}_*.png"),
                    key=lambda p: int(re.search(r"_(\d+)\.png$", p).group(1)))
    if not states:
        states = [f"slides/{s['id']}.png"]
    total = d + PAD
    per = total / len(states)
    d_list = [round(per, 3)] * (len(states) - 1) + [round(total - per * (len(states) - 1), 3)]
    pieces = []
    for k, (img, t) in enumerate(zip(states, d_list)):
        p = f"segs/_s{idx}_{k}.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", img,
             "-vf", f"scale={SW}:{SH},format=yuv420p",
             "-t", f"{t:.3f}", "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", p])
        pieces.append(p)
    inputs = []
    for p in pieces:
        inputs += ["-i", p]
    inputs += ["-i", mp3]
    fc = "".join(f"[{k}:v]" for k in range(len(pieces))) + \
         f"concat=n={len(pieces)}:v=1:a=0[v];[{len(pieces)}:a]apad=pad_dur={PAD}[a]"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", fc,
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", mp4])
    durs.append(total)
    mp3durs.append(d)
    print("seg ok", mp4, f"{d:.1f}s x{len(states)}states")

# ---------- 3. 段间转场（xfade + acrossfade） ----------
n = len(segs)
inputs = []
for s in segs:
    inputs += ["-i", f"segs/seg{s['id']}.mp4"]
parts = []
prev_v, prev_a = "[0:v]", "[0:a]"
t_acc = durs[0]
offsets = []
for i in range(1, n):
    off = t_acc - FADE
    offsets.append(off)
    trans = TRANSITIONS[(i - 1) % len(TRANSITIONS)]
    out_v, out_a = f"[v{i}]", f"[a{i}]"
    parts.append(f"{prev_v}[{i}:v]xfade=transition={trans}:duration={FADE}:"
                 f"offset={off:.3f}{out_v}")
    parts.append(f"{prev_a}[{i}:a]acrossfade=d={FADE}{out_a}")
    prev_v, prev_a = out_v, out_a
    t_acc = off + durs[i]
run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
     "-map", prev_v, "-map", prev_a,
     "-c:v", "libx264", "-preset", "medium", "-crf", "18",
     "-c:a", "aac", "-b:a", "192k", "merged.mp4"])

# ---------- 4. 字幕（浅底：深墨字+白描边） ----------
if SH > SW:
    SUB_MAXLEN = 9
    SUB_FS = max(40, round(SW * 0.062))
    SUB_MV = round(SH * 0.075)
    SUB_MLR = round(SW * 0.045)
else:
    SUB_MAXLEN = 16
    SUB_FS = max(34, round(SH * 0.034))
    SUB_MV = round(SH * 0.060)
    SUB_MLR = round(SW * 0.05)
INK_ASS = "&H00262B2F"   # 墨色 #2F2B26 → BGR

def split_lines(text, maxlen=SUB_MAXLEN):
    parts = re.split(r"(?<=[，。；：？！、])", text)
    lines = []
    units = "点年万亿千万百十%+倍张只家元块天"
    for p in parts:
        p = p.strip()
        while len(p) > maxlen:
            cut = maxlen
            if cut < len(p) and p[cut].isdigit() and p[cut - 1].isdigit():
                while cut > 0 and p[cut - 1].isdigit():
                    cut -= 1
            elif (cut < len(p) and cut > 0 and p[cut] in units
                  and p[cut - 1].isdigit()):
                cut += 1
            lines.append(p[:cut]); p = p[cut:]
        if p:
            lines.append(p)
    return lines

events = []
for i, (s, d, md) in enumerate(zip(segs, durs, mp3durs)):
    start = 0.0 if i == 0 else offsets[i - 1] + FADE
    lines = split_lines(s["text"])
    total = sum(len(l) for l in lines)
    t = start
    for l in lines:
        seg_len = md * len(l) / total
        events.append((t, min(t + seg_len, start + md), l))
        t += seg_len

def ts(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    ss, ms = int(sec % 60), int(round(sec % 1 * 100)) % 100
    return f"{h}:{m:02d}:{ss:02d}.{ms:02d}"

ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {SW}
PlayResY: {SH}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUB_FONT},{SUB_FS},{INK_ASS},&H00FFFFFF,&H00FFFFFF,&H00000000,1,0,0,0,100,100,0,0,1,2.6,0,2,{SUB_MLR},{SUB_MLR},{SUB_MV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
for a, b, l in events:
    ass += f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{l}\n"
open("subs.ass", "w", encoding="utf-8-sig").write(ass)

# ---------- 5. 烧字幕 ----------
run(["ffmpeg", "-y", "-i", "merged.mp4", "-vf", "ass=subs.ass",
     "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy",
     "final.mp4"])

total = dur_of("final.mp4")
print(f"DONE: {BASE}\\final.mp4  时长 {int(total//60)}分{total%60:.0f}秒")
