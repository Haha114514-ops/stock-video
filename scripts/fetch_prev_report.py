"""下载上一年同类定期报告（默认上一年半年报）并切段，用来做同比口径的经营数据（门店数、产能、客户数等）。

用法:
    python fetch_prev_report.py <代码> <工程目录>/data/reports [--year 2025] [--cat 半年报|年报]

fetch_data.py 只下最新一份年报和半年报；同比要用的上一年同期报告用这个补。stock-video 和 stock-report 共用。
"""
import os, re, sys, time
import requests
import akshare as ak

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report_cut  # noqa: E402


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    code, rdir = sys.argv[1], sys.argv[2]
    year = int(sys.argv[sys.argv.index('--year') + 1]) if '--year' in sys.argv else time.localtime().tm_year - 1
    cat = sys.argv[sys.argv.index('--cat') + 1] if '--cat' in sys.argv else '半年报'
    os.makedirs(rdir, exist_ok=True)
    # 半年报在当年披露，年报在次年披露
    start, end = (f'{year}0101', f'{year}1231') if cat == '半年报' else (f'{year + 1}0101', f'{year + 1}1231')
    d = ak.stock_zh_a_disclosure_report_cninfo(symbol=code, market='沪深京', category=cat, start_date=start, end_date=end)
    d = d[~d['公告标题'].str.contains('摘要|英文|English|已取消')]
    if d.empty:
        raise SystemExit(f'没找到 {year} {cat}')
    r = d.iloc[0]
    title = re.sub(r'[\\/:*?"<>|\s]', '', r['公告标题'])
    aid = re.search(r'announcementId=(\d+)', r['公告链接']).group(1)
    day = str(r['公告时间'])[:10]
    pdf = os.path.join(rdir, title + '.pdf')
    if not os.path.exists(pdf):
        for ext in ('PDF', 'pdf'):
            resp = requests.get(f'https://static.cninfo.com.cn/finalpage/{day}/{aid}.{ext}', timeout=60,
                                headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 404:
                break
        resp.raise_for_status()
        if not resp.content.startswith(b'%PDF'):
            raise SystemExit('下载到的不是 PDF')
        with open(pdf, 'wb') as fp:
            fp.write(resp.content)
    print('ok', title, report_cut.cut(pdf, rdir, title, []))


if __name__ == '__main__':
    main()
