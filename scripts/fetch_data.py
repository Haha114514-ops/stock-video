# -*- coding: utf-8 -*-
"""A股个股数据抓取（东财 / 新浪 / 巨潮），失败项记日志不中断。
用法：python fetch_data.py <代码如300896> <输出目录> [同行代码 ...] [--sub=子公司代码,…] [--notes=科目,…] [--no-reports] [--no-numbers]
  --notes      清单外要切的附注科目（这期命门相关，如 商誉,开发支出），传给 report_cut.py
  --sub        上市的并表子公司（如华润三九的天士力 600535、昆药 600422）：抓它自己的三大表 sub_<代码>_is/bs/cf.csv，
               用于最新一季的"去掉子公司"推演（年报附注只有年度数）
  --no-numbers 跳过本公司与同行的数字表，只重抽报告原文（--sub 仍生效）
产出：
  数字   px_raw / px_qfq 日线、value_em 估值序列、is/bs/cf 三大表长表、zygc 主营构成、fhps 分红、
         indicator_em 财务指标（141列：ROE/周转/毛利率/资产负债率，银行另有存款、贷款、不良率、拨备覆盖率等）、
         同行 comp_<代码>_is.csv / comp_<代码>_value.csv
  原文   reports/  最新一份年报 + 半年报 PDF（巨潮），由 report_cut.py 切成
         <标题>_目录索引.md           —— 先读这个：各节起始页、切好的段（页码 / 字数）、清单里没切到的项
         <标题>_管理层讨论与分析.txt  —— 找"这家公司的命门"先读这个
         <标题>_附注_<科目>.txt       —— 所得税调整、有息负债各项、减值、投资收益、现金流量表补充资料、分部、期后事项等
         <标题>_全文.txt              —— 每页前一行 =====PDF第N页=====；清单外的内容按关键词搜，只读命中的页
         <标题>_子公司权益.txt        —— 附注"在子公司中的权益"：重要非全资子公司的少数股东比例/损益/分红/权益，
                                         及其资产、负债、收入、净利润、经营现金流（抵销前）
         <标题>_合并范围变更.txt      —— 附注"合并范围的变更 / 变动"：并购的购买日、对价、商誉、购买日至期末的收入与净利润
  并表   sub_<代码>_is/bs/cf/value.csv（--sub 指定的上市子公司；value 用于按持股折算市值、算控股折价）
  fetch_log.json
东财日线断连时自动回退新浪日线。"""
import io, json, os, re, sys, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')
import akshare as ak

args = [a for a in sys.argv[1:] if not a.startswith('--')]
if len(args) < 2 or not re.fullmatch(r'\d{6}', args[0]): sys.exit(__doc__)
code, OUT, peers = args[0], args[1], args[2:]
subs = [c for a in sys.argv[1:] if a.startswith('--sub=') for c in a[6:].split(',') if c]
os.makedirs(OUT, exist_ok=True)
log = {}
def ex(c):
    """交易所前缀：北交所 4 / 8 / 92 开头（2024 年起新代码 920xxx），沪市 6 / 900（B 股），其余深市"""
    return ('BJ' if c.startswith(('4', '8', '92')) else 'SH' if c.startswith(('6', '9')) else 'SZ') + c

def grab(name, fn, *a, **k):
    for i in range(3):
        try:
            df = fn(*a, **k); df.to_csv(os.path.join(OUT, name), index=False, encoding='utf-8-sig')
            log[name] = len(df); print('ok', name, len(df)); return df
        except Exception as e:
            print('retry', name, i, repr(e)[:160]); time.sleep(2 + 2 * i)
    log[name] = 'FAIL: ' + traceback.format_exc(limit=1)[-200:]
    return None

# ---------- 数字 ----------
if '--no-numbers' not in sys.argv:
    for adj, nm in (('', 'px_raw.csv'), ('qfq', 'px_qfq.csv')):
        if grab(nm, ak.stock_zh_a_hist, symbol=code, period='daily', adjust=adj) is None:
            grab(nm, ak.stock_zh_a_daily, symbol=ex(code).lower(), adjust=adj)   # 新浪回退
    grab('value_em.csv', ak.stock_value_em, symbol=code)
    grab('is.csv', ak.stock_profit_sheet_by_report_em, symbol=ex(code))
    grab('bs.csv', ak.stock_balance_sheet_by_report_em, symbol=ex(code))
    grab('cf.csv', ak.stock_cash_flow_sheet_by_report_em, symbol=ex(code))
    grab('zygc.csv', ak.stock_zygc_em, symbol=ex(code))
    grab('fhps.csv', ak.stock_fhps_detail_em, symbol=code)
    grab('indicator_em.csv', ak.stock_financial_analysis_indicator_em, symbol=f'{code}.{ex(code)[:2]}', indicator='按报告期')
    for p in peers:
        grab(f'comp_{p}_is.csv', ak.stock_profit_sheet_by_report_em, symbol=ex(p))
        grab(f'comp_{p}_value.csv', ak.stock_value_em, symbol=p)
for s in subs:   # 上市的并表子公司：自己的三大表
    grab(f'sub_{s}_is.csv', ak.stock_profit_sheet_by_report_em, symbol=ex(s))
    grab(f'sub_{s}_bs.csv', ak.stock_balance_sheet_by_report_em, symbol=ex(s))
    grab(f'sub_{s}_cf.csv', ak.stock_cash_flow_sheet_by_report_em, symbol=ex(s))
    grab(f'sub_{s}_value.csv', ak.stock_value_em, symbol=s)   # 市值：按持股折算，和母公司市值比（控股折价）

# ---------- 定期报告原文（巨潮） ----------
# 抽文本、切管理层讨论和附注、写目录索引都在 report_cut.py（57号补丁十一）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_cut
extra_notes = [k for a in sys.argv[1:] if a.startswith('--notes=') for k in a[8:].split(',') if k]

def fetch_reports():
    import requests
    rdir = os.path.join(OUT, 'reports'); os.makedirs(rdir, exist_ok=True)
    y = time.localtime().tm_year
    for cat in ('年报', '半年报'):
        try:
            d = ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market='沪深京', category=cat,
                                                       start_date=f'{y - 2}0101', end_date=time.strftime('%Y%m%d'))
            d = d[~d['公告标题'].str.contains('摘要|英文|English|已取消')].sort_values('公告时间', ascending=False)
            if d.empty: log[f'report_{cat}'] = '无'; continue
            r = d.iloc[0]; title = re.sub(r'[\\/:*?"<>|\s]', '', r['公告标题'])
            aid = re.search(r'announcementId=(\d+)', r['公告链接']).group(1)
            day = str(r['公告时间'])[:10]
            pdf = os.path.join(rdir, title + '.pdf')
            if not os.path.exists(pdf):
                for ext in ('PDF', 'pdf'):   # 巨潮有的文件是小写 .pdf（招商蛇口 2026 半年报），大写 404
                    url = f'https://static.cninfo.com.cn/finalpage/{day}/{aid}.{ext}'
                    resp = requests.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
                    if resp.status_code != 404: break
                resp.raise_for_status()
                if not resp.content.startswith(b'%PDF'): raise ValueError('不是 PDF: ' + url)
                with open(pdf, 'wb') as fp: fp.write(resp.content)
            log[f'report_{cat}'] = f'（{day}）' + report_cut.cut(pdf, rdir, title, extra_notes)
            print('ok', log[f'report_{cat}'])
        except Exception as e:
            log[f'report_{cat}'] = 'FAIL: ' + repr(e)[:200]; print('fail', cat, repr(e)[:200])

if '--no-reports' not in sys.argv: fetch_reports()
with open(os.path.join(OUT, 'fetch_log.json'), 'w', encoding='utf-8') as fp: json.dump(log, fp, ensure_ascii=False, indent=1)
fails = [k for k, v in log.items() if str(v).startswith('FAIL')]
if fails: print('失败项（详见 fetch_log.json）：', '、'.join(fails))
