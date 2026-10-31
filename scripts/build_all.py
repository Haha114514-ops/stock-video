# -*- coding: utf-8 -*-
"""TTS -> 分段视频 -> 拼接 -> 烧字幕 -> 成品"""
import asyncio, json, os, re, subprocess, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
SUBS_ONLY = "--subs-only" in sys.argv       # 只重建字幕并重烧，复用 merged.mp4
ONLY = None                                  # --only=seg7b,seg9：只重渲点名段（G25·51号）
for _a in sys.argv[1:]:
    if _a.startswith("--only="):
        ONLY = set(x.strip() for x in _a.split("=", 1)[1].split(",") if x.strip())
BASE = _args[0] if _args else os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

import edge_tts

PAD = 0.5          # 每段末尾静音(秒)
FPS = 30

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"CMD FAILED: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout

def dur_of(path):
    out = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path])
    return float(json.loads(out)["format"]["duration"])

# ---------- 1. TTS ----------
cfg = json.load(open("segments.json", encoding="utf-8-sig"))
segs = cfg["segments"]
os.makedirs("tts", exist_ok=True)

# ---------- 0. 合成前自动质检门（2026-10-24 立：红灯即停，不许合成） ----------
import importlib.util as _ilu
_gf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_check.py")
_gspec = _ilu.spec_from_file_location("gate_check", _gf)
_gate = _ilu.module_from_spec(_gspec)
_gspec.loader.exec_module(_gate)
_gate.run_gate(BASE)

# 画布尺寸：从第一张 slide 自动识别（横屏1920x1080 / 竖屏1080x1920）
try:
    from PIL import Image
    SW, SH = Image.open(os.path.join("slides", segs[0]["slide"])).size
except Exception:
    SW, SH = 1920, 1080
print(f"canvas: {SW}x{SH}")

async def tts_all():
    for s in segs:
        mp3 = f"tts/seg{s['id']}.mp3"
        bnd = f"tts/seg{s['id']}.bounds.json"
        if os.path.exists(mp3) and os.path.getsize(mp3) > 1000:
            print("skip tts", mp3); continue
        rate = s.get("rate", cfg["rate"])          # 支持分段语速覆盖
        bounds = []
        comm = edge_tts.Communicate(s["text"], cfg["voice"], rate=rate,
                                    boundary="WordBoundary")
        with open(mp3, "wb") as fp:
            async for ch in comm.stream():
                if ch["type"] == "audio":
                    fp.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    bounds.append({"t": ch["offset"] / 1e7, "text": ch["text"]})
        json.dump(bounds, open(bnd, "w", encoding="utf-8"))
        print("tts ok", mp3, f"rate={rate}", f"{len(bounds)} bounds")

if not SUBS_ONLY:
    asyncio.run(tts_all())

# ---------- 2. 分段视频 / 3. 拼接 ----------
# G25 渲染分层缓存（51号立·64号诊断）：画片PNG+音频未变的段跳过重渲；
# --only=seg7b,seg9 点名段强制重渲。台账 segs/render_manifest.json。
import hashlib as _hl
def _md5f(p):
    try:
        return _hl.md5(open(p, "rb").read()).hexdigest()
    except Exception:
        return ""
_MANIFEST = os.path.join("segs", "render_manifest.json")
_man = {}
if os.path.exists(_MANIFEST):
    try:
        _man = json.load(open(_MANIFEST, encoding="utf-8-sig"))
    except Exception:
        _man = {}

if SUBS_ONLY:
    durs = [dur_of(f"tts/seg{s['id']}.mp3") for s in segs]
    print(f"subs-only: 复用 merged.mp4，{len(durs)} 段音频，跳过重编码")
else:

    os.makedirs("segs", exist_ok=True)
    durs = []

    def _seg_key(s):
        pngs = [s.get("slide")] + [st.get("img") for st in (s.get("states") or [])]
        return "|".join(f"{p}:{_md5f(os.path.join('slides', p))}" for p in pngs if p)

    def _norm(s):
        return "".join(ch for ch in s if (ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
                       and ch not in "·—…")

    for s in segs:
        mp3, mp4 = f"tts/seg{s['id']}.mp3", f"segs/seg{s['id']}.mp4"
        d = dur_of(mp3); durs.append(d)
        sid = str(s["id"])
        key = _seg_key(s) + "|" + _md5f(mp3)
        old_key = (_man.get(sid) or {}).get("key")
        if os.path.exists(mp4) and old_key == key and (ONLY is None or sid not in ONLY):
            print("skip seg", mp4, "(G25: 画片/音频未变)")
            continue
        if ONLY is not None and sid not in ONLY and os.path.exists(mp4):
            print("skip seg", mp4, "(--only 未点名)")
            continue
        states = s.get("states") or []
        if states:
            # 段内状态切换：states=[{at:"解说子串"| hold:秒, img:"xx.png"}]，按字级时间戳切图
            bp = f"tts/seg{s['id']}.bounds.json"
            bnds = json.load(open(bp, encoding="utf-8-sig")) if os.path.exists(bp) else []
            full = _norm("".join(b["text"] for b in bnds))
            cuts, imgs = [0.0], [s["slide"]]
            for st in states:
                if "hold" in st:
                    t = cuts[-1] + float(st["hold"])
                else:
                    pos = full.find(_norm(st["at"]))
                    if pos < 0 or not bnds:
                        print("state 未命中:", st["at"]); t = d
                    else:
                        # 命中「包含短语首字」的 token 起点（旧逻辑 acc>=pos 会跳到下一 token，
                        # 系统性慢半拍——31号审计 2.3 节实证）；提前 0.25s 让高亮与读音同步
                        acc, cue = 0, 0.0
                        for b in bnds:
                            blen = len(_norm(b["text"]))  # 52号修：与 full.find 的归一化流同尺，
                            if blen and acc + blen > pos:  # raw len 会因「6%」类 token 超前而提早命中
                                cue = float(b["t"]); break
                            acc += blen
                        t = cue - 0.25
                t = max(t, cuts[-1] + 0.08)
                cuts.append(min(t, d)); imgs.append(st["img"])
            parts = []
            n = len(cuts)
            for i in range(n):
                a = cuts[i]; b = max(cuts[i + 1] if i + 1 < n else d + PAD, a + 0.04)
                p = f"segs/seg{s['id']}_p{i}.mp4"
                run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", f"slides/{imgs[i]}",
                     "-t", f"{b - a:.3f}", "-vf", f"scale={SW}:{SH},format=yuv420p",
                     "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
                     "-crf", "20", p])
                parts.append(p)
            with open(f"segs/seg{s['id']}_parts.txt", "w", encoding="utf-8") as fp:
                for p in parts:
                    fp.write(f"file '{os.path.basename(p)}'\n")
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"segs/seg{s['id']}_parts.txt",
                 "-c", "copy", f"segs/seg{s['id']}_v.mp4"])
            run(["ffmpeg", "-y", "-i", f"segs/seg{s['id']}_v.mp4", "-i", mp3,
                 "-af", f"apad=pad_dur={PAD}", "-t", f"{d + PAD:.3f}",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mp4])
            print("seg ok (states)", mp4, f"{d:.1f}s, {len(imgs)} states")
        else:
            run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", f"slides/{s['slide']}",
                 "-i", mp3,
                 "-filter_complex", f"[0:v]scale={SW}:{SH},format=yuv420p[v];[1:a]apad=pad_dur={PAD}[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{d + PAD:.3f}",
                 "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20",
                 "-c:a", "aac", "-b:a", "192k", mp4])
            print("seg ok", mp4, f"{d:.1f}s")
        _man[sid] = {"key": key}

    # ---------- 3. 拼接 ----------
    with open("list.txt", "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"file 'segs/seg{s['id']}.mp4'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "merged.mp4"])
    json.dump(_man, open(_MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 4. 字幕（算法在 subs.py，改字幕别改这里） ----------
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "subs_engine", os.path.join(os.path.dirname(os.path.abspath(__file__)), "subs.py"))
SUBS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SUBS)

events, sub_stats = SUBS.build_events(segs, durs, maxlen=14 if SH > SW else 22)
cov_total = SUBS.report(sub_stats, events)   # 自检打印（2026-10-24 规：曾丢失调用，27号恢复）
_low = [x for x in sub_stats if x["cov"] < 0.85]
if cov_total < 0.90 or _low:
    sys.exit("GATE RED: 字幕覆盖率不达标（合计 %.1f%%，低于85%%的段 %s）——带病交付禁止烧录，修完再跑"
             % (cov_total * 100, [x["id"] for x in _low]))
ass = SUBS.header(SW, SH, cfg, sub_fs=cfg.get("sub_font"))
ass += SUBS.lines(events)

def ts(sec):
    return SUBS.ts(sec)

# ---------- 4.6 数据蹦出层（callouts.json 可选：{slide文件名: [{match,text,x,y}]}） ----------
pop_events = []
hl_events = []
cos = {}
if os.path.exists("callouts.json"):
    try:
        cos = json.load(open("callouts.json", encoding="utf-8-sig"))
    except Exception as e:
        print("callouts.json 解析失败:", e); cos = {}
t0 = 0.0
for s, d in zip(segs, durs):
    co_list = cos.get(s["slide"], [])
    if co_list:
        bp = f"tts/seg{s['id']}.bounds.json"
        bnds = json.load(open(bp, encoding="utf-8-sig")) if os.path.exists(bp) else []
        toks = [(norm_spoken(b["text"]), float(b["t"])) for b in bnds]
        toks = [(tx, tt) for tx, tt in toks if tx]
        full = "".join(tx for tx, _ in toks)
        tok_spans, posn = [], 0
        for tx, tt in toks:
            tok_spans.append((posn, posn + len(tx), tt))
            posn += len(tx)
        def t_at(p):
            for a, b_, tt in tok_spans:
                if a <= p < b_:
                    return tt
            return tok_spans[-1][2] if tok_spans else 0.0
        for co in co_list:
            m_nm = norm_spoken(co.get("match", ""))
            pos = full.find(m_nm) if m_nm else -1
            if pos < 0 or not bnds:
                print("callout 未命中:", co.get("match")); continue
            acc, cue = 0, 0.0
            for b in bnds:
                blen = len(_norm(b["text"]))  # 52号修：同 states，归一化长度对齐 find 流
                if blen and acc + blen > pos:
                    cue = b["t"]; break
                acc += blen
            st = t0 + max(cue - 0.12, 0.0)
            en = min(st + co.get("keep", 3.0), t0 + d)
            if "rect" in co:
                hl_events.append((st, en, co))
            else:
                pop_events.append((st, en, co))
    t0 += d + PAD
pop_events.sort(key=lambda e: e[0])
trimmed = []
for i, (st, en, co) in enumerate(pop_events):
    if i + 1 < len(pop_events):
        en = min(en, pop_events[i + 1][0] - 0.05)
    if en > st:
        trimmed.append((st, en, co))
pop_events = trimmed
print("pop events:", len(pop_events), "| hl events:", len(hl_events))
for st, en, co in pop_events:
    ass += (f"Dialogue: 1,{ts(st)},{ts(en)},Pop,,0,0,0,,"
            f"{{\\an2\\pos({co['x']},{co['y']})\\fscx20\\fscy20"
            f"\\t(0,180,\\fscx108\\fscy108)}}{co['text']}\n")
for st, en, co in hl_events:
    x, y, w_, h_ = co["rect"]
    cc = co.get("color", "&H0029B4F0")
    ass += (f"Dialogue: 2,{ts(st)},{ts(en)},Pop,,0,0,0,,"
            f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c{cc}\\1a&H60&}}"
            f"m {x} {y} l {x+w_} {y} l {x+w_} {y+h_} l {x} {y+h_}{{\\p0}}\n")
open("subs.ass", "w", encoding="utf-8-sig").write(ass)

# ---------- 5. 烧字幕（G25：merged/字幕均未变则跳过重编码，51号） ----------
_burn_skip = False
if not SUBS_ONLY:
    _bkey = {"merged": _md5f("merged.mp4"), "subs": _md5f("subs.ass")}
    if os.path.exists("final.mp4") and (_man.get("#burn") or {}).get("merged") == _bkey["merged"] \
            and (_man.get("#burn") or {}).get("subs") == _bkey["subs"]:
        print("skip burn (G25: merged/字幕未变，final.mp4 仍新鲜)")
        _burn_skip = True
if not _burn_skip:
    run(["ffmpeg", "-y", "-i", "merged.mp4", "-vf", "ass=subs.ass",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy", "final.mp4"])
    if not SUBS_ONLY:
        _man["#burn"] = {"merged": _md5f("merged.mp4"), "subs": _md5f("subs.ass")}
        json.dump(_man, open(_MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

total = dur_of("final.mp4")
print(f"DONE: {BASE}\\final.mp4  时长 {int(total//60)}分{total%60:.0f}秒")
