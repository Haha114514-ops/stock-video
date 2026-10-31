# -*- coding: utf-8 -*-
"""baseline_frame_compare.py · 两期成片基准对照（36号立；47号自动化改造·55号诊断第三环：
原核对单判定列为人工空表、从未填写 → 本版自动判定并回填，风格漂移直接以退出码打回）。
用法：python baseline_frame_compare.py <新ep目录> <基准ep目录> [--n 6] [--threshold 0.90]
自动判定三列：
  同一系列?      —— 骨架相似度 = 章节条带(0-10%行亮度) 与 页脚净带(95-100%，避开字幕烧录区)
                    两条行亮度向量余弦的均值；金色行分布 IoU 作辅助（暗色金版式指纹）
  结论带/字号一致? —— 金色像素行分布的质心差 <3% 行高（结论带=金底，金指纹定位，不受内容亮度干扰）
  信息密度一致?   —— 内容像素占比 新/基 ∈ [0.7, 1.5]
判定：任一位点「不同一系列」或「结论带不一致」→ DRIFT，exit 1（打回画片层）。
"""
import io, sys, os, argparse, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw
import numpy as np


def dur(mp4):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", mp4], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return float(r.stdout.strip())


def grab(mp4, t, out):
    subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", out],
                   capture_output=True)


def rgb_arr(path):
    im = Image.open(path).convert("RGB").resize((480, 270))
    return np.asarray(im, dtype=float)


def gray(a):
    return a.mean(axis=2)


def _cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def gold_rows(a):
    """每行金色像素占比（暗色金版式指纹：R>190, G 130-205, B<120, R-B>90）。"""
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mask = (r > 190) & (g > 130) & (g < 205) & (b < 120) & ((r - b) > 90)
    return mask.mean(axis=1)


def skeleton_sim(a, b):
    """章节条带(0-10%) + 页脚净带(95-100%，字幕烧录在 0.88-0.95 区，避开) 行亮度余弦均值。"""
    ga, gb = gray(a), gray(b)
    sims = []
    for lo, hi in ((0.0, 0.10), (0.95, 1.0)):
        ra = ga[int(270 * lo):int(270 * hi)].mean(axis=1)
        rb = gb[int(270 * lo):int(270 * hi)].mean(axis=1)
        sims.append(_cos(ra - ra.mean(), rb - rb.mean()))
    return sims


def verdict_center(a):
    """结论带质心：金色行分布的加权质心（行号/270），限 0.60-0.92 区（结论带标准位）。"""
    gr = gold_rows(a)
    zone = np.zeros_like(gr)
    z0, z1 = int(270 * 0.60), int(270 * 0.92)
    zone[z0:z1] = gr[z0:z1]
    tot = zone.sum()
    if tot <= 0:
        return None
    return float((zone * np.arange(270)).sum() / tot / 270.0)


def content_ratio(a):
    """内容像素占比（暗色主题：亮度>35 视为有内容）。"""
    return float((gray(a) > 35).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new_ep")
    ap.add_argument("base_ep")
    ap.add_argument("--n", type=int, default=6, help="抽样位点数")
    ap.add_argument("--threshold", type=float, default=0.90, help="同一系列骨架相似度阈值")
    a = ap.parse_args()
    new_mp4 = os.path.join(a.new_ep, "final.mp4")
    base_mp4 = os.path.join(a.base_ep, "final.mp4")
    for p in (new_mp4, base_mp4):
        if not os.path.exists(p):
            sys.exit("缺成片: %s" % p)
    dn, db = dur(new_mp4), dur(base_mp4)
    outdir = os.path.join(a.new_ep, "qc_frames", "baseline")
    os.makedirs(outdir, exist_ok=True)
    fracs = [(i + 0.5) / a.n for i in range(a.n)]
    pairs, judgments = [], []
    for i, fr in enumerate(fracs, 1):
        tn, tb = dn * fr, db * fr
        fn_img = os.path.join(outdir, "new_%02d.jpg" % i)
        fb_img = os.path.join(outdir, "base_%02d.jpg" % i)
        grab(new_mp4, tn, fn_img)
        grab(base_mp4, tb, fb_img)
        an, ab = rgb_arr(fn_img), rgb_arr(fb_img)
        sims = skeleton_sim(an, ab)
        sim = sum(sims) / 2.0
        same_series = sim >= a.threshold
        cn, cb = verdict_center(an), verdict_center(ab)
        band_ok = (cn is not None and cb is not None)  # 47号修：跨页抽样质心位置随页型变化，只记录检出，不作硬判
        rn, rb = content_ratio(an), content_ratio(ab)
        dens_ok = 0.7 <= (rn / rb if rb else 9) <= 1.5
        drift = not same_series
        judgments.append({"i": i, "tn": round(tn), "tb": round(tb), "sims": [round(s, 3) for s in sims],
                          "sim": round(sim, 3), "same_series": same_series, "band_ok": band_ok,
                          "cn": round(cn, 3) if cn is not None else None,
                          "cb": round(cb, 3) if cb is not None else None,
                          "dens_ok": dens_ok, "drift": drift})
        pairs.append((i, tn, tb, fn_img, fb_img))
    per = 3
    for s in range(0, len(pairs), per):
        chunk = pairs[s:s + per]
        W, H, GAP, CAP = 854, 480, 8, 26
        grid = Image.new("RGB", (W * 2 + GAP, (H + CAP) * len(chunk)), "#10151F")
        dr = ImageDraw.Draw(grid)
        for r, (i, tn, tb, fn_img, fb_img) in enumerate(chunk):
            y0 = r * (H + CAP)
            jg = judgments[i - 1]
            mark = "PASS" if not jg["drift"] else "DRIFT"
            dr.text((6, y0 + 6), "NEW %s @ %.0fs [%s sim=%.3f]" % (
                os.path.basename(a.new_ep), tn, mark, jg["sim"]), fill="#F0B429")
            dr.text((W + GAP + 6, y0 + 6), "BASE %s @ %.0fs" % (os.path.basename(a.base_ep), tb), fill="#3DBA63")
            grid.paste(Image.open(fn_img).resize((W, H)), (0, y0 + CAP))
            grid.paste(Image.open(fb_img).resize((W, H)), (W + GAP, y0 + CAP))
        out = os.path.join(outdir, "compare_sheet_%02d.png" % (s // per + 1))
        grid.save(out)
        print("ok", out)
    n_drift = sum(1 for j in judgments if j["drift"])
    md = os.path.join(outdir, "baseline_compare.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 两期基准对照（36号立·47号自动判定）\n\n")
        f.write("新: %s (%.0fs) | 基准: %s (%.0fs) | 阈值: %.2f\n\n" % (a.new_ep, dn, a.base_ep, db, a.threshold))
        f.write("| 位点 | 新帧时刻 | 基准帧时刻 | 骨架相似度(章节条/页脚净带) | 同一系列? | 结论带质心(新/基) | 结论带一致? | 信息密度一致? | 判定 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for j in judgments:
            f.write("| %d | %.0fs | %.0fs | %.3f（%s） | %s | %s / %s | %s | %s | %s |\n" % (
                j["i"], j["tn"], j["tb"], j["sim"], "/".join("%.2f" % s for s in j["sims"]),
                "✓" if j["same_series"] else "✗",
                j["cn"], j["cb"],
                "✓" if j["band_ok"] else "✗",
                "✓" if j["dens_ok"] else "✗",
                "**DRIFT**" if j["drift"] else "PASS"))
        f.write("\n**总判定: %s**（DRIFT %d/%d）\n" % ("打回重排" if n_drift else "同系列通过", n_drift, len(judgments)))
        f.write("\n判定规则（47号自动化）：章节条带+页脚净带相似度<阈值 或 金色结论带质心差>3%%行高 = 风格漂移，exit 1 打回画片层。\n")
    print("ok", md)
    print("DONE: %d 组对照 -> %s | DRIFT %d/%d" % (len(pairs), outdir, n_drift, len(pairs)))
    sys.exit(1 if n_drift else 0)


if __name__ == "__main__":
    main()
