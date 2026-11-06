"""只读查看 facts.json：一行一个键，打印值和说法；序列只打印长度。

用法：python facts_peek.py <工程目录或 facts.json> [键前缀 ...]
  不带前缀：全部标量键。按日期的字典（如分红 div）折叠成一行，要看就带前缀 div。
  带前缀：只看以这些前缀开头的键（rev  val.pe  bs.cash）。
列表永远只打印"长度 N"和首末两个日期（若是日期），不打印内容。
主控看 facts 一律用本脚本，不要 print / cat 整份 facts.json。
"""
import json
import re
import sys
from pathlib import Path

META = ('labels', 'quotes')
DATE = re.compile(r'^\d{4}(-\d{2}(-\d{2})?)?$')
FOLD = 10  # 日期键 ≥ 这么多的字典当序列折叠


def is_dated(d):
    return isinstance(d, dict) and len(d) >= FOLD and all(DATE.match(str(k)) for k in d)


def walk(v, path, out):
    """out: [(键, 种类, 内容)]，种类 = val / list / fold"""
    if isinstance(v, dict) and not (is_dated(v) and path):
        if path:
            out.append((path, 'group', v))
        for k, x in v.items():
            walk(x, f'{path}.{k}' if path else str(k), out)
    elif isinstance(v, dict):
        out.append((path, 'fold', v))
    elif isinstance(v, list):
        out.append((path, 'list', v))
    else:
        out.append((path, 'val', v))


def leaves(v):
    """一个节点下有几个键（标量 + 列表），折叠的字典也逐个算"""
    if isinstance(v, dict):
        return sum(leaves(x) for x in v.values())
    return 1


def show(v):
    if isinstance(v, float):
        return f'{v:.6g}'
    s = str(v)
    return s if len(s) <= 60 else s[:57] + '…'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    p = Path(sys.argv[1])
    if p.is_dir():
        p = p / 'facts.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    labels, quotes = d.get('labels', {}), d.get('quotes', {})
    pre = sys.argv[2:]

    def want(k):
        return not pre or any(k == q or k.startswith(q + '.') for q in pre)

    out = []
    for k, v in d.items():
        if k in META:
            continue
        # 前缀正好指到或指进一个按日期的字典时展开它
        if pre and is_dated(v) and any(q == k or q.startswith(k + '.') for q in pre):
            for kk, x in v.items():
                walk(x, f'{k}.{kk}', out)
        else:
            walk(v, k, out)

    n = nval = nlist = nlab = 0
    for k, kind, v in out:
        if kind == 'fold':
            # 前缀指进它里面时上面已展开；这里只剩折叠行
            if not want(k) and not any(q.startswith(k + '.') for q in pre):
                continue
            ks = list(v)
            print(f'{k}  〔按日期 {len(v)} 项 {ks[0]}…{ks[-1]}，带前缀 {k} 展开〕' + (f'  | {labels[k]}' if k in labels else ''))
            c = leaves(v)
            n += c
            nval += c
            continue
        if not want(k):
            continue
        if kind == 'group':
            if k in labels:
                print(f'{k}.*  | {labels[k]}')
            continue
        n += 1
        lab = labels.get(k, '')
        nlab += bool(lab)
        q = f'  〔摘录 {len(str(quotes[k]))} 字〕' if k in quotes else ''
        if kind == 'list':
            nlist += 1
            span = ''
            if v and all(isinstance(x, str) and DATE.match(x) for x in (v[0], v[-1])):
                span = f' {v[0]}…{v[-1]}'
            print(f'{k}  〔序列 长度 {len(v)}{span}〕' + (f'  | {lab}' if lab else '') + q)
        else:
            nval += 1
            print(f'{k} = {show(v)}' + (f'  | {lab}' if lab else '') + q)

    keys = {k for k, kd, _ in out}
    orphan = [k for k in labels if k not in keys and not any(k.startswith(f + '.') for f, kd, _ in out if kd == 'fold')]
    tail = f'共 {n} 个键（标量 {nval}，序列 {nlist}），有说法 {nlab}'
    if not pre:
        tail += f'；facts.json 共 {leaves({k: v for k, v in d.items() if k not in META})} 个键'
        if orphan:
            tail += f'；有说法没值 {len(orphan)} 个：{", ".join(orphan[:8])}' + ('…' if len(orphan) > 8 else '')
    print(tail)


if __name__ == '__main__':
    main()
