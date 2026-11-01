# -*- coding: utf-8 -*-
"""review_pack.py —— 给审片人准备材料（不判断好坏，只把要看的东西摆出来）

    python review_pack.py <工程目录> [--video 成片.mp4] [--out 输出目录] [--facts facts.json]

输出到 <工程>/review/（或 --out）：
  ch_XX.png      每章一张拼图：每句话开口后 1.5 秒一帧 + 章末一帧，帧上标成片时间（按 timeline.json 精确定位）
  审片包.md      片长与章节表、每章旁白全文、静止段（≥3 秒不动）、旁白数字和 facts.json 对账、带推断词的句子

自查问题由作者对着本目录回答（57号补丁一删了观众审片子代理）；口径审片 57号补丁五起移到文字方案阶段，这里只留给"确认后改过的句子"复核用。
审片包.md 另有：旁白数字 ↔ facts 说法对照（facts.json 的 labels，见 components.put）、推算句、两组审片问题。
"""
import os, sys, re, json, glob, runpy, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sysenv
INFER = (r'信号|说明|意味着|因为|所以|导致|原因|看来|看起来|似乎|显然|一定|必然|推测|待验证|可能|等于|相当于|其实|'
         r'白得|白送|算进去|定价|市场(在|还在|先)|打不破|打破|解释不了')
CALC = r'推算|假设|年化|大约|约\d|左右|花完|撑'


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')


def mmss(x):
    return f'{int(x // 60)}:{x % 60:04.1f}'


def scene_names(root, n):
    """从 video.py 的 M.setup(scenes=...) 读章节名；读不到就用序号"""
    try:
        sys.argv = ['video.py']
        g = runpy.run_path(os.path.join(root, 'video.py'), run_name='review_pack')
        sc = g['M'].C['scenes']
        if len(sc) == n: return [s[0] for s in sc], [list(s[1]) for s in sc], g['M']
    except Exception as e:
        print('读不到 video.py 的章节名：', e)
    return [f'第{i}章' for i in range(n)], None, None


def grab(video, t, path):
    # -ss 放在 -i 前：按时间精确定位（不要用 fps 滤镜抽帧，它会取到约 10 秒后的画面）
    r = run(sysenv.ffmpeg('-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1', '-vf', 'scale=640:-1', path))
    return r.returncode == 0 and os.path.exists(path)


def sheets(video, tl, names, out):
    from PIL import Image, ImageDraw, ImageFont
    fp, fi = sysenv.font_file('b'); fnt = ImageFont.truetype(fp, 22, index=fi)
    tmp = os.path.join(out, '_f'); os.makedirs(tmp, exist_ok=True)
    paths = []
    for si, sc in enumerate(tl):
        ts = [min(b + 1.5, sc['T'] - 0.6) for b in sc['beats']] + [sc['T'] - 0.6]
        ims = []
        for k, t in enumerate(ts):
            p = os.path.join(tmp, f'{si:02d}_{k:02d}.png')
            if not grab(video, sc['off'] + t, p): continue
            im = Image.open(p).convert('RGB'); d = ImageDraw.Draw(im)
            lab = f'{mmss(sc["off"] + t)}  第{k + 1}句' if k < len(sc['beats']) else f'{mmss(sc["off"] + t)}  章末'
            d.rectangle((0, 0, d.textlength(lab, font=fnt) + 16, 32), fill=(0, 0, 0))
            d.text((8, 3), lab, font=fnt, fill=(255, 220, 0)); ims.append(im)
        if not ims: continue
        cols = 3; rows = (len(ims) + cols - 1) // cols; w, h = ims[0].size
        sh = Image.new('RGB', (cols * w, rows * h + 44), (0, 0, 0)); d = ImageDraw.Draw(sh)
        d.text((10, 8), f'{si:02d} {names[si]}   {mmss(sc["off"])} ~ {mmss(sc["off"] + sc["T"])}', font=fnt, fill=(255, 255, 255))
        for i, im in enumerate(ims): sh.paste(im, ((i % cols) * w, 44 + (i // cols) * h))
        p = os.path.join(out, f'ch_{si:02d}.png'); sh.save(p); paths.append(p)
    for fn in glob.glob(os.path.join(tmp, '*.png')): os.remove(fn)
    os.rmdir(tmp)
    return paths


def freezes(video):
    # 只量内容区（y 120~920），裁掉片头条、字幕和进度条：字幕一直在换，整帧量会把"只有章标题"的十几秒算成在动
    r = run(sysenv.ffmpeg('-v', 'info', '-i', video, '-vf', 'crop=iw:ih*800/1080:0:ih*120/1080,freezedetect=n=0.001:d=3', '-an', '-f', 'null', '-'))
    st = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', r.stderr)]
    du = [float(x) for x in re.findall(r'freeze_duration: ([\d.]+)', r.stderr)]
    return list(zip(st, du))


def flat_numbers(o, acc):
    if isinstance(o, dict):
        for v in o.values(): flat_numbers(v, acc)
    elif isinstance(o, list):
        for v in o: flat_numbers(v, acc)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        acc.append(abs(float(o)))
    return acc


def num_ok(s, vals):
    """旁白里的数字 s（字符串）能否在 facts 里找到：按它写出的小数位四舍五入比较，也试 比例→百分数"""
    d = len(s.split('.')[1]) if '.' in s else 0; x = float(s)
    for v in vals:
        for c in (v, v * 100):
            if round(c, d) == x: return True
            if d == 0 and abs(c - x) <= 0.5: return True
    return False


def flat_paths(o, pre='', acc=None):
    """facts 里每个数和它的键路径（'val.hi1'、'annual.3.np'）"""
    acc = [] if acc is None else acc
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('labels', 'quotes', 'series', 'price'): continue     # 说法本身、画图用的长序列不参与匹配
            flat_paths(v, f'{pre}.{k}' if pre else str(k), acc)
    elif isinstance(o, list):
        for i, v in enumerate(o): flat_paths(v, f'{pre}.{i}', acc)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        acc.append((pre, float(o)))
    return acc


def _nums(s):
    for m in re.finditer(r'(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])', s):
        n = m.group(1); tail = s[m.end():m.end() + 2]
        if re.fullmatch(r'(19|20)\d\d', n) or tail[:1] in ('月', '日', '号') or (tail[:1] == '年' and len(n) == 4):
            continue
        yield m, n


def repeats(lines_by_scene, k=3):
    """同一个数在 ≥k 句里念过（57号补丁一，接替观众审片"同一个数说了好几遍"）：一个数念一遍就够，结论只说一遍"""
    seen = {}
    for si, lines in enumerate(lines_by_scene):
        for li, s in enumerate(lines):
            for _, n in set(_nums(s)):
                if len(n.replace('.', '')) < 2: continue          # 1、3 这类太常见
                seen.setdefault(n, []).append((si, li))
    return sorted([(n, w) for n, w in seen.items() if len(w) >= k], key=lambda x: -len(x[1]))


def numbers(lines_by_scene, facts):
    vals = flat_numbers(facts, [])
    miss = []
    for si, lines in enumerate(lines_by_scene):
        for li, s in enumerate(lines):
            for m, n in _nums(s):
                if not num_ok(n, vals): miss.append((si, li, n, s))
    return miss


def matches(n, paths):
    """旁白数字 n 能对上的 facts 键（按写出的小数位比较，也试 比例→百分数、百万→亿 / 万）"""
    d = len(n.split('.')[1]) if '.' in n else 0; x = float(n)
    for scale in (1, 100, 0.01):                 # 先找原值对上的；没有再试 比例→百分数、百万→亿，避免 3.2% 撞上 3.16 亿
        out = [p for p, v in paths if round(abs(v) * scale, d) == x and (d > 0 or x >= 10)]
        if out: return out
    return []


def label_table(lines_by_scene, facts):
    """旁白里每个数：它前面的说法（念出来的那半句）↔ facts 里对上的键和冻结的说法。
    数对、说法错（"一年前 6.71"其实是区间最高点）只有并排看才查得出。没有冻结说法的键标"（无说法）"。"""
    paths = flat_paths(facts); labels = facts.get('labels', {}); rows = []
    for si, lines in enumerate(lines_by_scene):
        for li, s in enumerate(lines):
            for m, n in _nums(s):
                ks = matches(n, paths)
                if not ks: continue
                ctx = s[max(0, m.start() - 16):m.start()] + n + s[m.end():m.end() + 3]     # 说法常在前一个逗号之前（"一年前，……6.71"）
                ks = sorted(ks, key=lambda k: k not in labels)[:4]          # 有说法的排前面，但没说法的也列出来，免得错配
                rows.append((si, li, ctx, '；'.join(f'{k} = {labels[k]}' if k in labels else f'{k}（无说法）' for k in ks)))
    return rows, bool(labels)


BANNED = r'买入|卖出|加仓|减仓|抄底|满仓|清仓|目标价'


def still_max():
    """单段静止上限，从 motion.py 的 STILL_MAX 读（一处定义，preview / 审片包 / plan_check 共用）"""
    try:
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'motion.py'), encoding='utf-8').read()
        return float(re.search(r'STILL_MAX\s*=\s*[^\n]*?([\d.]+)\s*$', src, re.M).group(1))
    except Exception:
        return 7.0


def redlines(lines_by_scene, pics):
    """红线（57号补丁七）：文字方案和成片共用。pics[si] = 第 si 章画面上的文字（文字方案的画面列；成片阶段传 video.py 源码）。
    返回问题列表；空列表 = 过。"""
    out = []
    last = ''.join(lines_by_scene[-1]) if lines_by_scene else ''
    if '不构成投资建议' not in last:
        out.append('结尾一章旁白里没有念"不构成投资建议"（红线 3）')
    for si, lines in enumerate(lines_by_scene):
        for li, s in enumerate(lines):
            for m in re.finditer(BANNED, s):
                if m.group() == '目标价' and re.search(r'(非|不是|不)$', s[max(0, m.start() - 2):m.start()]):
                    continue
                out.append(f'第 {si:02d} 章第 {li + 1} 句念了「{m.group()}」：像买卖建议或目标价（红线 5）')
        if any('参考价' in s for s in lines) and '非目标价' not in (pics[si] if si < len(pics) else ''):
            out.append(f'第 {si:02d} 章旁白讲了参考价，画面上没有"非目标价"角注（红线 3）')
    return out


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    root = os.path.abspath(a[0])
    mp4s = glob.glob(os.path.join(root, 'output', '*.mp4'))
    if '--video' not in a and not mp4s: sys.exit(f'{root}/output 里没有成片：先跑 python video.py mux，或用 --video 指定')
    video = a[a.index('--video') + 1] if '--video' in a else max(mp4s, key=os.path.getmtime)
    out = a[a.index('--out') + 1] if '--out' in a else os.path.join(root, 'review')
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(root, 'timeline.json'), encoding='utf-8') as fp: tl = json.load(fp)
    sc, total = tl['scenes'], tl['total']
    names, lines, M = scene_names(root, len(sc))
    if lines is None:
        aud = json.load(open(os.path.join(root, 'audio', 'audio_text.json'), encoding='utf-8'))
        lines = [[aud[k] for k in sorted(aud) if k.startswith(f's{si:02d}_')] for si in range(len(sc))]
    facts_p = a[a.index('--facts') + 1] if '--facts' in a else os.path.join(root, 'facts.json')
    facts = json.load(open(facts_p, encoding='utf-8')) if os.path.exists(facts_p) else {}

    print('抽帧…'); shp = sheets(video, sc, names, out)
    print('静止段…'); fz = freezes(video)
    miss = numbers(lines, facts) if facts else []
    lrows, has_labels = label_table(lines, facts) if facts else ([], False)
    try: chk = M.check_report(M.check_scenes()) if M else None
    except Exception as e: print('对口型检查失败：', e); chk = None

    def chap(x): return max(i for i, s in enumerate(sc) if s['off'] <= x + 1e-6)
    L = [f'# 审片包：{os.path.basename(root)}', '',
         f'- 成片：`{video}`，{mmss(total)}（{total:.0f} 秒），{len(sc)} 章',
         '- 作者看完本目录后回答文末自查问题；口径审片已在文字方案阶段做过，确认后改过的旁白句交回同一个口径子代理复核。', '',
         '## 章节与旁白', '']
    for si, s in enumerate(sc):
        L.append(f'### {si:02d} {names[si]}（{mmss(s["off"])} 起，{s["T"]:.0f} 秒）  拼图：`ch_{si:02d}.png`')
        L += [f'{li + 1}. {x}' for li, x in enumerate(lines[si])]; L.append('')
    L += ['## 念到的东西，画面上有没有（每条字幕念完前一刻，按分镜实际画了什么查）', '']
    L += [f'- {x}' for x in chk] if chk else ['- 无'] if chk is not None else ['- 没跑成（读不到 video.py）']
    L += ['', '## 静止段（内容区 3 秒以上不动；只有字幕在变也算不动）', '',
          f'共 {len(fz)} 段，合计 {sum(d for _, d in fz):.0f} 秒，占全片 {sum(d for _, d in fz) / total * 100:.0f}%（只报数）。超过 {still_max():.0f} 秒的（必须补）：', '']
    L += [f'- {mmss(s)}，{d:.1f} 秒，第 {chap(s):02d} 章 {names[chap(s)]}' for s, d in fz if d > still_max()] or ['- 无']
    try: vsrc = open(os.path.join(root, 'video.py'), encoding='utf-8').read()
    except Exception: vsrc = ''
    L += ['', '## 红线（免责、买卖建议口吻、参考价页"非目标价"；有就必须改）', '']
    L += [f'- {x}' for x in redlines(lines, [vsrc] * len(lines))] or ['- 过']
    L += ['', '## 旁白数字对账（facts.json 里找不到的，要核：自算口径、公告原文、还是写错了）', '']
    L += [f'- 第 {si:02d} 章第 {li + 1} 句「{n}」：{s}' for si, li, n, s in miss] or ['- 全部能对上']
    L += ['', '## 旁白数字 ↔ facts 说法（数对不等于说法对：逐行看念出来的半句和冻结的说法是不是一回事）', '']
    if facts and not has_labels:
        L += ['- 这期 facts.json 没有 `labels`（facts.py 没用 `put` 冻结说法），下面只列对上的键，说法要对着 facts.py 自己核。', '']
    L += [f'- 第 {si:02d} 章第 {li + 1} 句「…{c}」 ↔ {lab}' for si, li, c, lab in lrows] or ['- 无']
    L += ['', '## 带推断词的句子（每句都要有证据；推测要说"可能 / 推测"，有几种可能就并列几种）', '']
    L += [f'- 第 {si:02d} 章第 {li + 1} 句：{x}' for si in range(len(sc)) for li, x in enumerate(lines[si]) if re.search(INFER, x)] or ['- 无']
    L += ['', '## 推算句（前提念全了吗？和画面角注是不是同一句？结论有没有把片子自己的推算说成"如果发生"？）', '']
    L += [f'- 第 {si:02d} 章第 {li + 1} 句：{x}' for si in range(len(sc)) for li, x in enumerate(lines[si]) if re.search(CALC, x)] or ['- 无']
    L += ['', '## 同一个数念了好几遍（≥3 句；除了开场提问、结尾回答，其余能删就删）', '']
    L += [f'- 「{n}」{len(w)} 次：' + '、'.join(f'{si:02d}章{li + 1}句' for si, li in w) for n, w in repeats(lines)] or ['- 无']
    L += ['', '## 自查问题（作者回答；57号补丁一起不再另起观众审片子代理）', '',
          '1. 只凭这部片写出：这家公司靠什么赚钱、收入几块各占多少、家底（现金、负债、现金流）怎么样；利润表、资产负债表、现金流量表各自最反常的那一项是什么、为什么（原因出自哪条附注或公告；没有反常项就写"无"）；现在怎么样、为什么会这样；管理层的话对不对得上；为什么便宜、是不是真便宜；什么情况下不成立；接下来看什么。哪句写不出来或写得含糊？',
          '2. 开场问的问题，结尾回答了吗？回答是数据撑得住的，还是硬给了一个答案？',
          '3. 说完"多便宜"，你马上知道"为什么便宜"吗？有没有同一件事被当成两条证据说了两遍？估值几问有没有哪一问独占一章、和前后接不上？',
          '4. 哪一章在凑数？哪几处画面是空的、挤的、静止太久、或者先画了大框再往里填？哪些术语没解释？',
          '5. 章节顺序是从这家公司的主线推出来的吗？哪些章节或画面换一家公司也能原样套用（开场大数字、估值四宫格、结尾好坏两框之类）？这一期真需要它们吗？',
          '6. 哪些结论画面上没有给证据（例如说"几乎没负债"却没拆负债）？结论有没有说了不止一遍？', '',
          '## 口径复核（只核用户确认文字方案后改过的句子；没改过就跳过。交回文字方案阶段的同一个口径子代理）', '',
          '1. 上面"旁白数字 ↔ facts 说法"逐行看：哪些数念出来的说法（时间窗、对象、口径）和数据不一致？',
          '2. 公告类事实（牌照、协议、股东安排）对照原文：有没有漏掉条件、例外，或改写成了原文没有的意思？',
          '3. 推算句：前提念全了吗（已扣什么、没算什么）？截止日之后已经发生的支出扣了吗？旁白和画面角注说的是同一个前提吗？',
          '4. 有没有说过头：单一归因、"市场在定价什么"说成事实、像目标价或买卖建议、核心论据未经审计却没说？',
          '5. 结论和片中推算矛盾吗（例如把片子自己算出的基准情景说成"如果发生才不便宜"）？', '']
    p = os.path.join(out, '审片包.md')
    open(p, 'w', encoding='utf-8').write('\n'.join(L))
    print('done', p, len(shp), '张拼图')


if __name__ == '__main__':
    main()
