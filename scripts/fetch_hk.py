# -*- coding: utf-8 -*-
"""港股个股数据抓取（东财 / 新浪 / 百度），失败项记日志不中断。fetch_data.py 只管 A 股，港股用这个。
用法：python fetch_hk.py <代码如03918> <输出目录> [同行港股代码 ...]
产出：
  price.csv            日线（不复权；东财断连回退新浪）  列：日期,open,最高,最低,收盘,volume,amount
  price_qfq.csv        前复权日线（算长期涨跌用）
  fin_利润表/资产负债表/现金流量表.csv   东财港股三大表长表（REPORT_DATE, STD_ITEM_NAME, AMOUNT；年度 + 中期）
  indicator_hk.csv     东财港股财务指标（按报告期）
  val_pe_ttm.csv / val_pb.csv / val_mcap.csv   百度估值序列（近十年，5 天一点）
  dividend.csv         东财派息记录（含每股派息、币种、除净日）
  profile.csv          公司资料
  comp_<代码>_*.csv    同行：三大表利润表 + 百度 PE/PB
  fetch_log.json
港股年报/中报原文不自动抓：去 hkexnews.hk（披露易）下载 PDF 放进 <工程>/data/reports/，
用 fitz 抽文本后在 facts.py 里逐条注明页码（口径见 方法与口径 §1 港股条）。"""
import io, json, os, sys, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')
import akshare as ak

args = [a for a in sys.argv[1:] if not a.startswith('--')]
if len(args) < 2 or not args[0].isdigit(): sys.exit(__doc__)
code, OUT, peers = args[0].zfill(5), args[1], [p.zfill(5) for p in args[2:]]   # 港股代码补足 5 位：3918 → 03918
os.makedirs(OUT, exist_ok=True)
log = {}

def grab(name, fn, *a, **k):
    for i in range(3):
        try:
            df = fn(*a, **k)
            if df is None or len(df) == 0: raise ValueError('空表')
            df.to_csv(os.path.join(OUT, name), index=False, encoding='utf-8-sig')
            log[name] = len(df); print('ok', name, len(df)); return df
        except Exception as e:
            print('retry', name, i, repr(e)[:160]); time.sleep(2 + 2 * i)
    log[name] = 'FAIL: ' + traceback.format_exc(limit=1)[-200:]
    return None

def price(nm, adj):
    df = grab(nm, ak.stock_hk_hist, symbol=code, period='daily', start_date='20000101', end_date='20991231', adjust=adj)
    if df is not None:
        df = df[['日期', '开盘', '最高', '最低', '收盘', '成交量', '成交额']]
        df.columns = ['日期', 'open', '最高', '最低', '收盘', 'volume', 'amount']
    else:   # 新浪回退
        df = grab(nm, ak.stock_hk_daily, symbol=code, adjust=adj)
        if df is None: return
        df = df.rename(columns={'date': '日期', 'high': '最高', 'low': '最低', 'close': '收盘'})
        df = df[['日期', 'open', '最高', '最低', '收盘', 'volume'] + (['amount'] if 'amount' in df else [])]
    df.to_csv(os.path.join(OUT, nm), index=False, encoding='utf-8-sig')

price('price.csv', '')
price('price_qfq.csv', 'qfq')
for st in ('利润表', '资产负债表', '现金流量表'):
    grab(f'fin_{st}.csv', ak.stock_financial_hk_report_em, stock=code, symbol=st, indicator='报告期')
grab('indicator_hk.csv', ak.stock_financial_hk_analysis_indicator_em, symbol=code, indicator='报告期')
for ind, nm in (('市盈率(TTM)', 'val_pe_ttm.csv'), ('市净率', 'val_pb.csv'), ('总市值', 'val_mcap.csv')):
    grab(nm, ak.stock_hk_valuation_baidu, symbol=code, indicator=ind, period='近十年')
grab('dividend.csv', ak.stock_hk_dividend_payout_em, symbol=code)
grab('profile.csv', ak.stock_hk_company_profile_em, symbol=code)
for p in peers:
    grab(f'comp_{p}_is.csv', ak.stock_financial_hk_report_em, stock=p, symbol='利润表', indicator='年度')
    grab(f'comp_{p}_pe.csv', ak.stock_hk_valuation_baidu, symbol=p, indicator='市盈率(TTM)', period='近十年')
    grab(f'comp_{p}_pb.csv', ak.stock_hk_valuation_baidu, symbol=p, indicator='市净率', period='近十年')
with open(os.path.join(OUT, 'fetch_log.json'), 'w', encoding='utf-8') as fp: json.dump(log, fp, ensure_ascii=False, indent=1)
fails = [k for k, v in log.items() if str(v).startswith('FAIL')]
if fails: print('失败项（详见 fetch_log.json）：', '、'.join(fails))
