# -*- coding: utf-8 -*-
"""build_report.py —— 报告稿.md + facts.json + charts.py → output/报告.html + 报告.pdf

    python build_report.py <工程> [--theme dark|paper] [--html-only] [--out 文件名（不带扩展名）]

报告稿.md 的写法（模板：templates/报告稿模板.md）：
  文件头 --- 之间：公司 / 代码 / 截止日 / 标题 / 主线 / 公司一句话 / 三表总览 / 封面卡 / 数据来源
  ## 01 章名            一章；"## 摘要"、"## 口径与推断说明" 不编号也行
  {{键|规格}}           从 facts.json 取数（规格见 rlib.fmt：亿 / 亿1 / % / %0 / 倍 / .2f）。键写错直接报错
  [[图 函数名]]          charts.py 里的函数，返回 fig；图下自动配图注（函数的 docstring 第一行）
  [[卡 键|规格|标题, 键|规格|标题, …]]   一排数字卡，卡下小字是 facts 里冻结的说法
  ==重点==              金色强调（视频里"讲到谁亮谁"的纸面版）；一段里一两处，不满篇
  ::: 推测 … :::         推测框（几种可能并列；标题自动写"推测"）
  ::: 推算 … :::         推算框（前提写全）
  ::: 金句 … :::         金句卡，全篇两三次
  ::: 注 … :::           灰色小字注
主题：dark = 和视频一个样子（深底金字），paper = 白底，适合打印。PDF 用本机 Chrome / Edge / playwright 的 chromium。
"""
import html
import importlib.util
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rlib  # noqa: E402

try:
    rlib.video_scripts()          # 字体用 stock-video 的 sysenv（找不到 stock-video 也能出图，只是字体靠 fontconfig）
except SystemExit:
    pass
import rcharts  # noqa: E402

USAGE = __doc__


# ---------- 读稿 ----------
def read_draft(proj):
    p = Path(proj) / '报告稿.md'
    if not p.exists(): sys.exit(f'没有 {p}：把 templates/报告稿模板.md 复制过去再写')
    src = p.read_text(encoding='utf-8-sig')
    meta, body = {}, src
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', src, re.S)
    if m:
        body = src[m.end():]
        for line in m.group(1).splitlines():
            if ':' in line or '：' in line:
                k, _, v = re.split(r'([:：])', line, 1)
                meta[k.strip()] = v.strip()
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)        # 写给作者的注释不印、不查
    return meta, body


def split_chapters(body):
    """[(标题, 正文)]；## 开头的才算章"""
    parts = re.split(r'^##\s+(.+?)\s*$', body, flags=re.M)
    pre = parts[0].strip()
    chs = [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    return pre, chs


# ---------- 数字 ----------
def interp(text, fx, used):
    def rep(m):
        key, _, spec = m.group(1).strip().partition('|')
        try:
            v = rlib.get(fx, key.strip())
        except KeyError:
            sys.exit(f'报告稿里 {{{{{key}}}}} 在 facts.json 里找不到（先在 facts.py 里 put）')
        used.append(key.strip())
        return rlib.fmt(v, spec.strip())
    return re.sub(r'\{\{([^}]+)\}\}', rep, text)


# ---------- 图 ----------
def load_charts(proj):
    p = Path(proj) / 'charts.py'
    if not p.exists(): return None
    spec = importlib.util.spec_from_file_location('charts', p)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HERE))
    spec.loader.exec_module(mod)
    return mod


def render_fig(mod, name, fx, outdir, cache):
    if name in cache: return cache[name]
    if mod is None or not hasattr(mod, name):
        sys.exit(f'[[图 {name}]]：charts.py 里没有函数 {name}')
    fn = getattr(mod, name)
    fig = fn(fx)
    path = Path(outdir) / 'fig' / f'{name}.svg'
    rcharts.save(fig, path)
    cap = (fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else ''
    cache[name] = (path, cap)
    return cache[name]


# ---------- markdown ----------
def md_to_html(s):
    import markdown
    return markdown.markdown(s, extensions=['tables', 'sane_lists', 'attr_list'])


BOX = {'推测': ('guess', '推测'), '推算': ('calc', '推算'), '金句': ('quote', ''), '注': ('note', '')}


def chapter_html(text, fx, mod, outdir, cache, used, figs_used):
    text = interp(text, fx, used)
    blocks = []                                     # 先把自定义块换成占位，markdown 处理完再换回来

    def keep(h):
        blocks.append(h); return f'\n\nXBLOCK{len(blocks) - 1}X\n\n'

    def box(m):
        kind = m.group(1).strip(); inner = m.group(2).strip()
        cls, head = BOX.get(kind, ('note', kind))
        hh = f'<div class="box-h">{head}</div>' if head else ''
        return keep(f'<div class="box {cls}">{hh}{inline(md_to_html(inner))}</div>')
    text = re.sub(r'^:::\s*(\S+)\s*\n(.*?)\n:::\s*$', box, text, flags=re.M | re.S)

    def fig(m):
        name = m.group(1).strip(); figs_used.append(name)
        path, cap = render_fig(mod, name, fx, outdir, cache)
        svg = path.read_text(encoding='utf-8')
        svg = re.sub(r'^<\?xml[^>]*>\s*(<!DOCTYPE[^>]*>\s*)?', '', svg)
        capt = f'<figcaption>图：{html.escape(cap)}</figcaption>' if cap else ''
        return keep(f'<figure class="fig" id="fig-{html.escape(name)}">{svg}{capt}</figure>')
    text = re.sub(r'^\[\[图\s+([^\]]+)\]\]\s*$', fig, text, flags=re.M)

    def cards(m):
        out = []
        for item in re.split(r'[,，]\s*', m.group(1).strip()):
            key, spec, title = (item.split('|') + ['', ''])[:3]
            key = key.strip()
            try:
                v = rlib.get(fx, key)
            except KeyError:
                sys.exit(f'[[卡 {item}]]：{key} 在 facts.json 里找不到')
            used.append(key)
            lab = rlib.label(fx, key)
            out.append(f'<div class="card"><div class="c-t">{html.escape(title.strip() or key)}</div>'
                       f'<div class="c-v">{html.escape(rlib.fmt(v, spec.strip()))}</div>'
                       f'<div class="c-l">{html.escape(lab)}</div></div>')
        return keep(f'<div class="cards">{"".join(out)}</div>')
    text = re.sub(r'^\[\[卡\s+([^\]]+)\]\]\s*$', cards, text, flags=re.M)

    h = inline(md_to_html(text))
    for i, b in enumerate(blocks):
        h = re.sub(rf'<p>\s*XBLOCK{i}X\s*</p>|XBLOCK{i}X', lambda _m, b=b: b, h)
    return h


def inline(h):
    return re.sub(r'==(.+?)==', r'<mark>\1</mark>', h)


# ---------- 页面 ----------
CSS = """
:root { --bg:#0b1124; --card:#121e3a; --ink:#ecf1fa; --sub:#96a6c2; --dim:#5c6c8c; --grid:#3c4e73;
        --gold:#f5b942; --red:#ff5252; --green:#22c578; --blue:#38bdf8; --edge:#fff4d6; }
html.paper { --bg:#ffffff; --card:#f6f3ec; --ink:#1f2430; --sub:#5a6275; --dim:#9aa1b0; --grid:#d9dce3;
        --gold:#b97f05; --red:#d93636; --green:#1f9d5c; --blue:#2b7bbf; --edge:#1f2430; }
html, body { background: var(--bg); color: var(--ink); margin: 0; }
body { font-family: "PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC","WenQuanYi Zen Hei",sans-serif;
       font-size: 10.6pt; line-height: 1.85; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.num, .c-v { font-family: "DIN Alternate","Bahnschrift","DejaVu Sans",sans-serif; }
h1, h2, h3 { line-height: 1.35; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always;
         position: relative; }
.cover .tag { color: var(--gold); letter-spacing: .25em; font-size: 10pt; }
.cover h1 { font-size: 30pt; margin: 6mm 0 2mm; }
.cover .code { color: var(--sub); font-size: 12pt; }
.cover .thesis { margin-top: 12mm; font-size: 15pt; line-height: 1.6; border-left: 3px solid var(--gold); padding-left: 5mm; }
.cover .what { margin-top: 6mm; color: var(--sub); font-size: 11pt; }
.cover .cards { margin-top: 14mm; }
.cover .meta { position: absolute; bottom: 0; color: var(--sub); font-size: 9pt; line-height: 1.7; }
.prog { display: flex; gap: 2mm; margin: 0 0 4mm; flex-wrap: wrap; }
.prog span { font-size: 8pt; color: var(--dim); border-bottom: 2px solid var(--grid); padding: 0 1.5mm 1mm; }
.prog span.on { color: var(--gold); border-color: var(--gold); font-weight: bold; }
.prog span.done { color: var(--sub); border-color: var(--sub); }
section.ch { page-break-before: always; }
section.ch.cont { page-break-before: auto; margin-top: 10mm; }
h2 { font-size: 18pt; margin: 0 0 4mm; }
h2 .no { color: var(--gold); margin-right: 3mm; font-family: "DIN Alternate","Bahnschrift","DejaVu Sans",sans-serif; }
h3 { font-size: 12.5pt; margin: 6mm 0 2mm; color: var(--ink); }
h3::before { content: ""; display: inline-block; width: 3px; height: 1em; background: var(--gold); margin-right: 2.5mm; vertical-align: -2px; }
p { margin: 0 0 3mm; text-align: justify; }
strong { color: var(--ink); }
mark { background: transparent; color: var(--gold); font-weight: bold; border-bottom: 1.5px solid var(--gold); }
ul, ol { padding-left: 6mm; margin: 0 0 3mm; } li { margin-bottom: 1mm; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9.4pt; line-height: 1.55; }
th { color: var(--sub); font-weight: normal; text-align: left; border-bottom: 1px solid var(--grid); padding: 1.6mm 2mm; }
td { border-bottom: 1px solid var(--grid); padding: 1.6mm 2mm; vertical-align: top; }
figure.fig { margin: 3mm 0 5mm; page-break-inside: avoid; break-inside: avoid; }
figure.fig svg { width: 100%; height: auto; display: block; }
figcaption { color: var(--sub); font-size: 8.6pt; margin-top: 1mm; }
.cards { display: flex; gap: 3mm; margin: 2mm 0 5mm; page-break-inside: avoid; }
.card { flex: 1; background: var(--card); border-radius: 2mm; padding: 3mm 3.5mm; border-top: 2px solid var(--gold); }
.c-t { font-size: 8.6pt; color: var(--sub); }
.c-v { font-size: 20pt; color: var(--gold); font-weight: bold; line-height: 1.3; margin: 1mm 0; }
.c-l { font-size: 7.6pt; color: var(--dim); line-height: 1.45; }
.box { border-radius: 2mm; padding: 3mm 4mm; margin: 2mm 0 4mm; page-break-inside: avoid; font-size: 10pt; }
.box p:last-child, .box ul:last-child { margin-bottom: 0; }
.box-h { font-size: 8.6pt; font-weight: bold; letter-spacing: .1em; margin-bottom: 1mm; }
.box.guess { border: 1px dashed var(--sub); } .box.guess .box-h { color: var(--sub); }
.box.calc { background: var(--card); border-left: 3px solid var(--blue); } .box.calc .box-h { color: var(--blue); }
.box.quote { background: var(--card); border-left: 4px solid var(--gold); font-size: 13pt; line-height: 1.7; padding: 5mm 6mm; }
.box.note { color: var(--sub); font-size: 8.8pt; padding: 0; }
.disclaimer { margin-top: 10mm; padding-top: 3mm; border-top: 1px solid var(--grid); color: var(--sub); font-size: 8.6pt; }
"""


def build(proj, theme='dark', html_only=False, out_name='报告'):
    proj = Path(proj).resolve()
    meta, body = read_draft(proj)
    fx = rlib.load_facts(proj)
    rcharts.theme(theme)
    mod = load_charts(proj)
    outdir = proj / 'output'; outdir.mkdir(exist_ok=True)
    pre, chs = split_chapters(body)
    used, figs_used, cache = [], [], {}

    names = [re.sub(r'^\d+\s*', '', t) for t, _ in chs]
    nums = [re.match(r'^(\d+)\s', t) for t, _ in chs]
    numbered = [i for i, n in enumerate(nums) if n]
    parts = []
    for i, (t, txt) in enumerate(chs):
        n = nums[i]
        prog = ''
        if n and len(numbered) > 1:
            spans = []
            for j in numbered:
                cls = 'on' if j == i else ('done' if j < i else '')
                spans.append(f'<span class="{cls}">{html.escape(names[j])}</span>')
            prog = f'<div class="prog">{"".join(spans)}</div>'
        head = (f'<span class="no">{n.group(1)}</span>' if n else '') + html.escape(names[i])
        cont = ' cont' if not n and i > 0 and not nums[i - 1] else ''
        parts.append(f'<section class="ch{cont}">{prog}<h2>{head}</h2>'
                     f'{chapter_html(txt, fx, mod, outdir, cache, used, figs_used)}</section>')

    cover_cards = ''
    if meta.get('封面卡'):
        cover_cards = chapter_html(f"[[卡 {meta['封面卡']}]]", fx, mod, outdir, cache, used, figs_used)
    company, code = meta.get('公司', ''), meta.get('代码', '')
    title = meta.get('标题') or f'{company} {code} 拆解'
    cover = (f'<div class="cover"><div class="tag">个股拆解 · 图文报告</div><h1>{html.escape(title)}</h1>'
             f'<div class="code">{html.escape(company)} {html.escape(code)} · 数据截至 {html.escape(meta.get("截止日", ""))}</div>'
             f'<div class="thesis">{inline(html.escape(meta.get("主线", "")))}</div>'
             f'<div class="what">{html.escape(meta.get("公司一句话", ""))}</div>{cover_cards}'
             f'<div class="meta">数据来源：{html.escape(meta.get("数据来源", "公司定期报告、公告；行情与估值来自东方财富 / 新浪"))}<br>'
             f'本报告不构成投资建议。</div></div>')
    intro = chapter_html(pre, fx, mod, outdir, cache, used, figs_used) if pre.strip() else ''
    disc = ('<div class="disclaimer">免责声明：本报告只解读公开财报和公告，数字来自公司定期报告、公告和公开行情数据，'
            '标"推算"的是按文中前提自行计算，标"推测"的是几种可能并列、不是结论。文中"参考价"不是目标价。'
            '本报告不构成投资建议，不对任何人的买卖决定负责。</div>')
    bg = '#0b1124' if theme == 'dark' else '#ffffff'
    foot = (company + ' ' + code + ' · 不构成投资建议').replace('"', '')
    page = ('@page { size: A4; margin: 16mm 15mm 18mm 15mm; background: %s;'      # 页边也铺底色（Chrome 131 起支持）
            ' @bottom-left { content: "%s"; color: #8894ad; font-size: 7.5pt; }'
            ' @bottom-right { content: counter(page) " / " counter(pages); color: #8894ad; font-size: 7.5pt; } }'
            ' @page :first { @bottom-left { content: none; } @bottom-right { content: none; } }' % (bg, foot))
    doc = (f'<!doctype html><html class="{theme}" lang="zh-CN"><head><meta charset="utf-8">'
           f'<title>{html.escape(title)}</title><style>{page}{CSS}</style></head><body>'
           f'{cover}{intro}{"".join(parts)}{disc}</body></html>')
    hp = outdir / f'{out_name}.html'
    hp.write_text(doc, encoding='utf-8')
    (outdir / 'build_log.txt').write_text(
        '用到的 facts 键：\n' + '\n'.join(sorted(set(used))) + '\n\n用到的图：\n' + '\n'.join(figs_used) + '\n',
        encoding='utf-8')
    print('HTML', hp)
    if html_only: return hp
    pdf = outdir / f'{out_name}.pdf'
    to_pdf(hp, pdf)
    print('PDF ', pdf)
    return pdf


def _launch(p):
    exe = os.environ.get('STOCK_VIDEO_BROWSER')
    tries = [dict(executable_path=exe)] if exe else []
    tries += [dict(channel='chrome'), dict(channel='msedge'), {}]
    for g in ('/opt/pw-browsers/chromium', '/opt/pw-browsers/chromium-*/chrome-linux/chrome'):
        import glob
        tries += [dict(executable_path=x) for x in glob.glob(g) if os.path.isfile(x)]
    err = None
    for kw in tries:
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception as e:
            err = e
    sys.exit(f'启动不了浏览器出 PDF：装 Chrome，或 playwright install chromium，或设 STOCK_VIDEO_BROWSER\n{err}\n'
             f'（HTML 已经生成，可以用浏览器打开后"打印 → 存为 PDF"）')


def to_pdf(hp, pdf):
    """页脚、页码、页边底色都写在 CSS 的 @page 里（Chrome 131 起支持；更老的浏览器页边会是白的、没有页码）"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page()
        pg.goto(Path(hp).as_uri()); pg.wait_for_load_state('networkidle')
        pg.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
        b.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'): sys.exit(USAGE)
    th = a[a.index('--theme') + 1] if '--theme' in a else 'dark'
    on = a[a.index('--out') + 1] if '--out' in a else '报告'
    build(a[0], th, '--html-only' in a, on)
