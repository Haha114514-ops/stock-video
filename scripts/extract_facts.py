"""从 fetch_data.py 的产出里提出读表要用的数，写成一份小的 facts.md（读表底稿：主控读它找原因、定判断标准；
上片的数仍在 facts.py 里冻结）。

用法:
    python extract_facts.py <工程目录> [--peers 代码1,代码2,代码3]

<工程目录>/data 下要有 fetch_data.py --no-reports 抓好的 is/bs/cf/indicator_em/value_em/zygc/fhps/px_raw.csv。
--peers 给出同行代码时，若 <工程目录>/peers/<代码> 不存在会调用同目录的 fetch_data.py 去抓。只支持 A 股。

输出（都在 <工程目录> 下）:
    facts.md          年度/最新期关键数、单季拆分、现金（经营−资本开支及筹资其他支付）、估值分位、分红、同行对比
    pb_series.csv     市净率双月序列（画估值历史图用，不要打印进对话）
金额单位：亿元；比率单位：%。
"""
import os, sys, subprocess
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def find_sv():
    """stock-video 目录（本脚本在它的 scripts/ 下）"""
    return os.path.dirname(HERE)


def rd(d, f):
    return pd.read_csv(os.path.join(d, f), encoding='utf-8')


def yi(v):
    return None if pd.isna(v) else round(v / 1e8, 2)


def g(row, col):
    v = row.get(col) if hasattr(row, 'get') else None
    return None if v is None or pd.isna(v) else v


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    proj = sys.argv[1]
    peers = []
    if '--peers' in sys.argv:
        peers = [c for c in sys.argv[sys.argv.index('--peers') + 1].split(',') if c]
    D = os.path.join(proj, 'data')
    out = []
    P = out.append

    is_, bs, cf, ind = rd(D, 'is.csv'), rd(D, 'bs.csv'), rd(D, 'cf.csv'), rd(D, 'indicator_em.csv')
    for t in (is_, bs, cf, ind):
        t['RD'] = t['REPORT_DATE'].str[:10]
    latest = is_['RD'].max()
    ly = str(int(latest[:4]) - 1) + latest[4:]
    keep = lambda t: t[(t.RD.str.endswith('12-31') & (t.RD >= '2018')) | t.RD.isin([latest, ly])].sort_values('RD')

    def table(t, cols, title):
        t = keep(t)
        P(f'\n## {title}（亿元）\n')
        P('| 期末 | ' + ' | '.join(cols) + ' |')
        P('|' + '---|' * (len(cols) + 1))
        for _, r in t.iterrows():
            P(f'| {r.RD} | ' + ' | '.join(str(yi(g(r, c))) for c in cols) + ' |')

    P(f'# facts（最新期 {latest}，对比期 {ly}）')
    table(is_, ['TOTAL_OPERATE_INCOME', 'OPERATE_COST', 'SALE_EXPENSE', 'MANAGE_EXPENSE', 'FINANCE_EXPENSE',
                'ASSET_IMPAIRMENT_INCOME', 'CREDIT_IMPAIRMENT_INCOME', 'OTHER_INCOME', 'NONBUSINESS_EXPENSE',
                'OPERATE_PROFIT', 'PARENT_NETPROFIT', 'DEDUCT_PARENT_NETPROFIT'], '利润表')
    table(bs, ['MONETARYFUNDS', 'TRADE_FINASSET_NOTFVTPL', 'ACCOUNTS_RECE', 'INVENTORY', 'USERIGHT_ASSET', 'FIXED_ASSET',
               'GOODWILL', 'TOTAL_ASSETS', 'SHORT_LOAN', 'LONG_LOAN', 'NOTE_ACCOUNTS_PAYABLE', 'LEASE_LIAB',
               'NONCURRENT_LIAB_1YEAR', 'TOTAL_LIABILITIES', 'TOTAL_PARENT_EQUITY'], '资产负债表')
    table(cf, ['NETCASH_OPERATE', 'CONSTRUCT_LONG_ASSET', 'PAY_OTHER_FINANCE', 'ASSIGN_DIVIDEND_PORFIT'], '现金流量表')

    # 股东可得现金：经营现金流 − 资本开支；"支付其他与筹资活动有关的现金"单列，
    # 它是不是刚性支出（租赁付款等）因公司而异，要看附注再决定扣不扣
    P('\n## 现金：经营现金流 − 资本开支，及筹资里的其他支付（亿元；后者是否刚性支出看附注）\n')
    P('| 期末 | 经营现金流−资本开支 | 支付其他筹资 | 两者相减 | 分红付息（含利息、含上年末期） |')
    P('|---|---|---|---|---|')
    for _, r in keep(cf).iterrows():
        ocf, capex, oth = (g(r, c) or 0 for c in ('NETCASH_OPERATE', 'CONSTRUCT_LONG_ASSET', 'PAY_OTHER_FINANCE'))
        P(f'| {r.RD} | {yi(ocf - capex)} | {yi(oth)} | {yi(ocf - capex - oth)} | {yi(g(r, "ASSIGN_DIVIDEND_PORFIT"))} |')

    # 单季拆分：用部分期间外推全年之前先看各季度分布（不预设哪个季度强弱）
    P('\n## 单季拆分（亿元，由累计数相减得到）\n')
    qc = ['TOTAL_OPERATE_INCOME', 'OPERATE_PROFIT', 'PARENT_NETPROFIT', 'DEDUCT_PARENT_NETPROFIT']
    ends = [('Q1', '03-31', None), ('Q2', '06-30', '03-31'), ('Q3', '09-30', '06-30'), ('Q4', '12-31', '09-30')]
    cum = {r.RD: r for _, r in is_.iterrows()}
    P('| 年 | 季 | ' + ' | '.join(qc) + ' |')
    P('|' + '---|' * (len(qc) + 2))
    single = {}
    for y in range(int(latest[:4]) - 3, int(latest[:4]) + 1):
        for q, e, pe in ends:
            a = cum.get(f'{y}-{e}')
            if a is None:
                continue
            b = cum.get(f'{y}-{pe}') if pe else None
            vals = {c: (g(a, c) or 0) - ((g(b, c) or 0) if b is not None else 0) for c in qc}
            single[(y, q)] = vals
            P(f'| {y} | {q} | ' + ' | '.join(str(yi(vals[c])) for c in qc) + ' |')
    P('\n各季度归母净利润占全年（%，全年为负或接近零时不算）：')
    for y in range(int(latest[:4]) - 3, int(latest[:4])):
        if all((y, q) in single for q, _, _ in ends):
            fy = sum(single[(y, q)]['PARENT_NETPROFIT'] for q, _, _ in ends)
            if fy > 1e7:
                P(f'- {y}：' + '，'.join(f'{q} {round(single[(y, q)]["PARENT_NETPROFIT"] / fy * 100)}%' for q, _, _ in ends))
            else:
                P(f'- {y}：全年归母 {yi(fy)} 亿元，占比不适用')

    # 比率
    P('\n## 比率（%）\n')
    rc = ['XSMLL', 'XSJLL', 'ROEJQ', 'ZCFZL', 'CHZZTS', 'YSZKZZTS', 'TOTALOPERATEREVETZ', 'PARENTNETPROFITTZ']
    P('| 期末 | 毛利率 | 净利率 | ROE | 资产负债率 | 存货天数 | 应收天数 | 收入同比 | 归母净利同比 |')
    P('|' + '---|' * 9)
    for _, r in keep(ind).iterrows():
        P(f'| {r.RD} | ' + ' | '.join(str(None if g(r, c) is None else round(g(r, c), 2)) for c in rc) + ' |')

    # 估值
    v = rd(D, 'value_em.csv')
    last = v.iloc[-1]
    P(f'\n## 估值（{last["数据日期"]} 收盘）\n')
    P(f'- 收盘价 {last["当日收盘价"]} 元，总市值 {yi(last["总市值"])} 亿元，总股本 {round(last["总股本"] / 1e8, 3)} 亿股')
    for c in ('PE(TTM)', '市净率', '市销率'):
        s = v[c].dropna()
        cur = s.iloc[-1]
        P(f'- {c} {round(cur, 2)}：全部历史分位 {round((s < cur).mean() * 100, 1)}%，近5年分位 '
          f'{round((s.tail(1215) < cur).mean() * 100, 1)}%，中位数 {round(s.median(), 2)}，区间 {round(s.min(), 2)}~{round(s.max(), 2)}')
    v['m'] = v['数据日期'].str[:7]
    v.groupby('m').last().iloc[::2][['市净率', 'PE(TTM)']].round(2).to_csv(os.path.join(proj, 'pb_series.csv'), encoding='utf-8')
    px = rd(D, 'px_raw.csv').rename(columns={'日期': 'date', '收盘': 'close'})  # fetch_data 两种行情源列名不同
    px['date'] = px['date'].astype(str)
    px['y'] = px.date.str[:4]
    yr = px.groupby('y').close.agg(['min', 'max', 'last']).tail(6)
    P('- 年度收盘（未复权，最低/最高/年末）：' + '；'.join(f'{y} {r["min"]}/{r["max"]}/{r["last"]}' for y, r in yr.iterrows()))
    for y in yr.index[:-1]:
        ye = v[v['数据日期'] <= f'{y}-12-31'].tail(1)
        if not ye.empty:
            P(f'  - {y} 年末：收盘 {ye.iloc[0]["当日收盘价"]}，PE(TTM) {round(ye.iloc[0]["PE(TTM)"], 1)}，市净率 {round(ye.iloc[0]["市净率"], 2)}')

    # 分红：近 12 个月每股（按除权除息日）
    f = rd(D, 'fhps.csv')
    cut = (pd.to_datetime(last['数据日期']) - pd.Timedelta(days=365)).strftime('%Y-%m-%d')
    recent = f[f['除权除息日'].astype(str) >= cut]
    dps = recent['现金分红-现金分红比例'].fillna(0).sum() / 10
    P(f'- 近12个月每股现金分红 {round(dps, 3)} 元（{len(recent)} 次），股息率 {round(dps / last["当日收盘价"] * 100, 2)}%，'
      f'一年分红总额约 {round(dps * last["总股本"] / 1e8, 2)} 亿元')

    # 主营构成最新一期
    z = rd(D, 'zygc.csv')
    zl = z[z['报告日期'] == z['报告日期'].max()]
    P(f'\n## 主营构成（{z["报告日期"].max()}）\n')
    P('| 分类 | 项目 | 收入(亿) | 收入占比% | 毛利率% |')
    P('|---|---|---|---|---|')
    for _, r in zl.iterrows():
        P(f'| {r["分类类型"]} | {r["主营构成"]} | {yi(r["主营收入"])} | {round(r["收入比例"] * 100, 1)} | '
          f'{None if pd.isna(r["毛利率"]) else round(r["毛利率"] * 100, 1)} |')

    # 同行
    if peers:
        sv = find_sv()
        P('\n## 同行对比（估值为最新收盘，经营数据为最新期）\n')
        P('| 代码 | 收盘日 | PE(TTM) | 市净率 | 市销率 | 最新期收入同比% | 最新期归母净利同比% | 毛利率% | 净利率% |')
        P('|---|---|---|---|---|---|---|---|---|')
        for code in [os.path.basename(proj.rstrip('/\\')).split('_')[-1]] + peers:
            pdir = D if code not in peers else os.path.join(proj, 'peers', code)
            if code in peers and not os.path.exists(os.path.join(pdir, 'value_em.csv')):
                subprocess.run([sys.executable, os.path.join(sv, 'scripts', 'fetch_data.py'), code, pdir, '--no-reports'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                pv = rd(pdir, 'value_em.csv').iloc[-1]
                pi = rd(pdir, 'indicator_em.csv')
                pi = pi.sort_values('REPORT_DATE').iloc[-1]
                P(f'| {code} | {pv["数据日期"]} | {round(pv["PE(TTM)"], 1)} | {round(pv["市净率"], 2)} | {round(pv["市销率"], 2)} | '
                  f'{round(pi["TOTALOPERATEREVETZ"], 1)} | {round(pi["PARENTNETPROFITTZ"], 1)} | {round(pi["XSMLL"], 1)} | {round(pi["XSJLL"], 1)} |')
            except Exception as e:
                P(f'| {code} | 取数失败：{type(e).__name__} | | | | | | | |')

    path = os.path.join(proj, 'facts.md')
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(out) + '\n')
    print('ok', path, len('\n'.join(out)), 'chars')


if __name__ == '__main__':
    main()
