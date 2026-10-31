# -*- coding: utf-8 -*-
"""
cue_timing_check.py —— SKILL C9 条款检查器（2026-10-25·33号/34号）
对 segments.json 每个 states cue：
  1) 定位 at 词在成片中的口播时刻（tts 字级边界 + subs.ass 段起点对齐）
  2) 在 口播时刻+0.5秒 处抽帧
  3) 感知哈希比对声明状态图 / 上一状态图
  4) 红黄牌：绿=已切换(≤0.5s) / 红=滞后(仍是上一状态) / 黄=匹配不上待人工
用法:
  python cue_timing_check.py <ep目录> [--tol 0.5] [--out qc_timing.json]
输出: 控制台表格 + qc_timing.json（供 regression_check.py 对照）
"""
import json, os, re, sys, subprocess, tempfile, argparse
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

TOL_DEFAULT = 0.5
HASH_T = 12          # 感知哈希汉明距阈值
CROP_BOTTOM = 0.85   # 哈希前裁掉底部15%（字幕带）
PROBES = [0.8, 1.2, 1.8, 2.5, 3.5]   # 红牌后测实际切换时刻的探针

def norm(s):
    return re.sub(r'[^\w]+', '', s or '')

def ahash(path, tmp):
    """裁底部字幕带后 16x16 感知哈希（快速预筛用）"""
    im = Image.open(path).convert('L')
    w, h = im.size
    im = im.crop((0, 0, w, int(h * CROP_BOTTOM))).resize((16, 16))
    px = list(im.getdata())
    avg = sum(px) / len(px)
    return [1 if p > avg else 0 for p in px]

def madiff(path_a, path_b, tmp):
    """480x270 灰度平均绝对差（小差异状态图的可分辨判定，2026-10-25·34号二轮修正）"""
    ims = []
    for p in (path_a, path_b):
        im = Image.open(p).convert('L')
        w, h = im.size
        ims.append(im.crop((0, 0, w, int(h * CROP_BOTTOM))).resize((480, 270)))
    pa, pb = list(ims[0].getdata()), list(ims[1].getdata())
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)

def ham(a, b):
    return sum(x != y for x, y in zip(a, b))

def grab(video, t, tmp):
    out = os.path.join(tmp, 'g.jpg')
    if os.path.exists(out):
        os.remove(out)
    subprocess.run(['ffmpeg', '-v', 'quiet', '-ss', f'{max(t,0):.2f}', '-i', video,
                    '-frames:v', '1', '-q:v', '2', '-y', out], timeout=30)
    return out if os.path.exists(out) else None

def parse_ass_subs(path):
    """返回 [(start_sec, norm_text)] 按时间序"""
    ev = []
    for line in open(path, encoding='utf-8-sig'):
        if not line.startswith('Dialogue:'):
            continue
        parts = line.split(',', 9)
        if len(parts) < 10:
            continue
        h, m, rest = parts[1].split(':')
        start = int(h) * 3600 + int(m) * 60 + float(rest)
        ev.append((start, norm(parts[9])))
    ev.sort()
    return ev

def seg_offsets_by_segments(ep, segments):
    """首选锚定：segs/segN.mp4 时长累加（34号二轮修正，硬切拼接下=精确段起点；
    subs.ass 文本匹配在个别段（如 seg9）会偏早数秒，降为 fallback）"""
    offs, t, ok = {}, 0.0, True
    for s in segments:
        sid = s['id']
        fp = os.path.join(ep, 'segs', f'seg{sid}.mp4')
        offs[sid] = round(t, 2)
        if os.path.exists(fp):
            t += dur(fp)
        else:
            ok = False
    return offs, ok

def dur(fp):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', fp],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return float(json.loads(r.stdout)['format']['duration'])

def seg_offsets(subs, segments):
    """fallback 锚定：字幕事件顺序匹配"""
    off, ptr = {}, 0
    for seg in segments:
        nt = norm(seg['text'])
        for i in range(ptr, len(subs)):
            st, tx = subs[i]
            if len(tx) >= 6 and tx in nt:
                off[seg['id']] = st
                ptr = i + 1
                break
        else:
            off[seg['id']] = None
    return off

def cue_time_in_seg(tokens, text, at, search_from):
    """把 at 子串映射到字级边界：返回 (词起点秒, 词序号) 或 None"""
    tn = [norm(w.get('text', '')) for w in tokens]
    full, char_tok = '', []
    for i, s in enumerate(tn):
        for _ in s:
            char_tok.append(i)
        full += s
    nt, na = norm(text), norm(at)
    pos = full.find(na, search_from)
    if pos < 0:
        pos = full.find(na)          # 兜底从头找
        if pos < 0:
            return None
    if pos + len(na) > len(char_tok):
        return None
    tok_i = char_tok[pos]
    return tokens[tok_i].get('t', 0.0), tok_i

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('epdir')
    ap.add_argument('--tol', type=float, default=TOL_DEFAULT)
    ap.add_argument('--out', default=None, help='默认 <epdir>/qc_timing.json（51号：产物落工程，防污染工具库——64号实测曾写进用户库）')
    ap.add_argument('--video', default=None, help='成片路径，默认 <epdir>/final.mp4')
    a = ap.parse_args()

    ep = a.epdir
    video = a.video or os.path.join(ep, 'final.mp4')
    seg = json.load(open(os.path.join(ep, 'segments.json'), encoding='utf-8-sig'))
    offs, seg_anchor_ok = seg_offsets_by_segments(ep, seg['segments'])
    anchor_mode = 'segs累加' if seg_anchor_ok else 'subs匹配(fallback)'
    if not seg_anchor_ok:
        subs = parse_ass_subs(os.path.join(ep, 'subs.ass'))
        offs = seg_offsets(subs, seg['segments'])
    tmp = tempfile.mkdtemp(prefix='c9_')
    print(f'锚定方式: {anchor_mode}')

    rows, misses = [], []
    for s in seg['segments']:
        sid = s['id']
        states = s.get('states') or []
        if not states:
            continue
        bf = os.path.join(ep, 'tts', f'seg{sid}.bounds.json')
        if not os.path.exists(bf) or offs.get(sid) is None:
            misses.append((sid, '缺bounds或段起点未定位'))
            continue
        tokens = json.load(open(bf, encoding='utf-8-sig'))
        base_img = os.path.join(ep, 'slides', s.get('slide', ''))
        prev_img = base_img
        search_from = 0
        prev_t = offs[sid]
        for st in states:
            if 'at' in st:
                hit = cue_time_in_seg(tokens, s['text'], st['at'], search_from)
                if hit is None:
                    rows.append(dict(seg=sid, at=st['at'], img=st['img'], verdict='YELLOW',
                                     note='at未命中字级边界'))
                    misses.append((sid, f"at未命中: {st['at'][:20]}"))
                    continue
                cue_t, tok_i = hit
                search_from = sum(len(norm(w.get('text', ''))) for w in tokens[:tok_i + 1])
            else:                                # hold 型：距上一 cue 秒数
                cue_t = prev_t + float(st.get('hold', 0.14))
            prev_t = cue_t
            abs_t = offs[sid] + cue_t
            new_img = os.path.join(ep, 'slides', st['img'])
            deadline = abs_t + a.tol
            f_dead = grab(video, deadline, tmp)
            if f_dead is None or not os.path.exists(new_img):
                rows.append(dict(seg=sid, at=st['at'], img=st['img'], verdict='YELLOW',
                                 note='抽帧失败或状态图缺失', t_abs=round(abs_t, 2)))
                continue
            h_dead = ahash(f_dead, tmp)
            h_new = ahash(new_img, tmp)
            h_prev = ahash(prev_img, tmp) if os.path.exists(prev_img) else None
            # 相对判定（34号二轮修正）：小差异状态图（仅移动金点/一行高亮）在16x16哈希下
            # 互相距离也接近，改用 480x270 MAE 的相对远近（margin=0.5 灰度级）
            MARGIN = 0.5
            if h_prev is None:
                verdict = 'PASS' if ham(h_dead, h_new) <= HASH_T else 'YELLOW'
            else:
                p_dead = os.path.join(tmp, 'dead_ref.jpg')
                os.replace(f_dead, p_dead)
                d_new = madiff(p_dead, new_img, tmp)
                d_prev = madiff(p_dead, prev_img, tmp)
                if d_new <= d_prev - MARGIN:
                    verdict = 'PASS'
                elif d_prev < d_new - MARGIN:
                    verdict = 'RED'
                else:
                    verdict = 'YELLOW'
            if verdict == 'PASS':
                rows.append(dict(seg=sid, at=st['at'], img=st['img'], verdict='PASS',
                                 t_abs=round(abs_t, 2), lag=f'≤{a.tol}',
                                 d_new=round(d_new, 2), d_prev=round(d_prev, 2)))
            elif verdict == 'RED':
                lag = None
                for p in PROBES:             # 测实际切换时刻
                    fp = grab(video, abs_t + p, tmp)
                    if fp:
                        fp2 = os.path.join(tmp, 'probe.jpg')
                        os.replace(fp, fp2)
                        if madiff(fp2, new_img, tmp) < madiff(fp2, prev_img, tmp) - MARGIN:
                            lag = round(abs_t + p - abs_t, 2)
                            break
                rows.append(dict(seg=sid, at=st['at'], img=st['img'], verdict='RED',
                                 t_abs=round(abs_t, 2), lag=lag if lag else f'>{PROBES[-1]}',
                                 note=f'滞后：+{a.tol}s 仍更接近上一状态',
                                 d_new=round(d_new, 2), d_prev=round(d_prev, 2)))
            else:
                rows.append(dict(seg=sid, at=st['at'], img=st['img'], verdict='YELLOW',
                                 t_abs=round(abs_t, 2), note='帧与新/旧状态距离接近，人工复核',
                                 d_new=round(d_new, 2), d_prev=round(d_prev, 2)))
            prev_img = new_img

    red = sum(1 for r in rows if r['verdict'] == 'RED')
    yel = sum(1 for r in rows if r['verdict'] == 'YELLOW')
    pas = sum(1 for r in rows if r['verdict'] == 'PASS')
    print(f"\n== C9 cue时刻检查 == 共{len(rows)} cue | 绿{pas} 红{red} 黄{yel} | 容差{a.tol}s | 未定位{len(misses)}")
    for r in rows:
        flag = {'PASS': '绿', 'RED': '红', 'YELLOW': '黄'}[r['verdict']]
        print(f"[{flag}] seg{r['seg']:>4} @ {r.get('t_abs','-'):>7}s  {r['at'][:24]:<26} {r.get('note','')}")
    for m in misses:
        print(f"[缺] {m[0]}: {m[1]}")
    out = a.out or os.path.join(ep, 'qc_timing.json')
    json.dump({'video': video, 'tol': a.tol, 'anchor': anchor_mode, 'rows': rows, 'misses': misses},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出', out)

    # C9b 语义核对单：时刻维度查不出"状态图内容与cue词错位"（31/32号教训：
    # s6a_3/s6a_4两图装反，切换准时但内容错位），自动生成 at×状态图对照表供人工2秒/条核验
    sheet = out.replace('.json', '_语义核对单.md')
    md = ['# C9b 状态图语义核对单', '',
          '逐条核对：**at 词说的是什么 → 状态图里亮的是不是它**。错位=红（时刻准时但内容错），2秒/条。', '',
          '| seg | at词 | 状态图 | 语义一致? |', '|---|---|---|---|']
    for r in rows:
        md.append(f"| {r['seg']} | {r['at']} | {r['img']} | |")
    open(sheet, 'w', encoding='utf-8').write('\n'.join(md))
    print('已写出', sheet)
    sys.exit(1 if red else 0)

if __name__ == '__main__':
    main()
