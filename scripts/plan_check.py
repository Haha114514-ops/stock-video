# -*- coding: utf-8 -*-
"""plan_check.py —— 文字方案交出去之前跑（57号补丁七）

    python plan_check.py <工程目录>        读 <工程>/文字方案.md 和 facts.json，结果写 <工程>/plan_check.txt

把原来成片后才查、或者只靠作者自觉的几条，挪到写代码之前：
  必须改（退出码 1）：
    - 触发词在旁白里找不到（video.py 里 B.at 会报错）
    - 两个触发点之间隔太久：按约 4.3 字/秒估，超过 STILL_MAX 秒（和 preview 的静止段同一条线，读 motion.py）
    - 红线：结尾没念免责、念了买卖建议 / 目标价口吻、讲参考价的那章画面列没写"非目标价"
    - 未经审计的数第一次出现时，旁白还没说过"未经审计"
    - 总览没填"公司一句话"，或"生意那一拍落在：第 N 章第 M 句"没填 / 指向不存在的句子（57号补丁十七）
  要核（不挡路，口径审员和作者对着看）：
    - 开场章旁白里没出现"公司一句话"里的词（开场可能没说它是做什么的）
    - 旁白数字在 facts.json 里找不到；旁白数字 ↔ facts 说法对照
    - 同一个数念了 ≥3 句
    - 用了强推断词却没说"推测 / 可能"
    - 推算句没念"推算 / 假设 / 如果"
    - 估时超过 15 秒的长句（建议拆，不强制）
"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import review_pack as R  # noqa: E402  复用数字对账、重复、红线

RATE = 4.3            # 字/秒（去标点），金茂 v3 实测，和文字方案模板一致
LONG = 15.0           # 秒，超过建议拆句
STRONG = r'信号|说明了|意味着|显然|一定|必然|等于|相当于|白得|白送|算进去|定价|市场(在|还在|先)|打不破|打破|解释不了|看来|看起来|似乎'
HEDGE = r'推测|可能|也许|或许|不一定|说不准|不是结论|几种'
PREMISE = r'推算|假设|如果|按.{0,12}算|年化'


def clean(s):
    return re.sub(r'[^\w]', '', s).replace('_', '')


def parse(md):
    """→ [(章号, 章名, [(旁白, 画面, [触发词])])]"""
    chs, cur, cols = [], None, None
    for line in md.splitlines():
        h = re.match(r'^###\s+(\d+)\s*([^（(]*)', line)
        if h:
            cur = (h.group(1), h.group(2).strip(), []); chs.append(cur); cols = None; continue
        if cur is None or not line.strip().startswith('|'): continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if '旁白' in cells:
            cols = {k: cells.index(k) for k in ('旁白', '画面', '触发词') if k in cells}
            continue
        if not cols or not cells or not cells[0].isdigit(): continue
        get = lambda k: cells[cols[k]] if k in cols and cols[k] < len(cells) else ''
        trig = [t.strip(' 「」"“”') for t in re.split(r'[；;、/，,]+', get('触发词'))]
        trig = [t for t in trig if t and t not in ('—', '-', '–', '无')]
        cur[2].append((get('旁白'), get('画面'), trig))
    return chs


def beats(text, trig):
    """→ (缺的触发词, 各段 [(秒, 起字, 止字)])：开口算第一个节拍，每个触发词一个，句末收尾"""
    pos, miss, last = [0], [], 0
    for t in trig:
        i = text.find(t, last)
        if i < 0: i = text.find(t)
        if i < 0: miss.append(t); continue
        pos.append(len(clean(text[:i]))); last = i + len(t)
    n = len(clean(text)); pos = sorted(set(pos)) + [n]
    segs = [((b - a) / RATE, a, b) for a, b in zip(pos, pos[1:])]
    return miss, segs


def frag(text, a, b):
    """去标点位置 a~b 对应的原文片段（报"这几秒在念什么"）"""
    out, k = [], 0
    for ch in text:
        w = bool(clean(ch))
        if a <= k < b: out.append(ch)
        if w: k += 1
    s = ''.join(out).strip('，。；、：,. ')
    return s if len(s) <= 40 else s[:38] + '…'


BIZ_STOP = set('它靠给赚钱的和与及是在把从向卖做')


def business(md, chs, lines):
    """公司做什么（补丁十七）→ (必须改, 要核, 给作者看的那几句)"""
    must, check, show = [], [], []
    m = re.search(r'^-\s*公司一句话[^：:\n]*[：:][ \t]*(.*)$', md, re.M)
    one = m.group(1).strip() if m else ''
    if not one or '<' in one or '_' in one:
        must.append('总览的"公司一句话"没填：照 故事.md 第零节写"它靠 X 卖给 Y 赚钱"')
    else:
        show.append(f'- 公司一句话：{one}')
        cs = [c for c in re.sub(r'[^一-鿿]', '', one)]
        grams = {a + b for a, b in zip(cs, cs[1:]) if a not in BIZ_STOP and b not in BIZ_STOP}
        opening = ''.join(lines[0]) if lines else ''
        if grams and not any(g in opening for g in grams):
            check.append(f'开场（第 {chs[0][0]} 章）旁白里没出现"公司一句话"里的词：开场念到公司时有没有半句说它是做什么的？')
    m = re.search(r'^-\s*生意那一拍落在[：:]\s*第\s*(\d+)\s*章第\s*(\d+)\s*句', md, re.M)
    if not m:
        must.append('总览的"生意那一拍落在：第 N 章第 M 句"没填：写明故事第一次讲到收入、讲全几块业务怎么收钱的那一句')
    else:
        ci, li = int(m.group(1)), int(m.group(2))
        hit = [k for k, (no, _, _) in enumerate(chs) if int(no) == ci]
        if not hit or li < 1 or li > len(lines[hit[0]]):
            must.append(f'"生意那一拍"指向第 {ci} 章第 {li} 句，文字方案里没有这一句')
        else:
            k = hit[0]
            seg = lines[k][li - 1:li + 2]
            show.append(f'- 生意那一拍（第 {chs[k][0]} 章第 {li} 句起）：' + ' / '.join(seg))
    return must, check, show


def main():
    if len(sys.argv) < 2: print(__doc__); return 0
    root = os.path.abspath(sys.argv[1])
    md_p = os.path.join(root, '文字方案.md')
    if not os.path.exists(md_p): print('找不到', md_p); return 2
    md = open(md_p, encoding='utf-8').read()
    chs = parse(md)
    if not chs: print('文字方案里没读到"### NN 章名"和旁白表格'); return 2
    fp = os.path.join(root, 'facts.json')
    facts = json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else {}
    smax = R.still_max()

    lines = [[r[0] for r in rows] for _, _, rows in chs]
    pics = [' '.join(r[1] for r in rows) for _, _, rows in chs]
    must, check, longs = [], [], []
    total = 0.0

    # 触发词与间隔
    for si, (no, name, rows) in enumerate(chs):
        for li, (text, pic, trig) in enumerate(rows):
            miss, segs = beats(text, trig)
            dur = sum(d for d, _, _ in segs); total += dur
            tag = f'第 {no} 章第 {li + 1} 句'
            for t in miss:
                must.append(f'{tag}：触发词「{t}」在旁白里找不到（B.at 会报错）')
            for d, a, b in segs:
                if d > smax:
                    must.append(f'{tag}：约 {d:.1f} 秒没有触发点（上限 {smax:.0f} 秒），这段在念「{frag(text, a, b)}」→ 在这段里加一个触发词，或拆句')
            if dur > LONG:
                longs.append(f'{tag}：约 {dur:.0f} 秒（{len(clean(text))} 字），可以考虑拆成两句')

    # 红线
    must += R.redlines(lines, pics)

    # 公司做什么、靠什么赚钱
    bm, bc, biz = business(md, chs, lines)
    must += bm; check += bc

    # 未经审计：第一次念到标了"未经审计"的数时，前面（含这句）要说过
    labels = facts.get('labels', {})
    unaud = {k for k, v in labels.items() if '未经审计' in str(v)}
    if unaud:
        paths = R.flat_paths(facts); said = False; done = False
        for si, rows in enumerate(lines):
            for li, s in enumerate(rows):
                said = said or '未经审计' in s
                if done: continue
                hit = [k for _, n in R._nums(s) for k in R.matches(n, paths) if k in unaud]
                if hit:
                    done = True
                    if not said:
                        must.append(f'第 {chs[si][0]} 章第 {li + 1} 句第一次念到未经审计的数（{hit[0]}），旁白到这里还没说"未经审计"')

    # 要核
    if facts:
        for si, li, n, s in R.numbers(lines, facts):
            check.append(f'数字不在 facts 里：第 {chs[si][0]} 章第 {li + 1} 句「{n}」')
    for n, w in R.repeats(lines):
        check.append(f'同一个数念了 {len(w)} 句：「{n}」→ ' + '、'.join(f'{chs[si][0]}章{li + 1}句' for si, li in w))
    for si, rows in enumerate(lines):
        for li, s in enumerate(rows):
            m = re.search(STRONG, s)
            if m and not re.search(HEDGE, s):
                check.append(f'强推断词「{m.group()}」没配"推测 / 可能"：第 {chs[si][0]} 章第 {li + 1} 句')
            if re.search(R.CALC, s) and not re.search(PREMISE, s):
                check.append(f'像推算却没念"推算 / 假设 / 如果"：第 {chs[si][0]} 章第 {li + 1} 句')

    ref = []
    if facts:
        rows, has = R.label_table(lines, facts)
        ref = [f'- 第 {chs[si][0]} 章第 {li + 1} 句「…{c}」 ↔ {lab}' for si, li, c, lab in rows]

    n_sent = sum(len(r) for r in lines)
    head = (f'文字方案检查：{len(chs)} 章 {n_sent} 句，估时约 {total / 60:.0f} 分 {total % 60:.0f} 秒（{RATE} 字/秒）。'
            f'必须改 {len(must)} 条，要核 {len(check)} 条，长句 {len(longs)} 句。')
    out = [head, '',
           f'## 必须改（触发点间隔上限 {smax:.0f} 秒，和 preview 的静止段同一条线）'] + [f'- {x}' for x in must or ['无']] + \
          ['', '## 要核（作者和口径审员对着看，不挡路）'] + [f'- {x}' for x in check or ['无']] + \
          ['', '## 公司做什么（作者对着看：外行听完知道它卖什么、给谁、怎么收钱吗）'] + (biz or ['- 无']) + \
          ['', '## 长句（建议拆，不强制）'] + [f'- {x}' for x in longs or ['无']] + \
          ['', '## 旁白数字 ↔ facts 说法（给口径审员）'] + (ref or ['- 无（没有 facts.json 或没对上的数）'])
    open(os.path.join(root, 'plan_check.txt'), 'w', encoding='utf-8').write('\n'.join(out))
    sys.stdout.reconfigure(encoding='utf-8')
    print(head + ' → plan_check.txt')
    for x in must[:20]: print('  [必须改] ' + x)
    return 1 if must else 0


if __name__ == '__main__':
    sys.exit(main())
