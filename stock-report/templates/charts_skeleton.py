# -*- coding: utf-8 -*-
"""<公司> <代码> · 报告图表（复制到 <工程>/charts.py）

每个函数 = 报告稿里的一张 [[图 函数名]]：参数是 facts（facts.json 读进来的字典），返回一张 fig。
docstring 第一行就是图注。数字只从 FX 取，不手写（改 facts.py 时图跟着变）。
画法看 python <stock-report>/scripts/rcharts.py 里各函数的说明；不够用就在这里直接用 matplotlib 另画，配色用 C('gold') 等。
focus= 点名这段正文在讲的那一块，其余压暗；note= 图角口径注（时间、口径、"推算""未经审计""示意"）。
"""
from rcharts import *   # waterfall / bs_two_bars / cash_bridge / bars / seg_share / val_grid / price_line / hbars / lines / C / get


def 业务构成(FX):
    """收入大头和利润大头是不是同一块（<年份> 年报）"""
    segs = [(s['name'], s['rev_pct'], s['gp_pct'], s['gm']) for s in FX['seg']]
    return seg_share(segs, note='<年份> 年报，按产品 / 行业')


def 利润表总览(FX):
    """每 100 元收入被哪几刀切走（<年份> 年报）"""
    w = FX['wf']          # facts.py 里算好的"每 100 元"各项，正负号按对利润的影响
    return waterfall([('营业收入', 100)] + [(k, v) for k, v in w['steps']], end='归母净利',
                     focus=None, note='<年份> 年报；每 100 元营业收入')


def 资产负债表总览(FX):
    """<YYYY-MM-DD> 钱压在什么上、是谁的钱"""
    b = FX['bs']
    return bs_two_bars(b['assets'], b['funding'], b['date'], unit='亿元',
                       side=['<读出来的一句：净现金 / 应收 vs 存货 / 应付 vs 应收>'],
                       note=f"同一时点：{b['date']}；有息负债含租赁负债")


def 现金流量表总览(FX):
    """<年份> 年现金从哪来、到哪去"""
    c = FX['cf']
    return cash_bridge(('年初现金', c['begin']), c['items'], note='亿元；"分红付息"含利息；现金及现金等价物口径')


def 估值四宫格(FX):
    """PB / PE：长期与近 5 年的分位"""
    v = FX['val']; s = FX['series']
    return val_grid([dict(title='PB 长期', vals=s['pb'], dates=s['dates'], st=v['pb_long']),
                     dict(title='PB 近5年', vals=s['pb5'], dates=s['dates5'], st=v['pb_5y']),
                     dict(title='PE 长期', vals=s['pe'], dates=s['dates'], st=v['pe_long']),
                     dict(title='PE 近5年', vals=s['pe5'], dates=s['dates5'], st=v['pe_5y'])],
                    note='<起点写清：近 10 年 / 上市以来 / 2018 年以来>；分位带 20% / 50% / 80%')
