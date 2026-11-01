# -*- coding: utf-8 -*-
"""build v4：GSAP + 无头浏览器逐帧渲染管线（帧精确动效，零抖动）
流程：TTS → 时长 → timing spec → Playwright 驱动无头浏览器逐帧截图 → ffmpeg拼帧
     → 音轨拼接 → 混流 → ASS大字幕（浅底深字）烧录 → final.mp4
用法：python build_v4.py <工程目录>
浏览器：依次试本机 Chrome、Edge，再退到 playwright 自带的 chromium（playwright install chromium）。
字幕：ffmpeg 没带 libass 时（Homebrew 默认就没带）不烧字幕，出 final.mp4 + 同名 .srt 外挂，并提示怎么换 ffmpeg。
"""
import asyncio, glob, json, os, re, subprocess, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
    sys.exit(__doc__)
BASE = os.path.abspath(sys.argv[1])
os.chdir(BASE)

import edge_tts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sysenv
from sysenv import SUB_FONT   # 字幕字体（libass 按名字找），按本机取

PAD = 0.25
FPS = 30

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        sys.exit(f"CMD FAILED: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout

def dur_of(path):
    out = run(sysenv.ffprobe("-v", "quiet", "-print_format", "json", "-show_format",
                             path))
    return float(json.loads(out)["format"]["duration"])

# ---------- 1. TTS ----------
cfg = json.load(open("segments.json", encoding="utf-8-sig"))
segs = cfg["segments"]
os.makedirs("tts", exist_ok=True)

TXT_LOG = "tts/tts_text.json"   # 记下每段配音时的文本 / 语速 / 声音：改了旁白自动重配，不会复用旧音频

async def tts_all():
    old = json.load(open(TXT_LOG, encoding="utf-8")) if os.path.exists(TXT_LOG) else {}
    new = {}
    for s in segs:
        mp3 = f"tts/seg{s['id']}.mp3"
        rate = s.get("rate", cfg["rate"])
        key = [s["text"], cfg["voice"], rate]; new[mp3] = key
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1000 and old.get(mp3) == key:
            print("skip tts", mp3); continue
        for i in range(5):
            try:
                await edge_tts.Communicate(s["text"], cfg["voice"], rate=rate).save(mp3); break
            except Exception as e:
                print("retry tts", mp3, e); await asyncio.sleep(2 + 2 * i)
        else:
            sys.exit(f"TTS 失败: {mp3}")
        print("tts ok", mp3, f"rate={rate}")
    with open(TXT_LOG, "w", encoding="utf-8") as fp:
        json.dump(new, fp, ensure_ascii=False, indent=0)

asyncio.run(tts_all())

durs, mp3durs = [], []
for s in segs:
    d = dur_of(f"tts/seg{s['id']}.mp3")
    mp3durs.append(d)
    durs.append(d + PAD)
starts = [sum(durs[:i]) for i in range(len(durs))]
total = sum(durs)
n_frames = round(total * FPS)
print(f"total {total:.2f}s  {n_frames} frames @ {FPS}fps")

# ---------- 2. timing spec（cue表外置：工程目录 cues.json） ----------
cue_path = os.path.join(BASE, "cues.json")
if not os.path.exists(cue_path):
    sys.exit("缺少 cues.json（每段入场cue表）：{id: [[rel秒, 选择器, 类型, 参数?], ...]}")
CUE = json.load(open(cue_path, encoding="utf-8-sig"))
cues = []
for i, s in enumerate(segs):
    st = starts[i]
    for c in CUE[str(s["id"])]:
        cues.append([c[1], c[2], round(st + c[0], 3)] + list(c[3:]))
spec = {"sections": [{"id": f"s{s['id']}", "start": round(starts[i], 3),
                      "dur": round(durs[i], 3)} for i, s in enumerate(segs)],
        "cues": cues}
print(f"spec: {len(cues)} cues")

# ---------- 3. 逐帧渲染（Playwright + Edge） ----------
from playwright.sync_api import sync_playwright

web = Path(BASE, "web", "index.html")
if not web.exists():
    sys.exit(f"缺少 {web}：复制 scripts/web_template_ep03.html 到 web/index.html，gsap.min.js 放在同一目录")
FRAMES = os.path.join(BASE, "frames")
os.makedirs(FRAMES, exist_ok=True)
# 断点续渲：从 00000 起连续存在的帧保留，只渲缺的部分；时间轴 / cue / 页面改过就全部重渲
SPEC_LOG = os.path.join(FRAMES, "_spec.json")
stamp = json.dumps([spec, web.stat().st_mtime], ensure_ascii=False, sort_keys=True)
if not os.path.exists(SPEC_LOG) or open(SPEC_LOG, encoding="utf-8").read() != stamp:
    for fn in glob.glob(os.path.join(FRAMES, "*.png")):
        os.remove(fn)
    open(SPEC_LOG, "w", encoding="utf-8").write(stamp)
k0 = 0
while os.path.exists(os.path.join(FRAMES, f"{k0:05d}.png")):
    k0 += 1
if k0:
    print(f"resume: keep {k0} frames, render {k0}..{n_frames-1}")

def launch(p):
    """本机 Chrome → Edge → playwright 自带 chromium；STOCK_VIDEO_BROWSER 可指定浏览器可执行文件"""
    exe = os.environ.get("STOCK_VIDEO_BROWSER")
    tries = [dict(executable_path=exe)] if exe else []
    tries += [dict(channel="chrome"), dict(channel="msedge"), {}]
    err = None
    for kw in tries:
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception as e:
            err = e
    sys.exit(f"启动不了浏览器：装 Chrome，或跑 playwright install chromium\n{err}")

with sync_playwright() as p:
    browser = launch(p)
    page = browser.new_page(viewport={"width": 1080, "height": 1920},
                            device_scale_factor=1)
    page.goto(web.as_uri())   # as_uri 会转义中文和空格，macOS / Windows 路径都对
    page.evaluate("async () => { await document.fonts.ready; }")
    page.evaluate("spec => window.init(spec)", spec)
    for k in range(k0, n_frames):
        page.evaluate("t => window.seek(t)", round(k / FPS, 4))
        page.screenshot(path=os.path.join(FRAMES, f"{k:05d}.png"))
        if k % 300 == 0:
            print(f"render {k}/{n_frames}")
    browser.close()
print("render done")

# ---------- 4. 拼帧 + 音轨 + 混流 ----------
run(sysenv.ffmpeg("-y", "-framerate", str(FPS), "-i",
                  os.path.join(FRAMES, "%05d.png"), "-frames:v", str(n_frames),
                  "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                  "-pix_fmt", "yuv420p", "full.mp4"))
print("full.mp4 encoded")

ainputs, afilters = [], []
for i, s in enumerate(segs):
    ainputs += ["-i", f"tts/seg{s['id']}.mp3"]
    afilters.append(f"[{i}:a]apad=pad_dur={PAD}[a{i}]")
afilters.append("".join(f"[a{i}]" for i in range(len(segs))) +
                f"concat=n={len(segs)}:v=0:a=1[aout]")
run(sysenv.ffmpeg("-y", *ainputs, "-filter_complex", ";".join(afilters),
                  "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "audio.m4a"))
run(sysenv.ffmpeg("-y", "-i", "full.mp4", "-i", "audio.m4a",
                  "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
                  "-shortest", "merged.mp4"))
print("merged.mp4 ok")

# ---------- 5. 字幕（浅底：深墨字+白描边；时间轴=各段起点累计） ----------
SUB_MAXLEN = 9
SUB_FS = max(40, round(1080 * 0.062))
SUB_MV = round(1920 * 0.075)
SUB_MLR = round(1080 * 0.045)

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
for i, s in enumerate(segs):
    lines = split_lines(s["text"])
    t = starts[i]
    md = mp3durs[i]
    tot = sum(len(l) for l in lines)
    for l in lines:
        seg_len = md * len(l) / tot
        events.append((t, min(t + seg_len, starts[i] + md), l))
        t += seg_len

def ts(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    ss, ms = int(sec % 60), int(round(sec % 1 * 100)) % 100
    return f"{h}:{m:02d}:{ss:02d}.{ms:02d}"

ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUB_FONT},{SUB_FS},&H00262B2F,&H00FFFFFF,&H00FFFFFF,&H00000000,1,0,0,0,100,100,0,0,1,2.6,0,2,{SUB_MLR},{SUB_MLR},{SUB_MV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
for a, b, l in events:
    ass += f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{l}\n"
open("subs.ass", "w", encoding="utf-8-sig").write(ass)

def srt_ts(sec):
    ms = int(round(sec * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

with open("final.srt", "w", encoding="utf-8") as fp:
    for k, (a, b, l) in enumerate(events, 1):
        fp.write(f"{k}\n{srt_ts(a)} --> {srt_ts(b)}\n{l}\n\n")

# ---------- 6. 烧字幕 ----------
if sysenv.has_libass():
    run(sysenv.ffmpeg("-y", "-i", "merged.mp4", "-vf", "ass=subs.ass",
                      "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy",
                      "final.mp4"))
else:
    os.replace("merged.mp4", "final.mp4")
    print("注意：本机 ffmpeg 没带 libass，字幕没烧进画面，外挂字幕在 final.srt。"
          "要烧字幕：macOS 用 brew tap homebrew-ffmpeg/ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg，"
          "或设 STOCK_VIDEO_FFMPEG 指向带 libass 的 ffmpeg 后重跑（帧和配音会复用）。")

total_d = dur_of("final.mp4")
print(f"DONE: {os.path.join(BASE, 'final.mp4')}  时长 {int(total_d//60)}分{total_d%60:.0f}秒")
