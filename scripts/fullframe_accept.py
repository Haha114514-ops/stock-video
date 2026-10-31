# -*- coding: utf-8 -*-
"""
fullframe_accept.py —— SKILL 全量抽帧验收工具（2026-10-25·33号/34号）
成片每4秒一帧 → 感知哈希去重 → 逐卡验收核对单（替代旧"抽3帧人眼"）
用法:
  python fullframe_accept.py <成片.mp4> <输出目录> [--interval 4]
输出:
  <输出目录>/frames/f_XXXX.jpg   全部抽帧
  <输出目录>/frame_groups.json   去重组（代表帧/时间范围）
  <输出目录>/验收核对单.md        逐组人工核对行（叠印/碰撞/图窗/字幕/判定）
"""
import json, os, re, subprocess, argparse, warnings
warnings.filterwarnings('ignore')
from PIL import Image

HASH_T = 12

def ahash(im, size=16):
    im = im.convert('L').resize((size, size))
    px = list(im.getdata())
    avg = sum(px) / len(px)
    return [1 if p > avg else 0 for p in px]

def ham(a, b):
    return sum(x != y for x, y in zip(a, b))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('outdir')
    ap.add_argument('--interval', type=float, default=4.0)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.outdir, 'frames'), exist_ok=True)

    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', a.video],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    dur = float(json.loads(r.stdout)['format']['duration'])
    n = int(dur / a.interval) + 1
    print(f'成片 {dur:.1f}s，按 {a.interval}s 抽帧 ≈ {n} 张')

    # 分批抽帧（ffmpeg fps 滤镜一次完成）
    subprocess.run(['ffmpeg', '-v', 'quiet', '-i', a.video, '-vf', f'fps=1/{a.interval}',
                    '-q:v', '2', os.path.join(a.outdir, 'frames', 'f_%04d.jpg')], timeout=600)
    files = sorted(f for f in os.listdir(os.path.join(a.outdir, 'frames')) if f.endswith('.jpg'))

    groups = []
    for f in files:
        im = Image.open(os.path.join(a.outdir, 'frames', f))
        h = ahash(im)
        for g in groups:
            if ham(h, g['hash']) <= HASH_T:
                g['files'].append(f)
                break
        else:
            groups.append({'hash': h, 'files': [f]})

    out = []
    md = ['# 全量抽帧验收核对单', '',
          f'成片: {a.video}  |  抽帧间隔: {a.interval}s  |  帧: {len(files)}  |  唯一画面组: {len(groups)}', '',
          '逐组核对（每格填 ✓/✗/N/A，发现✗必须附本组代表帧路径）:', '',
          '| 组 | 代表帧 | 时间范围 | 卡片内容正确 | 无叠印 | 无碰撞 | 图窗/标签正确 | 字幕正常 | 判定 |',
          '|---|---|---|---|---|---|---|---|---|']
    for i, g in enumerate(groups):
        fs = g['files']
        t0 = (int(fs[0][2:6]) - 1) * a.interval
        t1 = (int(fs[-1][2:6]) - 1) * a.interval + a.interval
        out.append({'group': i, 'rep': fs[0], 't0': round(t0), 't1': round(t1),
                    'n': len(fs), 'files': fs})
        md.append(f'| g{i:02d} | {fs[0]} | {t0:.0f}-{t1:.0f}s | | | | | | |')
    json.dump(out, open(os.path.join(a.outdir, 'frame_groups.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    open(os.path.join(a.outdir, '验收核对单.md'), 'w', encoding='utf-8').write('\n'.join(md))
    print(f'唯一画面组: {len(groups)}；核对单: {os.path.join(a.outdir, "验收核对单.md")}')

if __name__ == '__main__':
    main()
