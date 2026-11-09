# -*- coding: utf-8 -*-
"""report_check.py —— 报告稿交口径审员之前、出 PDF 之前跑（对应视频的 plan_check.py）

    python report_check.py <工程>          读 报告稿.md、facts.json、charts.py → <工程>/report_check.txt；有"必须改"退出码 1

必须改：
  - 文件头缺 公司 / 代码 / 截止日 / 主线 / 公司一句话
  - {{键}} 在 facts.json 里找不到；[[图 名字]] 在 charts.py 里没有
  - 文件头"三表总览"没写、少一张表、指向稿子里没用到的图；
    资产负债表总览那张图不是 bs_two_bars（同一时点"有什么""钱是谁的"两根柱，方法与口径 §0）
  - 红线：买卖建议 / 目标价口吻；讲了参考价的那章没有"非目标价"（price_line 画的参考价自带）
  - 未经审计的数（facts 说法里带"未经审计"）第一次出现时，正文还没说过"未经审计"
要核（不挡路，口径审员和作者对着看）：
  - 利润表总览不是 waterfall、现金流量表总览不是 cash_bridge（换画法可以，整张表要看得全）
  - 第一章（或摘要）没出现"公司一句话"里的词
  - 正文数字在 facts.json 里找不到；正文数字 ↔ facts 说法对照
  - 同一个数写了 ≥3 次
  - 强推断词不在"推测"框里、句子里也没说"推测 / 可能"
  - 推算句没写"推算 / 假设 / 如果 / 按…算"
数字对账、重复、红线的规则和视频共用（stock-video/scripts/review_pack.py）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rlib  # noqa: E402
rlib.video_scripts()
import review_pack as R  # noqa: E402
import build_report as B  # noqa: E402

STRONG = r'信号|说明了|意味着|显然|一定|必然|等于|相当于|白得|白送|定价|市场(在|还在|先)|打不破|解释不了|看来|看起来|似乎'
HEDGE = r'推测|可能|也许|或许|不一定|说不准|不是结论|几种'
PREMISE = r'推算|假设|如果|按.{0,14}算|年化|前提'
NEED = ('公司', '代码', '截止日', '主线', '公司一句话')


def sentences(text):
    """正文拆句：去掉图 / 卡指令、表格分隔行；框（:::）里的句子带上框的类型"""
    out, kind = [], ''
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r'^:::\s*(\S*)', s)
        if m:
            kind = m.group(1) if m.group(1) else ''
            continue
        if not s or s.startswith('[[') or re.fullmatch(r'[|\-:\s]+', s): continue
        s = re.sub(r'^[#>*\-\d.\s]+(?=\S)', '', s) if not re.match(r'^\d', s) else s
        for part in re.split(r'(?<=[。！？；])', s):
            part = part.strip()
            if part: out.append((kind, part))
    return out


def main(proj):
    proj = Path(proj).resolve()
    meta, body = B.read_draft(proj)
    fx = rlib.load_facts(proj)
    pre, chs = B.split_chapters(body)
    must, check = [], []

    for k in NEED:
        if not meta.get(k): must.append(f'文件头没填「{k}」')

    # {{键}}：先核键，再换成数（数字对账按换完的文字做）
    keys_used = []
    def rep(m):
        key, _, spec = m.group(1).strip().partition('|')
        try:
            v = rlib.get(fx, key.strip())
        except KeyError:
            must.append(f'{{{{{key}}}}} 在 facts.json 里找不到'); return '？'
        keys_used.append(key.strip()); return rlib.fmt(v, spec.strip())

    titles = [t for t, _ in chs]
    texts = [re.sub(r'\{\{([^}]+)\}\}', rep, t) for _, t in chs]

    # 图
    src = (proj / 'charts.py').read_text(encoding='utf-8') if (proj / 'charts.py').exists() else ''
    funcs = {m.group(1): m for m in re.finditer(r'^def\s+(\w+)\s*\(', src, re.M)}

    def func_src(name):
        m = funcs.get(name)
        if not m: return ''
        nxt = [x.start() for x in funcs.values() if x.start() > m.start()]
        return src[m.start(): min(nxt) if nxt else len(src)]

    figs_by_ch = [re.findall(r'^\[\[图\s+([^\]]+?)\s*\]\]', t, re.M) for _, t in chs]
    all_figs = [f for fs in figs_by_ch for f in fs]
    for f in sorted(set(all_figs)):
        if f not in funcs: must.append(f'[[图 {f}]]：charts.py 里没有这个函数')

    # 三表总览
    tri = dict(re.findall(r'(利润表|资产负债表|现金流量表)\s*[=＝]\s*([^;；,，\s]+)', meta.get('三表总览', '')))
    if not meta.get('三表总览'):
        must.append('文件头没写「三表总览: 利润表=图名; 资产负债表=图名; 现金流量表=图名」（每期三张表都要整张读一遍）')
    else:
        for t, fn, want, hint in (('利润表', 'waterfall', False, '瀑布图'), ('资产负债表', 'bs_two_bars', True, '两根柱'),
                                  ('现金流量表', 'cash_bridge', False, '现金桥')):
            name = tri.get(t)
            if not name: must.append(f'三表总览缺「{t}」'); continue
            if name not in all_figs: must.append(f'三表总览「{t}={name}」：稿子里没有 [[图 {name}]]'); continue
            if fn not in func_src(name):
                msg = f'三表总览「{t}」那张图（{name}）没用 {fn}（默认画法：{hint}）'
                (must if want else check).append(msg + ('：资产负债表总览要同一时点"有什么""钱是谁的"两根柱，缺一边不算总览' if want else '；换画法可以，整张表要看得全'))

    # 红线（免责声明 build_report 自动印在文末，不查）
    pics = []
    for i, t in enumerate(texts):
        pic = t + ''.join(func_src(f) for f in figs_by_ch[i])
        if any('price_line' in func_src(f) and 'ref' in func_src(f) for f in figs_by_ch[i]): pic += '非目标价'
        pics.append(pic)
    lines_by = [[s for _, s in sentences(t)] for t in texts]
    for msg in R.redlines(lines_by, pics):
        if '不构成投资建议' in msg: continue
        msg = re.sub(r'第 (\d+) 章第 (\d+) 句', lambda m: f'{titles[int(m.group(1))]} 第 {m.group(2)} 句', msg)
        msg = re.sub(r'第 (\d+) 章', lambda m: titles[int(m.group(1))], msg)
        must.append(msg.replace('旁白', '正文').replace('念了', '写了').replace('画面上', '图上'))

    # 未经审计
    unaudited = [k for k, v in fx.get('labels', {}).items() if '未经审计' in v]
    if unaudited:
        paths = R.flat_paths(fx)
        said = False
        for i, t in enumerate(texts):
            for kind, s in sentences(t):
                if '未经审计' in s: said = True
                hit = [k for k in unaudited if k in keys_used and rlib.fmt(rlib.get(fx, k), '') in s]
                for m, n in R._nums(s):
                    hit += [k for k in R.matches(n, paths) if k in unaudited]
                if hit and not said:
                    must.append(f'{titles[i]}：「{s[:40]}」用到未经审计的数（{hit[0]}），之前正文没说过"未经审计"')
                    said = True

    # 公司一句话
    one = meta.get('公司一句话', '')
    first = (pre + ''.join(texts[:2]))
    words = [w for w in re.findall(r'[一-鿿]{2,4}', one) if w not in ('它靠', '赚钱', '公司')]
    if words and not any(w in first for w in words):
        check.append('摘要和第一章里没出现「公司一句话」的词：读者可能读到利润表还不知道它卖什么')

    # 数字对账、重复：facts 存的是元，正文常写亿元 / 万元——补一份换算后的值参与比对（说法跟着原键）
    fxa = dict(fx); fxa['labels'] = dict(fx.get('labels', {}))
    for scale, tag in ((1e8, '_亿'), (1e4, '_万')):
        d = {}
        for k, v in R.flat_paths(fx):
            if abs(v) >= scale * 0.01:
                d[k] = v / scale
                if k in fx.get('labels', {}): fxa['labels'][f'{tag}.{k}'] = fx['labels'][k] + f'（换算成{tag[1:]}）'
        fxa[tag] = d
    fx = fxa
    miss = R.numbers(lines_by, fx)
    for si, li, n, s in miss:
        check.append(f'{titles[si]}：数字 {n} 在 facts.json 里找不到 ——「{s[:50]}」')
    for n, where in R.repeats(lines_by):
        check.append(f'数字 {n} 写了 {len(where)} 次（{"、".join(titles[si] for si, _ in where[:4])}）：一个数说一遍就够')

    # 推断、推算
    for i, t in enumerate(texts):
        for kind, s in sentences(t):
            if re.search(STRONG, s) and kind != '推测' and not re.search(HEDGE, s):
                check.append(f'{titles[i]}：强推断词没标推测 ——「{s[:50]}」')
            if re.search(R.CALC, s) and kind != '推算' and not re.search(PREMISE, s):
                check.append(f'{titles[i]}：像推算却没写前提 ——「{s[:50]}」')

    rows, has_labels = R.label_table(lines_by, fx)
    out = [f'report_check：{proj.name}', '',
           f'== 必须改（{len(must)}）==', *([f'- {m}' for m in must] or ['（无）']), '',
           f'== 要核（{len(check)}）==', *([f'- {m}' for m in check] or ['（无）']), '',
           '== 正文数字 ↔ facts 说法 ==' + ('' if has_labels else '（facts.json 没有 labels：facts.py 用 put 冻结说法）')]
    out += [f'- {titles[si]} 第 {li + 1} 句：…{ctx}… → {lab}' for si, li, ctx, lab in rows]
    (proj / 'report_check.txt').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('\n'.join(out[:3 + len(must) + 3 + min(len(check), 20)]))
    print(f'\n全文：{proj / "report_check.txt"}')
    return 1 if must else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if len(sys.argv) < 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
