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
fetch_data.py 下载年报 / 半年报后自动调用；季报、港股 PDF 可手动跑。
港股年报 / 中期报告（繁体、香港财务报告准则）自动认出、走另一套：按每页页眉切管理层讨论与分析、关键审计事项、
四张主表，附注按递增编号切清单里的科目（所得税、租赁、贸易应付、合约负债、物业减值、股息 / 储备等），索引另列附注编号一览。"""
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

# ---------- 港股（繁体、香港财务报告准则）----------
# 港股年报 / 中期报告没有"第X节""合并资产负债表""一、合并财务报表项目注释"，A 股这套一段都切不到（高鑫零售 2025/26 年报切到 0 段，
# 材料员只能逐页翻）。港股版式：每页页首是栏目页眉（管理層討論與分析 / 獨立核數師報告 / 綜合財務報表附註…）；
# 附注标题是"编号单独一行（或同一行）+ 科目名"，编号从 1 递增，续页写"（續）"。
# 先繁→简逐字转换再匹配（一对一，位置不变，切出来的仍是原文），只认递增的编号，表格里"36 / 來自其他來源的收入"这类行不算。
T2S = str.maketrans('責連發編製賃別頒佈詮釋組須級歷階輸綜財務狀況損現動權變註審計關鍵項層討論與稅貿應負債約資產減僱員儲備銀貸報貨業廠設無後擔聯屬會斷開虧風險價簡團營運經費準據錄東處獨師數撥職離預確認遞國際則選擇績換匯兌歸對為於個這來從時間內長讓證結構測試圍範總額淨購買賣銷攤舊訂協議條號單筆誤實態續併倉庫戶參閱釐貼採遠覆類劃齊屆薪盈稱億萬幣儀濟標標紀錢據辦務圖書訊調證選隨雜寬種創視機構環境衛線', '责连发编制赁别颁布诠释组须级历阶输综财务状况损现动权变注审计关键项层讨论与税贸应负债约资产减雇员储备银贷报货业厂设无后担联属会断开亏风险价简团营运经费准据录东处独师数拨职离预确认递国际则选择绩换汇兑归对为于个这来从时间内长让证结构测试围范总额净购买卖销摊旧订协议条号单笔误实态续并仓库户参阅厘贴采远复类划齐届薪盈称亿万币仪济标标纪钱据办务图书讯调证选随杂宽种创视机构环境卫线')
def norm(s): return s.translate(T2S)
HK_PART = {   # 页眉 → 栏目（简体匹配）
    '管理层讨论与分析': r'管理层讨论(与|及)分析|业务回顾|财务回顾',
    '核数师报告': r'核数师报告|审计报告|审阅报告',
    '财务摘要': r'财务摘要|业绩摘要|五年(财务)?概要',
    '综合损益表': r'综合(损益|收益表)',
    '综合财务状况表': r'综合财务状况表',
    '综合权益变动表': r'综合权益变动表',
    '综合现金流量表': r'综合现金流量表',
    '财务报表附注': r'(财务报表|财务资料)附注',
}
HK_NOTES = {  # 附注科目名（去掉"（续）"后）→ 正则；同名取编号最小的一条
    '收入及分部': r'收入|营业额|分部',
    '除税前溢利（费用明细）': r'除税前(溢利|利润|亏损)|经营(溢利|利润)',
    '所得税': r'^(综合损益[^\n]{0,10})?所得税(开支|费用)?$|^税项$',
    '财务状况表内的所得税（递延税项）': r'财务状况表内的所得税|递延税项',
    '投资物业及物业厂房设备（含减值）': r'物业、?厂房及设备|投资物业',
    '使用权资产': r'使用权资产',
    '存货': r'^存货',
    '贸易及其他应收款项': r'贸易[^\n]{0,6}应收',
    '贸易及其他应付款项': r'贸易[^\n]{0,6}应付',
    '合约负债': r'合约负债',
    '银行贷款及借款': r'银行(贷款|借款)|^借款',
    '租赁负债': r'租赁负债|^租赁$',
    '现金及现金等价物': r'现金及现金等价物',
    '雇员福利': r'雇员福利|员工福利|退休福利|离职后福利|员工成本|雇员成本',
    '股本、储备及股息': r'股息|股本',
    '本公司财务状况及储备（可供分派储备）': r'本公司[^\n]{0,6}(财务状况|储备)|可供分派储备',
    '关键会计估计及判断': r'关键会计估计|会计判断',
    '金融风险管理': r'金融风险|财务风险',
    '承担及或然事项': r'承担|或然',
    '关联方交易': r'关(联|连)(方|人士)交易',
    '附属公司权益': r'附属公司',
    '期后事项': r'期后事项|报告期后|结算日后|日期?后[^\n]{0,6}事项',
}
HK_HINT = {'雇员福利': '员工成本多半在「除税前溢利」附注里，搜「員工成本」「薪金」'}
KAM_END = re.compile(r'^[ \t]*(其他信息|[^\n]{0,20}以外的信息|[^\n]{0,16}须承担的责任|核数师就[^\n]*承担的责任)', re.M)
AMOUNT = re.compile(r'^[ \t]*[(（\-–—]?[\d,，.]+[)）]?[ \t]*$')

def is_hk(text):
    return '综合财务状况表' in norm(text[:400000]) and '合并资产负债表' not in text

def hk_pages(text, N):
    """[(页码, 起, 止, 页眉)]：页眉 = 页首几行里第一行不是纯数字、不是每页都有的公司名 / 报告名的那行（去掉"（续）"）"""
    from collections import Counter
    ms = list(PAGE_RE.finditer(text)); pages, heads = [], []
    for i, m in enumerate(ms):
        a = m.end(); b = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        heads.append([l.strip() for l in N[a:b].split('\n') if l.strip()][:4]); pages.append((int(m.group(1)), a, b))
    cnt = Counter(l for h in heads for l in set(h))
    boiler = {l for l, c in cnt.items() if c > 0.6 * len(heads) and not any(re.search(kw, l) for kw in HK_PART.values())}
    out = []
    for (no, a, b), h in zip(pages, heads):
        hd = next((l for l in h if not re.fullmatch(r'[\d\s/╱\-–]+', l) and l not in boiler), '')
        out.append((no, a, b, re.sub(r'[（(]续[)）]$', '', hd)))
    return out

def hk_parts(pages):
    """栏目 → 页眉连续命中最长的一段 (首页, 末页, 起, 止)；目录页只一页，正文那段更长"""
    got = {}
    for name, kw in HK_PART.items():
        run = best = None
        for no, a, b, hd in pages:
            if hd and len(hd) <= 30 and re.search(kw, hd):
                run = (run[0], no, run[2], b) if run and run[1] == no - 1 else (no, no, a, b)
                if best is None or run[1] - run[0] > best[1] - best[0]: best = run
        if best: got[name] = best
    return got

def hk_notes(N, region):
    """附注区里递增编号的标题 → [(编号, 科目名, 起, 止)]；下一行是金额的是表格行，编号不接着上一条的不算"""
    a, b = region; hs = []
    for m in re.finditer(r'^[ \t]*(\d{1,2})[ \t]*(?:[.、．][ \t]*)?(?:\n[ \t]*|[ \t]+)([一-鿿][^\n]{0,40}?)[ \t]*$', N[a:b], re.M):
        nxt = re.search(r'\n[ \t]*([^\n]*\S)', N[a + m.end():a + m.end() + 200])
        if nxt and AMOUNT.match(nxt.group(1)) and not re.fullmatch(r'(19|20)\d\d', nxt.group(1).strip()): continue
        hs.append((int(m.group(1)), m.group(2), a + m.start()))
    notes = []; cur = 0
    for n, tt, p in hs:
        if n == cur + 1:
            if notes: notes[-1][3] = p
            notes.append([n, re.sub(r'[（(]续[)）]$', '', tt).strip(), p, b]); cur = n
    return [tuple(x) for x in notes]

def cut_hk(text, extra=()):
    """返回 (切好的段 [(名, 起, 止)], 没切到 [(名, 提示)], 原文定位 [(名, 页)], 各节 [(页眉, 首页)], 附注一览 [(编号, 名, 页)])"""
    N = norm(text); pg = Pages(text); pages = hk_pages(text, N); parts = hk_parts(pages)
    segs, miss, marks = [], [], []
    if '管理层讨论与分析' in parts: segs.append(('管理层讨论与分析', *parts['管理层讨论与分析'][2:]))
    else: miss.append(('管理层讨论与分析', '搜「管理層討論」「業務回顧」「財務回顧」'))
    if '财务摘要' in parts: segs.append(('财务摘要', *parts['财务摘要'][2:]))
    au = parts.get('核数师报告')
    k = re.search(r'^[ \t]*关键审计事项[ \t]*$', N[au[2]:au[3]], re.M) if au else None
    if k:
        st = au[2] + k.start(); e = KAM_END.search(N, st + 20, au[3])
        segs.append(('关键审计事项', st, e.start() if e else au[3]))
    elif au: miss.append(('关键审计事项', '搜「關鍵審計事項」（中期报告是审阅报告，没有这一节）'))
    for name in ('综合损益表', '综合财务状况表', '综合权益变动表', '综合现金流量表'):
        if name in parts: segs.append((name, *parts[name][2:])); marks.append((name, parts[name][0]))
        else: miss.append((name, f'搜「{name}」（繁体）'))
    notes = hk_notes(N, parts['财务报表附注'][2:]) if '财务报表附注' in parts else []
    want = dict(HK_NOTES); want.update({norm(x): re.escape(norm(x)) for x in extra})
    for name, kw in want.items():
        hit = next((x for x in notes if re.search(kw, x[1])), None)
        if hit: segs.append((f'{hit[0]}_{name}', hit[2], hit[3]))
        else: miss.append((name, HK_HINT.get(name, f'搜「{name}」（繁体）') + ('' if notes else '（没认出附注编号标题）')))
    secs = []; prev = None
    for no, a, b, hd in pages:
        if hd != prev and hd and len(hd) <= 30 and sum(1 for x in pages if x[3] == hd) >= 2: secs.append((hd, no))
        prev = hd
    return segs, miss, marks, secs, [(n, t, pg.at(p)) for n, t, p, _ in notes]

def cut_hk_write(text, pg, outdir, title, extra, save, got, miss, trunc):
    segs, ms, marks, secs, notes = cut_hk(text, extra)
    for name, a, b in segs: save(name, (a, b), None if name[0].isdigit() or name == '关键审计事项' else name)
    miss += ms
    L = [f'# {title} 目录索引（港股版式：繁体、香港财务报告准则）', '',
         f'全文 {pg.no[-1] if pg.no else 0} 页、{len(text)} 字：`{title}_全文.txt`（每页前一行 `=====PDF第N页=====`）。',
         '先读这份索引和下面切好的段；清单外的内容在全文里搜关键词（繁体），只读命中的那几页，不通读全文。',
         '科目对照：綜合財務狀況表 = 资产负债表，綜合損益表 = 利润表，貿易應付款項 ≈ 应付账款，合約負債 ≈ 合同负债，'
         '除稅前溢利 = 利润总额，核數師 = 审计师，附屬公司 = 子公司。', '',
         '## 各节起始页（按每页页眉）', '']
    L += [f'- {nm}：第 {p} 页' for nm, p in secs] or ['- （没认出页眉）']
    L += ['', '## 切好的段', '', '| 段 | 页码 | 字数 | 文件 |', '|---|---|---|---|']
    L += [f'| {n}{"（截断）" if n in trunc else ""} | {s} | {c} | `{f}` |' for n, s, c, f in got]
    L += ['', '## 附注编号一览（清单外的科目按这里的页码到全文里读）', '']
    L += [f'- 附注 {n} {t}：第 {p} 页' for n, t, p in notes] or ['- （没认出附注编号标题）']
    L += ['', '## 原文定位（只给起始页）', '']
    L += [f'- {n}：第 {p} 页' for n, p in marks] or ['- 无']
    L += ['', '## 清单里没切到的（不等于报告里没有：去全文里搜，查过写"查过：…"）', '']
    L += [f'- {n}：{h}' for n, h in miss] or ['- 无']
    if trunc: L += ['', f'截断的段只存了前 {CAP} 字，后面的去全文里按页码接着读。']
    open(os.path.join(outdir, f'{title}_目录索引.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return f'{title}（港股版式）全文{len(text)}字 / 切到 {len(got)} 段 / 没切到 {len(miss)} 项' + (f'（{"、".join(n for n, _ in miss)}）' if miss else '')

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
    hk = is_hk(text)

    def save(name, ab, fname=None):
        a, b = ab; seg = text[a:b]
        if len(seg) > CAP and name != '管理层讨论与分析':
            seg = seg[:CAP]; b = a + CAP; trunc.append(name)
        span = pg.span(a, b)
        w(fname or f'附注_{name}', f'【{title}·{name}，PDF {span}】\n' + seg)
        got.append((name, span, len(seg), f'{title}_{fname or "附注_" + name}.txt'))

    if hk: return cut_hk_write(text, pg, outdir, title, extra, save, got, miss, trunc)
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
    if not args or not os.path.isfile(args[0]): sys.exit(__doc__)
    pdf = args[0]; out = args[1] if len(args) > 1 else os.path.dirname(os.path.abspath(pdf))
    title = opt.get('title') or os.path.splitext(os.path.basename(pdf))[0]
    print(cut(pdf, out, title, [k for k in opt.get('notes', '').split(',') if k]))
