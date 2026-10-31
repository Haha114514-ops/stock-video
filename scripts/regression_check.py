# -*- coding: utf-8 -*-
"""
regression_check.py —— 两次 QC 结果对照（三态回归，2026-10-25·34号）
用法:
  python regression_check.py <上次qc_timing.json> <本次qc_timing.json> [--out 回归.md]
三态口径:
  已修复 = 上红/黄 → 本次绿
  未修复 = 上红 → 本次仍红
  新退化 = 上绿 → 本次红
  （黄牌对黄牌=维持人工；新增cue单独列出）
"""
import json, argparse

def key(r):
    return f"{r.get('seg')}|{r.get('at')}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prev')
    ap.add_argument('cur')
    ap.add_argument('--out', default='回归.md')
    a = ap.parse_args()
    P = {key(r): r for r in json.load(open(a.prev, encoding='utf-8'))['rows']}
    C = {key(r): r for r in json.load(open(a.cur, encoding='utf-8'))['rows']}

    fixed, persist, degrade, newgone, same = [], [], [], [], []
    for k, c in C.items():
        p = P.get(k)
        cv, pv = c['verdict'], (p['verdict'] if p else None)
        if p is None:
            newgone.append(('新增cue', k, c))
        elif cv == 'PASS' and pv in ('RED', 'YELLOW'):
            fixed.append((k, p, c))
        elif cv == 'RED' and pv == 'RED':
            persist.append((k, p, c))
        elif cv == 'RED' and pv == 'PASS':
            degrade.append((k, p, c))
        else:
            same.append((k, p, c))
    for k, p in P.items():
        if k not in C:
            newgone.append(('cue消失', k, p))

    md = ['# QC 回归对照', '',
          f'上次: {a.prev}  |  本次: {a.cur}', '',
          f'- 已修复: {len(fixed)}', f'- 未修复: {len(persist)}', f'- 新退化: {len(degrade)}',
          f'- 新增/消失: {len(newgone)}', f'- 维持: {len(same)}', '',
          '| 三态 | cue | 上次 | 本次 |', '|---|---|---|---|']
    for k, p, c in fixed:
        md.append(f"| 已修复 | {k} | {p['verdict']} | {c['verdict']} |")
    for k, p, c in persist:
        md.append(f"| 未修复 | {k} | {p['verdict']} | {c['verdict']} |")
    for k, p, c in degrade:
        md.append(f"| **新退化** | {k} | {p['verdict']} | {c['verdict']} |")
    for tag, k, r in newgone:
        md.append(f"| {tag} | {k} | {r.get('verdict','-')} | - |")
    open(a.out, 'w', encoding='utf-8').write('\n'.join(md))
    print('\n'.join(md[:10]))
    print('已写出', a.out)
    if degrade:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
