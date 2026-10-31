# -*- coding: utf-8 -*-
"""定期报告 PDF → 带页标记的全文 + 管理层讨论 + 按清单切好的段 + 目录索引（57号补丁十一）。
切段：主要会计数据、分季度、审计报告关键审计事项、利润分配、管理层讨论、二十来条附注；
只给页码：三张合并报表、重大诉讼、重大关联交易、担保。
材料员先读 <标题>_目录索引.md 和切好的段；清单外的内容用关键词在 _全文.txt 里定位，只读命中的那几页，不通读全文。

用法：python report_cut.py <PDF> [<输出目录>] [--title=标题] [--notes=关键词1,关键词2]
  输出目录  默认 PDF 所在目录
  --title   输出文件名前缀，默认 PDF 文件名
  --notes   清单外要切的附注科目（这期命门相关，如 商誉,开发支出），按"编号. 科目名"标题找
产出（都在输出目录）：
  <标题>_全文.txt            每页前一行 =====PDF第N页=====，抄出处时用这个页码
  <标题>_管理层讨论与分析.txt
  <标题>_附注_<名>.txt       清单里每一项一份，文件头写页码范围；超过 CAP 字截断并在索引里标出
  <标题>_目录索引.md         各节起始页、切好的段（页码 / 字数）、清单里没切到的项
fetch_data.py 下载年报 / 半年报后自动调用；季报、港股 PDF 可手动跑（港股版式不同，附注多半切不到，看索引里的"没切到"）。"""
import bisect, io, os, re, sys

PAGE = '=====PDF第{}页====='
PAGE_RE = re.compile(r'^=====PDF第(\d+)页=====$', re.M)
CN = '一二三四五六七八九十'
NL = r'[ \t]*(?:\n[ \t]*)?'   # 编号和标题之间可以换行（"六、" 单独一行，招商蛇口 2026 半年报）
CAP = 20000

# ---------- 清单 ----------
# 编号附注（"合并财务报表项目注释"一节里，"33." 换行 "长期借款"，或 "33、长期借款"）：名 → 科目名正则
NUM_NOTES = {
    '营业收入和营业成本': r'营业收入[和及、]营业成本|营业收入、营业成本',
    '所得税费用': r'所得税费用',
    '财务费用': r'财务费用',
    '投资收益': r'投资收益',
    '资产减值损失': r'资产减值损失',
    '信用减值损失': r'信用减值损失',
    '公允价值变动收益': r'公允价值变动(收益|损益)',
    '货币资金': r'货币资金',
    '应收账款': r'应收账款',
    '存货': r'存货',
    '商誉': r'商誉',
    '合同负债': r'合同负债',
    '短期借款': r'短期借款',
    '一年内到期的非流动负债': r'(一|1)[ \t]*年内到期的非流动负债',   # 金隅写"1 年内"
    '长期借款': r'长期借款',
    '应付债券': r'应付债券',
    '租赁负债': r'租赁负债',
    '现金流量表补充资料': r'现金流量表补充资料',
    '分部信息': r'分部(信息|报告)',
}
# 一级标题（"十二、资产负债表日后事项"）：名 → 标题正则；在整份报告里找
TOP_NOTES = {
    '主要会计数据': r'(近三年)?(公司)?主要会计数据(和财务指标)?',
    '分季度数据': r'(\d{4}[ \t]*年)?分季度主要财务(指标|数据)',
    '关键审计事项': r'关键审计事项[：:]?',
    '利润分配': r'(公司)?(本报告期)?利润分配(及资本公积金转增股本(情况|预案)|或资本公积金转增预案)',
    '非经常性损益': r'非经常性损益项目及金额|非经常性损益项目和金额',
    '资产负债表日后事项': r'资产负债表日后事项',
    '承诺及或有事项': r'承诺及或有事项|或有事项',
    '合并范围变更': r'合并范围的变(更|动)',   # 紫金写"变动"；"七、合并范围的变动 - 续"这类页眉不算结束
}
# 并表信息：目录里也有同名标题，取最长的一段（沿用 fetch_data 原逻辑）
SPAN_NOTES = {
    '子公司权益': (r'在子公司中的权益', r'在合营(企业|安排)[和或及]联营企业中的权益'),
}
KEEP_NAME = {'子公司权益', '合并范围变更'}   # 沿用旧文件名 <标题>_子公司权益.txt，不加"附注_"
# 只给页码、不切段（原表和"重要事项"各条写法差别大，到全文里读那几页）：名 → 单独成行的标题
LANDMARKS = {
    '合并资产负债表': r'(\d[、.．][ \t]*)?合并资产负债表',
    '合并利润表': r'(\d[、.．][ \t]*)?合并利润表',
    '合并现金流量表': r'(\d[、.．][ \t]*)?合并现金流量表',
    '重大诉讼、仲裁': rf'([{CN}]+、[ \t]*)?重大诉讼、仲裁事项',
    '重大关联交易': rf'([{CN}]+、[ \t]*)?重大关联交易',
    '担保': r'(\d[、.．][ \t]*)?重大担保|[（(]二[)）][ \t]*担保情况|担保情况',
}

# ---------- 抽文本 ----------
def pdf_text(pdf):
    import fitz
    with fitz.open(pdf) as doc:
        return '\n'.join(PAGE.format(i + 1) + '\n' + pg.get_text() for i, pg in enumerate(doc))

class Pages:
    def __init__(self, text):
        self.pos = [m.start() for m in PAGE_RE.finditer(text)]
        self.no = [int(m.group(1)) for m in PAGE_RE.finditer(text)]
    def at(self, p):
        i = bisect.bisect_right(self.pos, p) - 1
        return self.no[i] if i >= 0 else 1
    def span(self, a, b):
        a, b = self.at(a), self.at(max(a, b - 1))
        return f'第 {a} 页' if a == b else f'第 {a}~{b} 页'

# ---------- 管理层讨论与分析 ----------
# 只认行首：正文里"详见本报告'第五节重要事项…'"这类交叉引用不算下一节（招商蛇口 2025 年报因此只切到第 46 页，实际到第 61 页）。
# "第X节"后允许换行（金隅："第五节"单独一行，"重要事项"在下一行）
HEAD = re.compile(r'^[ \t]*第[一二三四五六七八九十]+[节章]\s*\S', re.M)
MDA = re.compile(r'^[ \t]*第[一二三四五六七八九十]+[节章]\s*(管理层讨论与分析|经营情况讨论与分析|董事会报告)', re.M)
# 正文标题不带"第X节"的版式（紫金矿业 2025 年报、2026 半年报：只有目录带"第三节"，正文标题是单独一行）
MDA_LINE = re.compile(r'^[ \t]*(管理层讨论与分析|经营情况讨论与分析)[ \t]*$', re.M)
END_LINE = re.compile(r'^[ \t]*(公司治理|重要事项|环境与社会责任|环境与应对气候改变|股份变动及股东情况)[ \t]*$', re.M)

def extract_mda(text):
    """正文里的"管理层讨论与分析"一节：目录里也会出现同名标题，取到下一节之间最长的那一段。
    按"第X节"取不到（<2000 字）时，退回按单独成行的标题取，到下一个单独成行的节名为止。返回 (起, 止)。"""
    best = (0, 0)
    for m in MDA.finditer(text):
        nxt = HEAD.search(text, m.end() + 20)
        e = nxt.start() if nxt else len(text)
        if e - m.start() > best[1] - best[0]: best = (m.start(), e)
    if best[1] - best[0] < 2000:
        for m in MDA_LINE.finditer(text):
            e = END_LINE.search(text, m.end() + 20)
            e = min(e.start() if e else len(text), m.start() + 150000)
            if e - m.start() > best[1] - best[0]: best = (m.start(), e)
    return best

# ---------- 附注 ----------
def notes_region(text):
    """"合并财务报表项目注释"一节到"母公司财务报表…注释"为止；分部、期后事项在中间也算。找不到就返回 None。"""
    st = re.search(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}合并财务报表(主要)?项目(注释|附注)[ \t]*$', text, re.M)
    if not st: return None
    en = re.search(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}(母公司|公司)财务报表(主要)?项目(注释|附注)', text[st.end():], re.M)
    return st.start(), st.end() + en.start() if en else len(text)

def num_head(kw, n=None):
    num = str(n) if n else r'\d{1,3}'
    # 标题后可带"（续）""/ (净收益)"之类的尾巴（华润三九"54、财务费用 / (净收益)"）
    return re.compile(rf'^[ \t]*({num})[ \t]*[、.．]{NL}(?:{kw})[ \t]*(?:[/／][ \t]*)?(?:[（(][^\n]{{0,30}}[)）])?[ \t]*$', re.M)

def cut_num(text, region, kw):
    a, b = region
    for m in num_head(kw).finditer(text, a, b):
        n = int(m.group(1))
        nxt = re.compile(rf'^[ \t]*{n + 1}[ \t]*[、.．][ \t]*(?:\n[ \t]*)?[一-鿿]', re.M).search(text, m.end(), b)
        e = nxt.start() if nxt else min(b, m.end() + CAP)
        if e - m.start() >= 100: return m.start(), e
    return None

TOP_ANY = re.compile(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}[一-鿿][^\n]*$', re.M)

def cut_top(text, kw, pg):
    """先找带"十二、"编号的标题，到下一个一级标题为止；一处都没有，再找单独成行、不带编号的
    （紫金"非经常性损益项目和金额"），认不出结尾，就取到标题所在页的下一页末。返回 (起, 止, 是否无编号)。"""
    best = None
    for m in re.finditer(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}(?:{kw})[ \t]*$', text, re.M):
        e = len(text)
        for n in TOP_ANY.finditer(text, m.end() + 20):
            if '续' not in n.group(0): e = n.start(); break
        e = min(e, m.start() + CAP * 2)
        if e - m.start() >= 100 and (best is None or e - m.start() > best[1] - best[0]): best = (m.start(), e)
    if best: return (*best, False)
    for m in re.finditer(rf'^[ \t]*(?:{kw})[ \t]*$', text, re.M):
        nxt = PAGE_RE.search(text, text.find(PAGE.format(pg.at(m.start()) + 1)) + 1) if PAGE.format(pg.at(m.start()) + 1) in text else None
        e = nxt.start() if nxt else len(text)
        if e - m.start() >= 100: return m.start(), e, True
    return None

def cut_span(text, st, en):
    best = None
    for m in re.finditer(st, text):
        e = re.search(en, text[m.end() + 20:])
        e = m.end() + 20 + e.start() if e else m.start() + 40000
        e = min(e, m.start() + 40000)
        if best is None or e - m.start() > best[1] - best[0]: best = (m.start(), e)
    return best

# ---------- 主流程 ----------
def sections(text, pg):
    """各节起始页：每个"第X节 名"取最后一次出现（第一次多半在目录里）。"""
    last = {}
    for m in re.finditer(r'^[ \t]*(第[一二三四五六七八九十]+[节章])[ \t]*\n?[ \t]*([^\n]{2,30}?)[ \t.…·\d]*$', text, re.M):
        last[m.group(1)] = (m.group(2).strip(), pg.at(m.start()))
    return [(k, *v) for k, v in last.items()]

def cut(pdf, outdir, title, extra=()):
    """切一份报告，返回给 fetch_log 用的一句话。"""
    os.makedirs(outdir, exist_ok=True)
    text = pdf_text(pdf); pg = Pages(text)
    w = lambda name, s: open(os.path.join(outdir, f'{title}_{name}.txt'), 'w', encoding='utf-8').write(s)
    w('全文', text)
    got, miss, trunc, loose = [], [], [], []

    def save(name, ab, fname=None):
        a, b = ab; seg = text[a:b]
        if len(seg) > CAP and name != '管理层讨论与分析':
            seg = seg[:CAP]; b = a + CAP; trunc.append(name)
        span = pg.span(a, b)
        w(fname or f'附注_{name}', f'【{title}·{name}，PDF {span}】\n' + seg)
        got.append((name, span, len(seg), f'{title}_{fname or "附注_" + name}.txt'))

    mda = extract_mda(text)
    if mda[1] - mda[0] >= 2000: save('管理层讨论与分析', mda, '管理层讨论与分析')
    else: miss.append(('管理层讨论与分析', '搜「管理层讨论与分析」「经营情况讨论与分析」'))

    reg = notes_region(text)
    num = dict(NUM_NOTES); num.update({k: re.escape(k) for k in extra})
    for name, kw in num.items():
        r = cut_num(text, reg, kw) if reg else None
        if r: save(name, r)
        else: miss.append((name, f'搜「{name}」' + ('' if reg else '（没找到"合并财务报表项目注释"一节）')))
    for name, kw in TOP_NOTES.items():
        try: r = cut_top(text, kw, pg)
        except Exception: r = None
        if r:
            save(name, r[:2], name if name in KEEP_NAME else None)
            if r[2]: loose.append(name)
        else: miss.append((name, f'搜「{name}」'))

    # 原文定位：第 3 页以后第一次单独成行出现的地方（跳过目录）；三张合并报表取审计报告之后的那一处
    audit = re.search(r'关键审计事项', text)
    marks = []
    for name, kw in LANDMARKS.items():
        try:
            after = audit.start() if audit and name.startswith('合并') else 0
            m = next((m for m in re.finditer(rf'^[ \t]*(?:{kw})[ \t]*$', text, re.M)
                      if m.start() >= after and pg.at(m.start()) > 2), None)
        except Exception: m = None
        if m: marks.append((name, pg.at(m.start())))
        else: miss.append((name, f'搜「{name}」'))
    for name, (st, en) in SPAN_NOTES.items():
        r = cut_span(text, st, en)
        if r: save(name, r, name)
        else: miss.append((name, f'搜「{name}」'))

    L = [f'# {title} 目录索引', '',
         f'全文 {pg.no[-1] if pg.no else 0} 页、{len(text)} 字：`{title}_全文.txt`（每页前一行 `=====PDF第N页=====`）。',
         '先读这份索引和下面切好的段；清单外的内容在全文里搜关键词，只读命中的那几页，不通读全文。', '',
         '## 各节起始页', '']
    L += [f'- {k} {nm}：第 {p} 页' for k, nm, p in sections(text, pg)] or ['- （没认出"第X节"标题）']
    L += ['', '## 切好的段', '', '| 段 | 页码 | 字数 | 文件 |', '|---|---|---|---|']
    L += [f'| {n}{"（截断）" if n in trunc else ""}{"（标题无编号，取到下一页末，结尾可能多出别的内容）" if n in loose else ""} | {s} | {c} | `{f}` |' for n, s, c, f in got]
    L += ['', '## 原文定位（只给起始页，到全文里读那几页）', '']
    L += [f'- {n}：第 {p} 页' for n, p in marks] or ['- 无']
    L += ['', '## 清单里没切到的（不等于报告里没有：去全文里搜，查过写"查过：…"）', '']
    L += [f'- {n}：{h}' for n, h in miss] or ['- 无']
    if trunc: L += ['', f'截断的段只存了前 {CAP} 字，后面的去全文里按页码接着读。']
    open(os.path.join(outdir, f'{title}_目录索引.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return f'{title} 全文{len(text)}字 / 切到 {len(got)} 段 / 没切到 {len(miss)} 项' + (f'（{"、".join(n for n, _ in miss)}）' if miss else '')

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opt = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
    pdf = args[0]; out = args[1] if len(args) > 1 else os.path.dirname(os.path.abspath(pdf))
    title = opt.get('title') or os.path.splitext(os.path.basename(pdf))[0]
    print(cut(pdf, out, title, [k for k in opt.get('notes', '').split(',') if k]))
