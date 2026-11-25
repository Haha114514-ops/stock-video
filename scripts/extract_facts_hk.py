# -*- coding: utf-8 -*-
"""港股读表底稿（57号补丁三十六）：读 fetch_hk.py 的产出 → <工程>/facts.md。A 股用 extract_facts.py。
用法：python extract_facts_hk.py <工程> [--peers 代码1,代码2,...] [--cutoff YYYY-MM-DD] [--out 路径]
  --peers   同行（默认 data/ 里所有 comp_<代码>_*.csv）
  --cutoff  截止日（默认 price.csv 最后一天）；估值、股价序列截到这天，晚于截止日的点丢掉并在日志里写明
  --out     默认 <工程>/facts.md
内容：
  三表：东财港股模板的全部科目（按科目编码顺序，全为 0 的不列），近 5 个年度 + 近 3 个中期；利润表附毛利率、税率、少数股东占比
  上下半年拆分：下半年 = 全年 − 中期（非 12 月年结按年结日对齐，3/31 年结的中期是 9/30）
  资产负债表派生：有息负债、现金（含受限）、净负债、净负债 / 总权益；有永续 / 其他权益工具时另列普通股东权益
  估值：PB、PE TTM 十年和近 5 年分位、现值以下占比；停牌期冻结不动的点（连续 4 点以上同值）剔除，不进分位和中位数
  普通股东口径 PE：有永续时，归母口径（市值 / 股东应占溢利 TTM）和普通股东口径（股价 / 每股盈利 TTM）并列
  股价、派息、同行（PB / PE 现值和分位、最新年度收入归母毛利率；有 comp_<代码>_bs.csv 时加净负债率）、控股公司对比上市子公司市值（sub_<代码>_mcap.csv）
提醒（东财港股科目合并的坑，facts.md 开头列出）：受限存款可能并进"中长期存款"、发展中物业可能并进"投资物业"或"存货"、
合约负债可能并进"其他应付款"——涉及这几项的数标"按报告附注重拆"，以报告原数为准。"""
import io, os, re, sys
import pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

argv, args, opt, i = sys.argv[1:], [], {}, 0
while i < len(argv):   # --k=v 和 --k v 都认
    a = argv[i]
    if a.startswith('--'):
        k, eq, v = a[2:].partition('=')
        if not eq and i + 1 < len(argv) and not argv[i + 1].startswith('--'): v = argv[i + 1]; i += 1
        opt[k] = v
    else: args.append(a)
    i += 1
if not args or not os.path.isdir(os.path.join(args[0], 'data')): sys.exit(__doc__)
P = args[0]; D = os.path.join(P, 'data'); OUT = opt.get('out') or os.path.join(P, 'facts.md')
out, logs = [], []
def w(s=''): out.append(s)
def f1(x): return '-' if x is None or pd.isna(x) else f'{x:,.1f}'
def csv(name):
    p = os.path.join(D, name)
    return pd.read_csv(p) if os.path.exists(p) else None

# ---------- 三表 ----------
def load(st):
    df = csv(f'fin_{st}.csv')
    if df is None: logs.append(f'缺 fin_{st}.csv'); return None
    df['d'] = df.REPORT_DATE.astype(str).str[:10]
    return df
FIN = {st: load(st) for st in ('利润表', '资产负债表', '现金流量表')}
base = next((x for x in FIN.values() if x is not None), None)
if base is None: sys.exit('data/ 里没有 fin_*.csv：先跑 fetch_hk.py')
name = str(base.SECURITY_NAME_ABBR.iloc[0]); code = str(base.SECURITY_CODE.iloc[0]).zfill(5)

# 年结日、财年变更
per = base.drop_duplicates('d')[['d', 'DATE_TYPE_CODE', 'FISCAL_YEAR']].sort_values('d')
fy = per.FISCAL_YEAR.astype(str)
if fy.nunique() > 1:
    ch = [(a, b, d) for (a, b, d) in zip(fy.shift(), fy, per.d) if a != b and isinstance(a, str) and a != 'nan']
    logs.append('**财年变更**：' + '；'.join(f'{d} 起年结日 {a} → {b}' for a, b, d in ch) + '。变更前后的"年度"长度可能不是 12 个月，同比要按报告说明重算。')
ann = sorted(per[per.DATE_TYPE_CODE.astype(int) == 1].d)
itm = sorted(per[per.DATE_TYPE_CODE.astype(int) == 2].d)
for a, b in zip(ann, ann[1:]):
    gap = (pd.Timestamp(b) - pd.Timestamp(a)).days
    if not 350 <= gap <= 380: logs.append(f'**年度间隔异常**：{a} → {b} 相隔 {gap} 天（财年变更或缺期），这两年不能直接比。')
other = sorted(set(per.d) - set(ann) - set(itm))
if other: logs.append(f'还有季度 / 其他期次（未列入表）：{", ".join(other[-4:])}')
ye = fy.iloc[-1]
COLS = ann[-5:] + itm[-3:]
lab = lambda d: d[:7] + ('年' if d in ann else '中')

def piv(df):
    df = df[df.d.isin(COLS)]
    order = df.drop_duplicates('STD_ITEM_NAME').sort_values('STD_ITEM_CODE').STD_ITEM_NAME.tolist()
    t = df.pivot_table(index='STD_ITEM_NAME', columns='d', values='AMOUNT', aggfunc='first') / 1e8
    t = t.reindex(order)
    return t[(t.fillna(0) != 0).any(axis=1)]

def pick(t, *names):
    for n in names:
        for k in t.index:
            if re.fullmatch(n, k): return k
    return None

def g(t, k, c):
    if t is None or k is None or c not in t.columns: return None
    v = t.loc[k, c]; return None if pd.isna(v) else float(v)

def table(t, title, extra=()):
    cols = [c for c in COLS if c in t.columns]
    w(f'### {title}（亿元人民币；东财折算，中期未经审计，"中"= 中期累计）')
    w('| 科目 | ' + ' | '.join(lab(c) for c in cols) + ' |'); w('|---' * (len(cols) + 1) + '|')
    for k in t.index: w(f'| {k} | ' + ' | '.join(f1(g(t, k, c)) for c in cols) + ' |')
    for nm, fn in extra: w(f'| **{nm}** | ' + ' | '.join(fn(c) for c in cols) + ' |')
    w()

pct = lambda a, b: '-' if a is None or not b else f'{a / b * 100:.1f}'
w(f'# {name} {code} 读表底稿（港股）'); w()
w(f'年结日 {ye}；年度 {len(ann)} 期、中期 {len(itm)} 期（东财港股三表，金额已折算人民币亿元）。上片的数仍在 facts.py 里冻结，关键数字以报告原文为准。'); w()

IS = piv(FIN['利润表']) if FIN['利润表'] is not None else None
BS = piv(FIN['资产负债表']) if FIN['资产负债表'] is not None else None
CF = piv(FIN['现金流量表']) if FIN['现金流量表'] is not None else None

# ---------- 提醒（东财港股科目合并） ----------
w('## 提醒：东财港股科目合并的坑（涉及的数标"按报告附注重拆"）')
tips = []
if BS is not None:
    if pick(BS, r'中长期存款'): tips.append('有"中长期存款"：受限存款 / 质押存款可能并在这里，现金和净负债按报告附注重拆。')
    if pick(BS, r'投资物业') and not pick(BS, r'发展中.*|.*待售物业|在建.*物业'): tips.append('有"投资物业"没有"发展中 / 待售物业"：发展中物业可能并进了投资物业或存货，按报告附注重拆。')
    if pick(BS, r'其他应付款.*') and not pick(BS, r'合同负债|合约负债|预收.*'): tips.append('没有"合同负债"单列：合约负债可能并进"其他应付款"，按报告附注重拆。')
tips.append('资产负债表总览（总资产、总负债、权益）用报告原数；东财模板把若干科目合并，小项相加不一定等于报告的分项。')
tips.append('中期数据未经审计；非人民币列报的公司，东财折算只看趋势，关键数字从报告原文取。')
for t in tips: w(f'- {t}')
for l in logs: w(f'- {l}')
w()

# ---------- 利润表 ----------
if IS is not None:
    rev = pick(IS, r'营业额', r'营运收入', r'经营收入总额', r'收益', r'.*收入'); gp = pick(IS, r'毛利')
    pbt = pick(IS, r'除税前.*'); tax = pick(IS, r'税项', r'.*所得税.*'); npf = pick(IS, r'除税后.*', r'.*年度溢利.*')
    mi = pick(IS, r'少数股东损益', r'非控.*'); par = pick(IS, r'股东应占.*', r'.*本公司.*')
    table(IS, '利润表', [
        ('毛利率%', lambda c: pct(g(IS, gp, c), g(IS, rev, c))),
        ('税项 / 除税前%', lambda c: pct(g(IS, tax, c), g(IS, pbt, c))),
        ('少数股东 / 除税后%', lambda c: pct(g(IS, mi, c), g(IS, npf, c))),
        ('股东应占 / 收入%', lambda c: pct(g(IS, par, c), g(IS, rev, c)))])
    pairs = []
    for a in ann:
        h = [i for i in itm if pd.Timestamp(a) - pd.Timedelta(days=366) < pd.Timestamp(i) < pd.Timestamp(a)]
        if h: pairs.append((a, h[-1]))
    if pairs:
        w('### 上下半年拆分（下半年 = 全年 − 中期）'); w('| 年度 | 上半年收入 | 下半年收入 | 上半年占% | 上半年股东应占 | 下半年股东应占 | 上半年毛利率% | 下半年毛利率% |'); w('|---|---|---|---|---|---|---|---|')
        for a, h in pairs[-5:]:
            r1, ra = g(IS, rev, h), g(IS, rev, a); p1, pa = g(IS, par, h), g(IS, par, a); g1, ga = g(IS, gp, h), g(IS, gp, a)
            if r1 is None or ra is None: continue
            w(f'| {a[:7]} | {f1(r1)} | {f1(ra - r1)} | {pct(r1, ra)} | {f1(p1)} | {f1(pa - p1) if pa is not None and p1 is not None else "-"} | '
              f'{pct(g1, r1)} | {pct(ga - g1, ra - r1) if ga is not None and g1 is not None else "-"} |')
        w()

# ---------- 资产负债表 ----------
if BS is not None:
    debt_k = [k for k in BS.index if re.search(r'贷款|借款|借贷|票据|债券|融资', k) and not re.search(r'应收|资产|投资|租赁', k)]
    cash_k = [k for k in BS.index if re.search(r'现金|受限制|存款', k) and not re.search(r'负债|应付', k)]
    perp_k = [k for k in BS.index if re.search(r'永续|永久|其他权益工具|资本证券', k)]
    eq = pick(BS, r'股东权益', r'本公司.*权益.*'); tot = pick(BS, r'总权益', r'权益总额')
    s = lambda ks, c: sum(g(BS, k, c) or 0 for k in ks)
    ex = [(f'有息负债（{"+".join(debt_k) or "无"}；不含租赁）', lambda c: f1(s(debt_k, c))),
          (f'现金（{"+".join(cash_k) or "无"}）', lambda c: f1(s(cash_k, c))),
          ('净负债', lambda c: f1(s(debt_k, c) - s(cash_k, c))),
          ('净负债 / 总权益%', lambda c: pct(s(debt_k, c) - s(cash_k, c), g(BS, tot, c)))]
    if perp_k and eq: ex.append((f'普通股东权益（{eq} − {"−".join(perp_k)}）', lambda c: f1((g(BS, eq, c) or 0) - s(perp_k, c))))
    table(BS, '资产负债表', ex)
    if perp_k: w(f'- 有永续 / 其他权益工具（{"、".join(perp_k)}）：PB、ROE、PE 用普通股东口径，PE 见估值下面"PE 两种口径"。'); w()

if CF is not None: table(CF, '现金流量表')

# ---------- 估值 ----------
pr = csv('price.csv')
if pr is not None:
    pr = pr.rename(columns={pr.columns[0]: '日期'}); pr['日期'] = pd.to_datetime(pr['日期'])
cut = pd.Timestamp(opt['cutoff']) if opt.get('cutoff') else (pr['日期'].max() if pr is not None else None)

# 停牌期：本股 price.csv 里相邻两个交易日相隔超过 10 天的区间；同行没有日线，用"连续 12 点（约 60 天）同值"认冻结
GAPS = []
if pr is not None:
    dd = pr['日期'].sort_values().reset_index(drop=True)
    GAPS = [(a, b) for a, b in zip(dd, dd[1:]) if (b - a).days > 10]

def series(f, own=False):
    s = csv(f)
    if s is None: return None, ''
    s['date'] = pd.to_datetime(s.date); s = s.dropna(subset=['value']).sort_values('date'); note = []
    if cut is not None and (s.date > cut).any():
        note.append(f'截止日后 {int((s.date > cut).sum())} 点已丢'); s = s[s.date <= cut]
    run = (s.value != s.value.shift()).cumsum(); n = s.groupby(run).value.transform('size')
    frz = (n >= 12) & (s.value == s.value.shift())
    if own:
        for a, b in GAPS: frz |= (s.date > a) & (s.date < b)
    if frz.any():
        d = s[frz].date; note.append(f'停牌期冻结值 {int(frz.sum())} 点已剔除（{d.min().date()}~{d.max().date()}），不进分位和中位数'); s = s[~frz]
    return s.reset_index(drop=True), '；'.join(note)

def qline(s, label):
    now = s.value.iloc[-1]; v = s.value[s.value > 0]
    if now <= 0: return f'{label}：现值为负（亏损或净资产为负），不算分位'
    if not len(v): return f'{label}：现值 {now}（全为负，不算分位）'
    return (f'{label}：p20 {v.quantile(.2):.2f} / p50 {v.quantile(.5):.2f} / p80 {v.quantile(.8):.2f}，现值以下占 {(v < now).mean() * 100:.0f}%，'
            f'最低 {v.min():.2f}（{s.date[v.idxmin()].date()}）最高 {v.max():.2f}（{s.date[v.idxmax()].date()}）' + ('；负值不进分位' if (s.value <= 0).any() else ''))

w(f'## 估值（百度，近十年 5 天一点；截止 {cut.date() if cut is not None else "?"}）')
for f, nm in (('val_pb.csv', 'PB'), ('val_pe_ttm.csv', 'PE TTM'), ('val_mcap.csv', '总市值（亿港元）')):
    s, note = series(f, own=True)
    if s is None or not len(s): w(f'- {nm}：缺 {f}'); continue
    w(f'- {nm} 现值 {s.value.iloc[-1]}（{s.date.iloc[-1].date()}）' + (f'（{note}）' if note else ''))
    if nm != '总市值（亿港元）':
        w('  - 十年 ' + qline(s, '')); w('  - 近 5 年 ' + qline(s[s.date >= s.date.iloc[-1] - pd.Timedelta(days=1826)].reset_index(drop=True), ''))

# 普通股东口径 PE：东财"股东应占溢利"含永续 / 其他权益工具持有人那份，百度 PE 的分母也含；
# 普通股东利润 = 报告的每股基本盈利（BASIC_EPS，已扣永续）× 股数。EPS_TTM 是东财用股东应占溢利自算的，不用。
def ttm(m):
    """{期末日: 累计值} → 最近 12 个月：最新年度 + 最新中期 − 上年同期中期"""
    a_ = [d for d in ann if d in m and pd.notna(m[d])]; i_ = [d for d in itm if d in m and pd.notna(m[d])]
    if not a_: return None, ''
    if i_ and i_[-1] > a_[-1]:
        prev = [d for d in i_ if 300 < (pd.Timestamp(i_[-1]) - pd.Timestamp(d)).days < 380]
        if prev: return m[a_[-1]] + m[i_[-1]] - m[prev[-1]], f'{a_[-1][:7]} 年 + {i_[-1][:7]} 中 − {prev[-1][:7]} 中'
    return m[a_[-1]], f'{a_[-1][:7]} 年'
ind = csv('indicator_hk.csv'); mc, _ = series('val_mcap.csv', own=True)
FX = float(opt['fx']) if opt.get('fx') else None
fxf = csv('fx.csv')
if FX is None and fxf is not None and len(fxf) and cut is not None:
    fxf['日期'] = pd.to_datetime(fxf['日期']); r = fxf[fxf['日期'] <= cut]
    if len(r): FX = float(r['港元'].iloc[-1]) / 100
perp = BS is not None and any(re.search(r'永续|永久|其他权益工具|资本证券', k) for k in BS.index)
if ind is not None and pr is not None and mc is not None and len(mc) and IS is not None:
    ind['d'] = ind.REPORT_DATE.astype(str).str[:10]
    px = pr[pr['日期'] <= cut]['收盘'].iloc[-1]; mcap = mc.value.iloc[-1]; sh = mcap / px   # 亿股
    eps, eps_src = ttm(dict(zip(ind.d, ind.BASIC_EPS)))
    par_all = FIN['利润表'][FIN['利润表'].STD_ITEM_NAME == par] if par else None
    hold, hold_src = ttm(dict(zip(par_all.d, par_all.AMOUNT / 1e8))) if par_all is not None and len(par_all) else (None, '')
    w(f'### PE 两种口径（{"有永续 / 其他权益工具，用普通股东口径" if perp else "资产负债表里没有永续科目；两种口径差得多时查股数变动（配股、重组发股）或报告里的其他权益工具"}）')
    w(f'- 股数 ≈ 市值 {mcap} 亿港元 / 股价 {px} = {sh:.1f} 亿股；汇率 ' + (f'1 港元 = {FX:.4f} 元人民币' if FX else '缺（跑新版 fetch_hk.py 出 fx.csv，或加 --fx）'))
    if hold is not None:
        w(f'- 股东应占溢利 TTM（{hold_src}）{hold:.1f} 亿元' + (f' → PE {mcap * FX / hold:.1f} 倍' if FX and hold > 0 else '（≤0 或缺汇率，不算 PE）'))
    if eps is not None:
        com = eps * sh
        w(f'- 普通股东利润 TTM = 每股基本盈利（{eps_src}）{eps:.4f} × {sh:.1f} 亿股 = {com:.1f} 亿元' + (f' → PE **{mcap * FX / com:.1f} 倍**' if FX and com > 0 else '（≤0 或缺汇率，不算 PE）'))
        if hold is not None: w(f'  - 差额 {hold - com:.1f} 亿元 ≈ 永续 / 其他权益工具持有人应占（每股盈利按报告币种；人民币列报的公司即人民币，非人民币列报先核对币种）')
    w()

if pr is not None:
    p = pr[pr['日期'] <= cut]; lastd = p['日期'].iloc[-1]; y1 = p[p['日期'] > lastd - pd.Timedelta(days=365)]
    hi, lo = y1.loc[y1['最高'].idxmax()], y1.loc[y1['最低'].idxmin()]
    w(f'## 股价（港元，不复权）'); w(f'- 截止 {lastd.date()} 收 {p["收盘"].iloc[-1]}；近一年最高 {hi["最高"]}（{hi["日期"].date()}）最低 {lo["最低"]}（{lo["日期"].date()}）；一年前收 {y1["收盘"].iloc[0]}')
    w('- 年结日收盘：' + '，'.join(f'{a[:7]} {p[p["日期"] <= a]["收盘"].iloc[-1]}' for a in ann[-6:] if (p['日期'] <= a).any()))
    fx = csv('fx.csv')
    if fx is not None and len(fx):
        fx['日期'] = pd.to_datetime(fx['日期']); r = fx[fx['日期'] <= cut].iloc[-1]
        w(f'- 港元兑人民币（人民银行中间价）{r["日期"].date()}：100 港元 = {r["港元"]} 元人民币')
    w()

dv = csv('dividend.csv')
if dv is not None:
    w('## 派息（东财，最近 10 条）')
    for r in dv.head(10).itertuples(index=False): w('- ' + ' | '.join(str(x) for x in r))
    w()

# ---------- 同行 ----------
peers = [x.zfill(5) for x in opt.get('peers', '').split(',') if x] or sorted({m.group(1) for f in os.listdir(D) for m in [re.match(r'comp_(\d+)_', f)] if m})
if peers:
    w('## 同行（百度 PB / PE 现值和十年分位；东财最新年度）')
    for c in peers:
        row = [c]
        for k in ('pb', 'pe'):
            s, note = series(f'comp_{c}_{k}.csv')
            if s is None or not len(s): continue
            v = s.value[s.value > 0]; now = s.value.iloc[-1]
            row.append(f'{k.upper()} {now}' + (f'（十年现值以下 {(v < now).mean() * 100:.0f}%）' if len(v) and now > 0 else '（为负，不算分位）' if now <= 0 else '') + (f'〔{note}〕' if note else ''))
        t = csv(f'comp_{c}_is.csv')
        if t is not None and len(t):
            t['d'] = t.REPORT_DATE.astype(str).str[:10]; row[0] = f'{t.SECURITY_NAME_ABBR.iloc[0]} {c}'; d = t.d.max()
            sub = t[t.d == d].set_index('STD_ITEM_NAME').AMOUNT / 1e8
            r_ = next((sub[k] for k in ('营业额', '营运收入', '经营收入总额', '收益') if k in sub), None)
            p_ = next((sub[k] for k in sub.index if k.startswith('股东应占')), None)
            row.append(f'{d[:7]} 收入 {f1(r_)} 股东应占 {f1(p_)} 毛利率 {pct(sub.get("毛利"), r_)}%')
        b = csv(f'comp_{c}_bs.csv')
        if b is not None and len(b):
            b['d'] = b.REPORT_DATE.astype(str).str[:10]; sb = b[b.d == b.d.max()].set_index('STD_ITEM_NAME').AMOUNT / 1e8
            dk = [k for k in sb.index if re.search(r'贷款|借款|借贷|票据|债券', k) and not re.search(r'应收|资产|投资', k)]
            ck = [k for k in sb.index if re.search(r'现金|受限制|存款', k) and not re.search(r'负债|应付', k)]
            te = next((sb[k] for k in ('总权益', '权益总额') if k in sb), None)
            nd = sb[dk].sum() - sb[ck].sum()
            row.append(f'{b.d.max()[:7]} 净负债 {f1(nd)} 亿' + (f'，净负债 / 总权益 {nd / te * 100:.0f}%' if te else ''))
        w('- ' + ' | '.join(row))
    w()

subs = sorted({m.group(1) for f in os.listdir(D) for m in [re.match(r'sub_(\d+)_mcap\.csv', f)] if m})
if subs and mc is not None and len(mc):
    w('## 控股公司 vs 上市子公司市值（亿港元；持股比例从年报附注取，算"子公司按持股折算的市值 / 母公司市值"）')
    w(f'- 母公司 {code}：{mc.value.iloc[-1]}')
    for c in subs:
        s, note = series(f'sub_{c}_mcap.csv')
        if s is not None and len(s): w(f'- 子公司 {c}：{s.value.iloc[-1]}（{s.date.iloc[-1].date()}）' + (f'〔{note}〕' if note else ''))
    w()

open(OUT, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(f'{OUT}：{len(chr(10).join(out))} 字；' + ('；'.join(re.sub(r'\*', '', l) for l in logs) if logs else '无财年 / 期次异常'))
