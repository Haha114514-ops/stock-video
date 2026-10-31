# -*- coding: utf-8 -*-
"""合成前自动质检门（2026-10-24 立，27号审计；2026-10-25·29号 重构：三大表同权＋焦点词）。

用法：
    python gate_check.py <ep目录>                # 常规：读 segments.json 顶层 "focus" 字段
    python gate_check.py <ep目录> --focus 负债,毛利  # CLI 覆盖焦点词（逗号分隔，可空）
    独立运行打印明细；被 build_all.py 导入时经 run_gate() 调用，红灯 sys.exit。

检查组（2026-10-25·29号 起为三大表同权，不再有单科专属配额）：
  G1 三大表齐全   完整版（段数>=10）必须含 利润表段/资产负债表段/现金流段，缺哪张=红；
                  段数<10（容易版/科普片）只记 NOTE 不拦
  G2 段内同权     检出的每个表段：亿级金额口播>=1；全片有用 states 时该段 cue>=1
  G3 两半对称     资产负债表段（科目结构使然，非词偏好）：资产侧与负债侧叙述都不得为零；
                  画片脚本里资产构成图与负债构成图都在（负债侧：长期/短期/借款/应付等分类）
  G4 焦点词       segments.json 顶层 "focus": ["词",...] 或 --focus 给词时，每个词查
                  「全片解说提及>=1 ＋ 相关 cue>=1」；为空=只跑通用标准（开工问询兜底）
  C4 禁链式继承   状态帧生成脚本不得 load 上一状态帧（只能 load 基础 slide）
  C5 段尾高亮数   末状态帧与基础图的粗粒度差分连通区<=1（顺序巡讲末项允许保留）
  C7 规约版本标注 segments.json 必须带 spec 字段（所依据 SKILL 版本日期或「按旧版制作」）；
      43号起加时效执法：spec 须含 SKILL.md 版本行的当前 NN号（重制/新期），否则=红
  C8 数字变动四要素 全段扫描：变化句必须「旧数 → 新数（±%）」齐全（2026-10-24 死结诊断立）
  C8b 变动声画联动 每句数字变动（含旧值/新值成对或带幅度的实变动句）必须有状态 cue 命中该句，
                  状态帧在数字原位显示四要素视觉块「旧数 →（方向箭头）±% → 新数」——
                  读数字变化时 canvas 必须明显变动（2026-10-25 用户明确要求；只有口播/字幕变=红）
  G9 结论/钩子页版式（42号条文，43号执法）：完整版末段 drawer 必须由 pillar_cards 承载，
                  禁 rowlist/KPI 卡当结论页主体；首段（钩子页）必须 K线半区+变动面板半区
  G10 资产完备（43号）：每段 states 数=画片脚本 HLS 数（防 zip 截断），且 slides/ 下
                  契约声明的状态 PNG 全部存在，缺一张=红
  G11 成片新鲜度（43号）：final*.mp4 已存在时，mtime 必须≥工程（契约/画片脚本/facts/slides）；
                  成片早于工程=红（43号诊断：43/38号登记的「v5成片」实为 21:02 旧文件）
  SYNC 双址一致性（43号）：theme_base36.py 用户库↔项目副本哈希必须一致（防运行件漂移）；
                  单侧独有的工具记 NOTE
  G5-相交 版式相交硬闸门（44号）：axes 面板两两相交、blk4 与 axes 相交=红（叠图视觉打架）
  G13 卡片字号下限（44号）：手搓卡片（≥2 FancyBboxPatch）内 f.text 字号<15=红，
                  卡片必须用 trio_cards/pillar_cards 组件承载（字大饱满）
  G6-收紧 纯文字数据页（44号「4+1图」）：含金额的段画面只有 rowlist 无图/内容组件=红；
                  无金额的观点/清单页豁免
  G14 公司史页组件承载（44号）：公司史章节段必须 timeline_ladder 阶梯组件或图表承载，
                  禁细线+小点裸时间轴（ep01s 阶梯视觉在 37号固化时丢失的教训）
  G15 总量闸门（45号，52号诊断）：完整版总字数>=3200、预估成片>=540s（5.4字/秒）、
                  对比段检出——防「合规但贫血」（太古EP01 2151字/6:44 全绿的教训；锚=长和3726字/11:16）
  G16 声画密度（45号）：段均 states>=3.5、全线<=48字/cue（锚=长和 4.5/37）——
                  讲一串数字只切1-2次画面=节奏贫瘠
  G17 构图密度（45号）：页均视觉元素>=5（锚=长和9.5组件权重标尺）——「一图+一句话」空洞页=红，
                  构图目标双栏互证（主图+右侧明细/变动面板）
  G18 估值四宫格（46号，52号修复轮·用户钦定）：估值章节必须一页 band_panel>=4
                  （PB/PE 十年·五年 三区制分位带+现值红点）——估值主视觉固定模式
  G19 基准量化对照（47号立，55号诊断第五环）：完整版契约必须带 baseline 五指标表
                  {segs/chars/cues/slides/dur_sec}，任一 <基准85%=红（waiver 豁免降黄）——
                  第0步从「读头注自觉」变「抄表执法」，防样板传承衰减

任何一项红 => exit 1；全部绿 => exit 0。
例子词治理（2026-10-25·29号）：本脚本不含任何单科专属关键词配额；单科重点词只能经
「开工问询 => segments.json focus 字段」进入，为空即不激活——例子词不得硬编码回本脚本。
"""
import json
import os
import re
import sys

AMOUNT_RE = re.compile(r"[0-9一二三四五六七八九十百千零〇]+(?:\.[0-9]+)?亿")

# 三大表段识别关键词（按段内最早出现位置选主题段；词表只做「表」的识别，不做单科配额）
TABLE_DEFS = [
    ("利润表段", ("利润表", "营收", "营业额", "收入", "溢利", "净利润", "毛利率", "经营溢利")),
    ("资产负债表段", ("资产负债", "净资产", "总负债")),
    ("现金流段", ("现金流", "经营现金", "自由现金")),
]
ASSET_KW = ("资产", "现金", "应收", "存货", "投资", "物业")
LIAB_KW = ("负债", "借款", "应付", "杠杆", "利息", "有息", "租赁")


def sentences(text):
    parts = re.split(r"(?<=[。；！？])", text)
    out, pos = [], 0
    for p in parts:
        if p:
            out.append((pos, pos + len(p), p))
        pos += len(p)
    return out


def find_table_segment(segs, keywords):
    """选主题段：含任一关键词且该词越靠段首越可能是主题段（顺带提及的结论段不算）。"""
    cands = []
    for s in segs:
        t = s.get("text", "")
        if len(t) < 40:
            continue
        pos = min((p for p in (t.find(k) for k in keywords) if p >= 0), default=-1)
        if pos >= 0:
            cands.append((pos / max(len(t), 1), -len(t), s))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    return cands[0][2]


def segment_family(segs, core):
    """id 前缀相同的连续段族（如 5/5b/5c）视为同一章节。"""
    fam = [s for s in segs if str(s.get("id", "")).startswith(str(core.get("id", "")))]
    return {"text": "".join(s.get("text", "") for s in fam),
            "states": [st for s in fam for st in (s.get("states") or [])],
            "slide": fam[-1].get("slide"), "ids": [str(s.get("id")) for s in fam]}


def g2_segment_checks(label, fam, has_states):
    """G2 段内同权：亿级金额口播>=1；全片用 states 时 cue>=1。"""
    reds, notes = [], []
    text = fam["text"]
    amounts = set(AMOUNT_RE.findall(text))
    if not amounts:
        reds.append("G2 %s（段%s）无亿级金额口播——每张表段至少说出一个该表核心金额"
                    % (label, "/".join(fam["ids"])))
    else:
        notes.append("G2 %s 金额口播 %d 个（%s）" % (label, len(amounts), "、".join(sorted(amounts)[:3])))
    if has_states and not fam["states"]:
        reds.append("G2 %s（段%s）零 cue——全片有声画联动而该表段没有（声画联动覆盖每张表）"
                    % (label, "/".join(fam["ids"])))
    elif has_states:
        notes.append("G2 %s cue %d 个" % (label, len(fam["states"])))
    return reds, notes


def side_spans(text, kws, strip=("资产负债表",)):
    out = []
    for a, b, p in sentences(text):
        s2 = p
        for w in strip:
            s2 = s2.replace(w, "")
        if any(k in s2 for k in kws):
            out.append((a, b, p))
    return out


# ---------- G3：两半图（画片脚本里资产构成图与负债构成图都在） ----------
CHART_KW = ("donut", "pie", "barh", "bar(")


def two_side_chart_check(ep_dir):
    reds, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    code = ""
    for fn in sorted(os.listdir(parent)):
        if fn.endswith(".py") and "slides" in fn:
            code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
    lines = code.splitlines()

    def chart_found(kws, name):
        for i, ln in enumerate(lines):
            if not any(c in ln for c in CHART_KW):
                continue
            window = "".join(lines[max(0, i - 6): i + 7])
            if any(k in window for k in kws):
                notes.append("G3 %s构成图候选：第%d行" % (name, i + 1))
                return True
        return False

    asset_ok = chart_found(ASSET_KW, "资产侧")
    liab_ok = chart_found(LIAB_KW, "负债侧")
    if not asset_ok:
        reds.append("G3 画片脚本未见资产侧构成图")
    if not liab_ok:
        reds.append("G3 画片脚本未见负债侧构成图（两半对称：像资产环形图那样给负债分类归纳，"
                    "theme.donut 渲染、扇区标名称+占比；只有比例条=不合格）")
    return reds, notes


# ---------- C4：状态帧生成脚本禁链式继承 ----------
CHAIN_PAT = re.compile(r'(?:load|Image\.open)\((["\'])(slide\d+[a-z]?_[^"\']+\.png)\1')


def chain_check(ep_dir):
    reds, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    for fn in sorted(os.listdir(parent)):
        if not (fn.endswith(".py") and "states" in fn):
            continue
        path = os.path.join(parent, fn)
        for i, ln in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            m = CHAIN_PAT.search(ln)
            if m:
                reds.append("C4 链式继承 %s 第%d行：load 状态帧 %s（必须 load 基础 slide 重绘＋保留区声明）"
                            % (fn, i, m.group(2)))
    if not reds:
        notes.append("C4 状态帧生成无链式继承")
    return reds, notes


# ---------- C5：段尾高亮数（末状态帧 vs 基础图 粗粒度差分连通区） ----------
def rest_highlight_count(ep_dir, seg):
    try:
        from PIL import Image
    except ImportError:
        return None, "PIL 不可用，C5 跳过"
    states = seg.get("states") or []
    base = os.path.join(ep_dir, "slides", seg.get("slide", ""))
    last = states[-1]["img"] if states else seg.get("slide")
    lastp = os.path.join(ep_dir, "slides", last)
    if not (os.path.exists(base) and os.path.exists(lastp)):
        return None, "末状态帧或基础图缺失，C5 跳过"
    a = Image.open(base).convert("RGB").resize((96, 54))
    b = Image.open(lastp).convert("RGB").resize((96, 54))
    W, H = 96, 54
    pa, pb = a.load(), b.load()
    mask = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            ra, ga, ba_ = pa[x, y]
            rb, gb, bb = pb[x, y]
            if abs(ra - rb) + abs(ga - gb) + abs(ba_ - bb) > 60:
                mask[y][x] = True
    seen = [[False] * W for _ in range(H)]
    comps = 0
    for y in range(H):
        for x in range(W):
            if mask[y][x] and not seen[y][x]:
                stack, size = [(x, y)], 0
                seen[y][x] = True
                while stack:
                    cx, cy = stack.pop()
                    size += 1
                    for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                        if 0 <= nx < W and 0 <= ny < H and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                if size >= 4:
                    comps += 1
    return comps, "%s vs %s" % (last, seg.get("slide"))


# ---------- C8：数字变动四要素（2026-10-24 死结诊断立；全段扫描） ----------
C8_NUM = re.compile(
    r"[0-9]+(?:\.[0-9]+)?(?:亿|万|%|个百分点)"
    r"|[0-9]+(?:\.[0-9]+)"
    r"|[0-9]{2,}"
    r"|百分之[0-9一二三四五六七八九十]+(?:点[0-9一二三四五六七八九十]+)?"
    r"|[0-9一二三四五六七八九十百千]+(?:点[0-9一二三四五六七八九十]+)?[亿万]"
)
C8_CUE = ("同比", "去年", "上年", "前年", "升", "降", "涨", "跌", "增", "下滑", "回落",
          "翻", "倍", "增至", "降至", "从", "提到", "扩大", "收窄", "转正", "转亏", "→", "↑", "↓")
C8_PCT = re.compile(
    r"[0-9]+(?:\.[0-9]+)?\s*(?:%|个百分点)"
    r"|百分之[0-9一二三四五六七八九十]+(?:点[0-9一二三四五六七八九十]+)?"
)
TICKER_RE = re.compile(r"0\d{4,}")  # 股票代码（00001/00700 式）不是数量，剔除


def _c8_tokens(sent):
    return [t for t in C8_NUM.findall(sent)
            if not re.fullmatch(r"(?:19|20)\d{2}", t) and not TICKER_RE.fullmatch(t)]


def change_format_check(segs):
    reds, notes = [], []
    hits, bad = 0, 0
    for s in segs:
        for _a, _b, sent in sentences(s.get("text", "")):
            if not any(c in sent for c in C8_CUE):
                continue
            toks = _c8_tokens(sent)
            if not toks:
                continue
            hits += 1
            miss = []
            if len(toks) < 2:
                miss.append("旧值/新值不成对（只报了 %s）" % "、".join(toks[:3]))
            if not C8_PCT.search(sent):
                miss.append("缺变动幅度±%")
            if miss:
                bad += 1
                reds.append("C8 段%s「%s…」：%s（判据：旧数 → 新数（↑/↓ ±XX%%）四要素）"
                            % (s.get("id"), sent[:24].strip(), "；".join(miss)))
    if hits == 0:
        notes.append("C8 未检出数字变动句（若文案确有变动叙述而零检出，人工复核）")
    else:
        notes.append("C8 数字变动句 %d 句，违规 %d 句" % (hits, bad))
    return reds, notes


# ---------- C8b：变动句声画联动（2026-10-25 用户明确要求：读数字变化 canvas 必须明显变动） ----------
def _real_change_spans(text):
    """实变动句区间：有变化暗示词，且数字 token≥2（旧值/新值成对）或带幅度百分比。
    单 token 命中多为估值锚/比率引用等误报，不强制 cue。返回 [(a, b, sent)]。"""
    spans = []
    for a, b, sent in sentences(text):
        if not any(c in sent for c in C8_CUE):
            continue
        toks = _c8_tokens(sent)
        if len(toks) >= 2 or C8_PCT.search(sent):
            spans.append((a, b, sent))
    return spans


def change_cue_check(segs):
    """C8b：每句实变动句必须有 at 落在该句区间内的状态 cue；全片有 states 而该段没有=红。
    状态帧内容按 SKILL「数字变动呈现规范」：旧数 →（方向箭头）±% → 新数 四要素视觉块。"""
    reds, notes = [], []
    has_states = any(s.get("states") for s in segs)
    if not has_states:
        notes.append("C8b 全片无 states（静态构建），联动门不适用")
        return reds, notes
    checked, miss = 0, 0
    for s in segs:
        text = s.get("text", "")
        spans = _real_change_spans(text)
        if not spans:
            continue
        at_pos = []
        for st in (s.get("states") or []):
            at = st.get("at")
            if at:
                p = text.find(at)
                if p >= 0:
                    at_pos.append((p, p + len(at)))
        for a, b, sent in spans:
            checked += 1
            if not any(pa < b and pb > a for pa, pb in at_pos):
                miss += 1
                reds.append("C8b 段%s「%s…」数字变动句无状态cue——读数字变化时画面必须明显变动："
                            "加 states cue（at=该句解说原词），状态帧在数字原位显示"
                            "「旧数 →（方向箭头）±%% → 新数」四要素视觉块"
                            % (s.get("id"), sent[:22].strip()))
    if checked:
        notes.append("C8b 实变动句 %d 句，缺联动 %d 句" % (checked, miss))
    else:
        notes.append("C8b 无实变动句，联动门通过")
    return reds, notes


# ---------- G4：焦点词（为空则不跑专项） ----------
def focus_checks(segs, words):
    reds, notes = [], []
    has_states = any(s.get("states") for s in segs)
    all_text = "".join(s.get("text", "") for s in segs)
    for w in words:
        w = w.strip()
        if not w:
            continue
        mentioned = w in all_text
        cue_hit = any(w in (st.get("at") or "") for s in segs for st in (s.get("states") or []))
        if not mentioned:
            reds.append("G4 焦点词「%s」全片解说零提及——当期点名重点必须讲到" % w)
        elif has_states and not cue_hit:
            reds.append("G4 焦点词「%s」解说有提及但零 cue——重点词要有声画联动" % w)
        else:
            notes.append("G4 焦点词「%s」提及+cue OK" % w)
    return reds, notes


# ---------- G5：版式标尺 + 时长闸门（36号立，源自36号诊断 A1-A10/B1） ----------
def _g5_consts(code):
    consts = {}
    for m in re.finditer(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(0\.\d+)\s*(?:#.*)?$', code, re.M):
        consts[m.group(1)] = float(m.group(2))
    for m in re.finditer(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(\d+)\s*(?:#.*)?$', code, re.M):
        consts[m.group(1)] = float(m.group(2))
    # 元组赋值（可带尾注）：VY, VFS = 0.175, 30  # 注释
    for m in re.finditer(r'^\s*([A-Z_][A-Z0-9_]*(?:\s*,\s*[A-Z_][A-Z0-9_]*)*)\s*=\s*([0-9.\s,]+?)\s*(?:#.*)?$',
                         code, re.M):
        names = [n.strip() for n in m.group(1).split(",")]
        vals = [v.strip() for v in m.group(2).split(",") if v.strip()]
        if len(names) == len(vals) and len(names) > 1:
            for n, v in zip(names, vals):
                try:
                    consts[n] = float(v)
                except ValueError:
                    pass
    return consts


def layout_scale_check(ep_dir):
    """版式硬标尺（继承 ep01s v3 基准）：标题≥32；结论带 y∈[0.155,0.26] 且 ≥28号
    （theme 默认 0.108/22 视为越线）；图表 axes 底边 <0.205 红 / [0.205,0.24) 黄；
    正文区孤儿浮块（f.text y∈(0.06,0.205) 字面量）=红；卡片/面板底边 <0.19 红 / [0.19,0.205) 黄；
    章节条字号 <13 黄。扫描池与 G3 相同（父目录 *slides*.py）。"""
    reds, warns, notes = [], [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    # 期专属脚本优先（36号修：扫描池曾按目录拼接，导致跨期串味）
    own_name = os.path.basename(os.path.abspath(ep_dir)) + "_slides.py"
    candidates = [os.path.join(parent, own_name),
                  os.path.join(ep_dir, own_name),
                  os.path.join(ep_dir, "slides.py")]
    code = ""
    used = None
    for c in candidates:
        if os.path.exists(c):
            code = open(c, encoding="utf-8").read()
            used = c
            break
    if not code.strip():
        inside = [os.path.join(ep_dir, fn) for fn in sorted(os.listdir(ep_dir))
                  if fn.endswith(".py") and "slides" in fn]
        if len(inside) == 1:
            code = open(inside[0], encoding="utf-8").read()
            used = inside[0]
    if used:
        notes.append("G5 扫描期专属脚本 %s" % os.path.basename(used))
    else:
        for fn in sorted(os.listdir(parent)):
            if fn.endswith(".py") and "slides" in fn:
                code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
        if code.strip():
            notes.append("G5 未找到期专属脚本，退回混合池扫描（建议命名 <ep>_slides.py）")
    if not code.strip():
        return ["G5 未找到画片脚本（期专属 <ep>_slides.py 或父目录 *slides*.py）"], warns, notes
    consts = _g5_consts(code)
    # 全局库感知（37号）：import theme_base36 的脚本，缺省值取库常量而非 theme 旧默认
    lib_based = "theme_base36" in code
    if lib_based:
        libp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme_base36.py")
        if os.path.exists(libp):
            consts.update(_g5_consts(open(libp, encoding="utf-8").read()))

    def res(tok, default):
        tok = (tok or "").strip()
        try:
            return float(tok)
        except ValueError:
            return consts.get(tok, default)

    # 1) 结论带（verdict/verd 调用与 def 处的 y=/fs=；未显式给=theme默认0.108/22，按越线计）
    ys = [res(m.group(1), None) for m in re.finditer(r'verd(?:ict)?\s*\([^)]*?[\s(]y\s*=\s*([0-9A-Za_.]+)', code)]
    fss = [res(m.group(1), None) for m in re.finditer(r'verd(?:ict)?\s*\([^)]*?[\s(]fs\s*=\s*([0-9A-Za_.]+)', code)]
    if not ys or not fss:
        if lib_based:
            if not ys:
                ys = [consts.get("VY", 0.175)]
                notes.append("G5 结论带取全局库常量 VY")
            if not fss:
                fss = [consts.get("VFS", 30)]
                notes.append("G5 结论带字号取全局库常量 VFS")
        else:
            ys = ys or [0.108]
            fss = fss or [22]
    if any(not (0.155 <= y <= 0.26) for y in ys):
        reds.append("G5 结论带位置越线 %s（须 y∈[0.155,0.26]，基准 0.175）" % sorted(set(ys)))
    else:
        notes.append("G5 结论带位置 OK %s" % sorted(set(ys)))
    if any(f < 28 for f in fss):
        reds.append("G5 结论带字号越线 %s（须≥28号，基准 30）" % sorted(set(fss)))
    else:
        notes.append("G5 结论带字号 OK %s" % sorted(set(fss)))

    # 2) 标题字号（def headline size= / TITLE 行 fontsize=）
    tsz = [float(x) for x in re.findall(r'def headline\([^)]*size\s*=\s*(\d+)', code)]
    tsz += [float(x) for x in re.findall(r'TITLE\[[^\]]+\][^\n]*fontsize\s*=\s*(\d+)', code)]
    if tsz and any(t < 32 for t in tsz):
        reds.append("G5 标题字号越线 %s（须≥32号，基准 34）" % sorted(set(tsz)))
    elif tsz:
        notes.append("G5 标题字号 OK %s" % sorted(set(tsz)))
    elif lib_based:
        notes.append("G5 标题由全局库 frame() 提供（TITLE_FS=%d）" % int(consts.get("TITLE_FS", 34)))

    # 3) 图表 axes 底边
    bots = [float(m.group(1)) for m in re.finditer(
        r'(?:axes_panel\(f,\s*\[|add_axes\(\[)\s*[\d.]+\s*,\s*([\d.]+)', code)]
    bad_b = [b for b in bots if b < 0.205]
    warn_b = [b for b in bots if 0.205 <= b < 0.24]
    if bad_b:
        reds.append("G5 图表底边严重越线 %s（<0.205，基准 0.24）" % sorted(set(bad_b)))
    if warn_b:
        warns.append("G5 图表底边偏浅 %s（[0.205,0.24)，基准 0.24）" % sorted(set(warn_b)))
    if not bad_b and not warn_b:
        notes.append("G5 图表底边 OK %s" % sorted(set(bots)))

    # 4) 孤儿浮块（正文区游离 f.text，字面量 y）
    orphans = sorted({m.group(1) for m in re.finditer(r'f\.text\(\s*[^,()]+,\s*(0\.\d+)\s*,', code)
                      if 0.06 < float(m.group(1)) < 0.205})
    if orphans:
        reds.append("G5 孤儿浮块 %s（正文区 y∈(0.06,0.205) 游离 f.text，R3 禁止；应并入主布局或拉通到 0.205）" % orphans)
    else:
        notes.append("G5 孤儿浮块 OK")

    # 5) 卡片/面板底边
    cards = sorted({float(m.group(1)) for m in re.finditer(
        r'\b(?:rbox|stat_card|change_row)\(\s*[^,()]+,\s*(0\.\d+)\s*,', code) if float(m.group(1)) < 0.205})
    if any(c < 0.19 for c in cards):
        reds.append("G5 卡片/面板底边越线 %s（<0.19，基准线 0.205）" % [c for c in cards if c < 0.19])
    mid = [c for c in cards if 0.19 <= c < 0.205]
    if mid:
        warns.append("G5 卡片/面板底边偏浅 %s（[0.19,0.205)）" % mid)
    if not cards:
        notes.append("G5 卡片/面板底边 OK")

    # 6) 章节条字号
    cap = [float(m.group(1)) for m in re.finditer(
        r'f\.text\([^,]+,\s*0\.9[3-8]\d*\s*,[^)]*?fontsize\s*=\s*(\d+(?:\.\d+)?)', code)]
    if cap and any(c < 13 for c in cap):
        warns.append("G5 章节条字号偏小 %s（SKILL 图例红线≥13）" % sorted(set(c for c in cap if c < 13)))
    elif cap:
        notes.append("G5 章节条字号 OK %s" % sorted(set(cap)))
    return reds, warns, notes


def duration_gate(segs):
    """时长闸门（合成前估算，36号立·45号校准系数·51号黄线校准、存量不追溯）：
    系数按 +20% 语速实测校准为 5.4字/秒（52号诊断：4.5 为常速系数，系统性高估时长 20%）。
    51号黄线校准（64号诊断）：实测用户满意成片段长至 243 字（45s），旧黄线 40s=216 字
    正卡工作区间顶部，每期固定产出 5±2 条制度性黄牌噪音——黄线 40s→45s、红线 45s→50s。
    成片后以 cue_timing_check 实际时长复核。"""
    reds, warns, notes = [], [], []
    CPS = 5.4  # 45号校准：+20% 语速实测字/秒（长和 5.47 / 太古 5.32）
    for s in segs:
        est = len(s.get("text", "")) / CPS
        if est > 50:
            reds.append("时长闸门 段%s 估算 %.0fs（%d字）>50s——强制按 5b 规范拆子段" % (s.get("id"), est, len(s.get("text", ""))))
        elif est > 45:
            warns.append("时长闸门 段%s 估算 %.0fs（%d字）>45s——建议拆子段" % (s.get("id"), est, len(s.get("text", ""))))
    if not reds and not warns:
        notes.append("时长闸门 OK（全部≤45s，系数5.4字/秒·45号校准·51号黄线45s）")
    else:
        notes.append("时长闸门：红 %d / 黄 %d（系数5.4·51号黄线校准45s，存量成片不追溯）" % (len(reds), len(warns)))
    return reds, warns, notes




# ---------- 45号：总量与密度三闸门（52号诊断立：太古EP01每条下限都踩线达标却比基准期
# 长和EP1S 缩水 40-58% 仍全绿——时长闸门系数标错且只封顶不兜底、states无下限、构图无密度条款） ----------
CPS_CALIB = 5.4  # +20% 语速实测字/秒（52号诊断：长和 5.47 / 太古 5.32；旧系数 4.5 为常速）

def content_volume_gate(segs, cfg=None):
    """G15 总量闸门：完整版（>=10段）总文案量/预估成片时长/对比段（45号立；51号豁免显性化，64号诊断）。
    锚=基准量纲表（45号实测自长和EP1S 22段/3726字/11:16）：总字数<3200=红（基准86%）；
    预估成片<540s=红（9分钟，防「合规但缩水一半」——太古EP01 6:44 无闸门拦截的教训）；
    段数<20=黄；竞对对比段未检出=黄——**可豁免（51号显性化）**：segments.json 顶层
    "g15_waiver":"理由" 开工声明 → 降为 notes 留痕，黄牌不再靠期期口头豁免空转。"""
    reds, warns, notes = [], [], []
    n = len(segs)
    if n < 10:
        notes.append("G15 段数 %d<10（容易版/科普片），总量闸门不适用" % n)
        return reds, warns, notes
    chars = sum(len(s.get("text", "")) for s in segs)
    est_total = chars / CPS_CALIB
    if chars < 3200:
        reds.append("G15 总文案 %d 字 <3200（基准量纲3726字的86%%）——完整版总量贫血：回文案层补信息点，不是拆句凑字" % chars)
    if est_total < 540:
        reds.append("G15 预估成片 %.0fs <540s（%d字÷5.4）——模板承诺10-13分钟（太古EP01 6:44缩水一半无闸门的教训）" % (est_total, chars))
    if n < 20:
        warns.append("G15 段数 %d <20（基准量纲22段）——确认每段已讲透" % n)
    cmp_kw = ("对比", "同行", "同业", "对手", "排行", "破净", "vs", "VS", "Vs")
    hits = [str(s.get("id")) for s in segs
            if any(k in (s.get("text", "") + " " + s.get("slide", "")) for k in cmp_kw)]
    if hits:
        notes.append("G15 总量 OK：%d段/%d字/预估%.0fs；对比段=%s" % (n, chars, est_total, "、".join(hits)))
    else:
        wv = str((cfg or {}).get("g15_waiver") or "").strip()
        if wv:
            notes.append("G15 竞对段未检出——开工声明豁免留痕（51号显性化）：%s" % wv)
        else:
            warns.append("G15 未检出竞对对比段（模板：竞争对比默认必讲；确需豁免须 segments.json 顶层 "
                         "\"g15_waiver\":\"理由\" 开工声明——51号起豁免显性化）")
    return reds, warns, notes


def cue_density_gate(segs):
    """G16 声画密度闸门：states（cue）总量下限与字/cue 上限（45号立）。
    锚=长和EP1S 100cue/段均4.5/37字每cue：段均states<3.5=红、<4.2=黄；
    全线>48字/cue=红、>42=黄——讲一串数字只切1-2次画面=节奏贫瘠（太古EP01 段均2.5/50字的教训）。"""
    reds, warns, notes = [], [], []
    n = max(1, len(segs))
    cues = sum(len(s.get("states") or []) for s in segs)
    chars = sum(len(s.get("text", "")) for s in segs)
    if not cues:
        return ["G16 全片无 states——声画联动缺失"], warns, notes
    per_seg = cues / n
    per_cue = chars / cues
    no_state = [str(s.get("id")) for s in segs if not (s.get("states") or [])]
    if per_seg < 3.5:
        reds.append("G16 段均 states %.1f <3.5（基准期长和=4.5的77%%）——声画切换密度不足" % per_seg)
    elif per_seg < 4.2:
        warns.append("G16 段均 states %.1f <4.2（基准4.5的93%%）——偏少" % per_seg)
    if per_cue > 48:
        reds.append("G16 全线 %.0f 字/cue >48（基准期=37）——单cue承载过长，画面跟不上解说" % per_cue)
    elif per_cue > 42:
        warns.append("G16 全线 %.0f 字/cue >42（基准37）——偏疏" % per_cue)
    if no_state:
        warns.append("G16 %d 段无 states（%s）——数据/叙述段应有状态切换" % (len(no_state), "、".join(no_state[:6])))
    notes.append("G16 声画密度：%d cue/%d段=段均%.1f；%.0f字/cue（基准4.5/37）" % (cues, n, per_seg, per_cue))
    return reds, warns, notes


_G17_ELEM = [r"f\.text\(", r"f\.add_artist\(",
             r"(?:B\.|T\.)?(?:blk4|panel_row|rowlist|trio_cards|pillar_cards|timeline_ladder|kpi_row|caption_strip|donut|candles|month_ohlc|band_panel|chip_row|card_fit|verd|verdict|headline|axes_panel|hbar_vals|band_panel)\s*\(",
             r"\.bar\(", r"\.barh\(", r"\.plot\(", r"\.pie\(", r"\.fill_between\(",
             r"annotate\(", r"FancyBboxPatch\(", r"Rectangle\(", r"Circle\("]

_G17_ANCHOR = 8.8  # 51号校准：45号条文误记9.5；ep01s gate 实测原文「基准8.8」（64号核对）


def _g17_pages(ep_dir):
    """解析期专属画片脚本逐页元素数 + spec「·NN号制作」制作版本号（51号拆出，供 G19 第6指标复用）。"""
    code = _slides_code(ep_dir)
    _W = {"trio_cards": 3, "pillar_cards": 4, "timeline_ladder": 3, "kpi_row": 3,
          "donut": 3, "candles": 2, "month_ohlc": 2, "chip_row": 3}  # 组件内嵌视觉元素数（52号：组件页同权）
    pages = {}
    for m in re.finditer(r"(?:^|\n)def (s[0-9a-z_]+)\(.*?(?=\ndef |\Z)", code, re.S):
        name, body = m.group(1), m.group(0)
        if name in ("save", "setup", "frame_base", "chrome"):
            continue
        n = sum(len(re.findall(pp, body)) for pp in _G17_ELEM)
        for comp, w in _W.items():
            c = len(re.findall(r"(?:B\.|T\.)?%s\s*\(" % comp, body))
            if c:
                n += c * (w - 1)  # 调用本身已计 1，这里补组件内嵌的其余元素
        pages[name] = n
    make_ver = None
    try:
        cfg = json.load(open(os.path.join(ep_dir, "segments.json"), encoding="utf-8-sig"))
        mv = re.search(r"·([0-9]+)号制作", str(cfg.get("spec") or ""))
        make_ver = int(mv.group(1)) if mv else None
    except Exception:
        pass
    return pages, make_ver


def layout_density_gate(ep_dir):
    """G17 构图密度闸门：逐页视觉元素调用密度（45号立，52号诊断；51号校准+逐页下限，64号诊断）。
    页面函数内 f.text/f.add_artist/命名组件/ax图表/annotate/图形补丁 合计（手绘与组件同权）；
    锚=基准量纲表 页均8.8（51号校准：45号条文误记9.5，ep01s gate 实测原文「基准8.8」）：
    页均<5=红、5-6.9=黄。单页稀疏只记notes（满版大图页合法）。
    **逐页下限（51号立）**：任一页 <4 元素=红——四期页均 8.8→7.3→7.0→5.6 棘轮下行且
    单页 2 元素被均值掩盖（64号实测：长和s10=2/天使s7=2/高鑫s5b=3）；新期执法存量不追溯
    （按 spec「·NN号制作」版本 ≥51 生效）。构图目标=双栏互证。"""
    reds, warns, notes = [], [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G17 未找到画片脚本"], warns, notes
    pages, make_ver = _g17_pages(ep_dir)
    if not pages:
        return ["G17 未解析出页面函数（def sN…）"], warns, notes
    vals = sorted(pages.values())
    avg = sum(vals) / len(vals)
    sparse = sorted(pages.items(), key=lambda kv: kv[1])[:3]
    if avg < 5:
        reds.append("G17 构图密度 页均 %.1f <5（基准量纲8.8的57%%）——按双栏互证重排：主图+右侧明细/变动面板+公式行" % avg)
    elif avg < 7:
        warns.append("G17 构图密度 页均 %.1f <7（基准8.8）——偏疏" % avg)
    if make_ver is not None and make_ver >= 51:
        thin = sorted((n, v) for n, v in pages.items() if v < 4)
        for n, v in thin:
            reds.append("G17 逐页下限 页%s 仅%d元素 <4（51号立·64号：单页塌方不被均值掩盖）——补右侧明细/芯片/公式行成双栏" % (n, v))
        if not thin:
            notes.append("G17 逐页下限 OK（全部≥4元素）")
    else:
        notes.append("G17 逐页下限：存量期（spec制作版本%s号）不追溯" % (make_ver if make_ver else "?"))
    notes.append("G17 构图密度：页均 %.1f 元素/页（%d页，基准8.8·51号校准）；最稀疏 %s" %
                 (avg, len(pages), "、".join("%s=%d" % kv for kv in sparse)))
    return reds, warns, notes



# ---------- C8b-P：变动句状态必须用数字变动组件（40号立，太古EP01失败品教训） ----------
def c8b_visual_gate(ep_dir, segs):
    """每个实变动句的 cue 状态，其段画法必须调用数字变动组件（B.blk4/blk4/B.panel_row/panel_row），
    且组件参数含该句数字 token；行高亮/换底色不顶替变动块。"""
    reds, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    own = os.path.join(parent, os.path.basename(os.path.abspath(ep_dir)) + "_slides.py")
    code = open(own, encoding="utf-8").read() if os.path.exists(own) else ""
    if not code:
        for fn in sorted(os.listdir(ep_dir)):
            if fn.endswith(".py") and "slides" in fn:
                code += open(os.path.join(ep_dir, fn), encoding="utf-8").read() + "\n"
    if not code.strip():
        return ["C8b-P 未找到画片脚本"], notes
    checked = bad = 0
    for s in segs:
        spans = _real_change_spans(s.get("text", ""))
        if not spans:
            continue
        body = code
        m = re.search(r"def s%s\(.*?(?=\ndef |\Z)" % re.escape(str(s.get("id"))), code, re.S)
        if m:
            body = m.group(0)
        has_comp = re.search(r"(?:B\.)?(?:blk4|panel_row)\s*\(", body)
        toks = set()
        for _a, _b, sent in spans:
            for tk in _c8_tokens(sent):
                toks.add(tk.split("%")[0].strip().rstrip("亿"))
            pm = C8_PCT.search(sent)
            if pm:
                toks.add(pm.group(0).replace("%", "").strip())
        comp_ok = False
        for cm in re.finditer(r"(?:B\.)?(?:blk4|panel_row)\s*\(([^)]*)\)", body):
            args = cm.group(1)
            if any(tk and len(tk) >= 2 and tk in args for tk in toks):
                comp_ok = True
                break
        for st in (s.get("states") or []):
            at = st.get("at") or ""
            for _a, _b, sent in spans:
                if at and at in s.get("text", "") and at in sent:
                    checked += 1
                    if has_comp and comp_ok:
                        pass
                    else:
                        bad += 1
                        reds.append("C8b-P 段%s 变动句「%s…」状态未由数字变动组件承载（行高亮不顶替变动块；须 blk4/panel_row 且参数含该句数字）" % (s.get("id"), sent[:18].strip()))
                    break
    if checked:
        notes.append("C8b-P 变动句状态 %d 个，未用变动组件 %d 个" % (checked, bad))
    else:
        notes.append("C8b-P 无变动句状态可查")
    return reds, notes




# ---------- G6：图表密度（39号立，太古v2文字墙教训） ----------
def chart_density_check(ep_dir):
    """期专属脚本：图表调用（donut/bar/barh/candles/band/plot线图）÷ 页面数 ≥50%；
    图型类别 ≥3。数据段文字墙=红。观点/清单页豁免由作者在注释标 #non-data。"""
    reds, warns, notes = [], [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    own = os.path.join(parent, os.path.basename(os.path.abspath(ep_dir)) + "_slides.py")
    code = open(own, encoding="utf-8").read() if os.path.exists(own) else ""
    if not code:
        for fn in sorted(os.listdir(ep_dir)):
            if fn.endswith(".py") and "slides" in fn:
                code += open(os.path.join(ep_dir, fn), encoding="utf-8").read() + "\n"
    if not code.strip():
        return ["G6 未找到画片脚本"], notes
    pages = max(1, len(re.findall(r"(?:B\.frame\(|f = frame_base\()", code)))
    pats = [r"T\.donut\(", r"B\.T\.donut\(", r"(?:B\.)?donut\(", r"\.bar\(", r"\.barh\(",
            r"B\.candles\(|candles\(", r"band_panel\(", r"\.plot\(", r"hbar_vals\("]
    charts = sum(len(re.findall(p, code)) for p in pats)
    kinds = sum(1 for p in pats if re.search(p, code))
    ratio = charts / pages * 100
    if ratio < 50:
        reds.append("G6 图表密度 %d/%d页 = %.0f%% <50%%——数据段文字墙，补图（饼/柱/带/蜡烛）" % (charts, pages, ratio))
    else:
        notes.append("G6 图表密度 OK：%d调用/%d页 = %.0f%%" % (charts, pages, ratio))
    if kinds < 3:
        warns.append("G6 图型类别 %d <3（饼/柱/带/蜡烛至少三种）" % kinds)
    else:
        notes.append("G6 图型类别 OK：%d 类" % kinds)
    return reds, notes




# ---------- G7：构成图信息完备性（40号立，太古「借贷+其他」二类环图教训） ----------
def donut_completeness_check(ep_dir):
    """构成图 items 分类≥4；「其他」类必须排末位。扫描期专属脚本中
    donut 调用链的列表字面量（[(名,值,色),...]），<4类=红。"""
    reds, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    own = os.path.join(parent, os.path.basename(os.path.abspath(ep_dir)) + "_slides.py")
    code = open(own, encoding="utf-8").read() if os.path.exists(own) else ""
    if not code:
        for fn in sorted(os.listdir(ep_dir)):
            if fn.endswith(".py") and "slides" in fn:
                code += open(os.path.join(ep_dir, fn), encoding="utf-8").read() + "\n"
    if not code.strip():
        return ["G7 未找到画片脚本"], notes
    checked = bad = 0
    for m in re.finditer(r"(\w+)\s*=\s*\[([^\]]*)\]", code):
        body = m.group(2)
        n = body.count("), (") + (1 if body.strip().startswith("(") else 0)
        if n < 2:
            continue
        items = re.findall(r"\(\s*['\"]([^'\"]+)['\"]", body)
        if not items:
            continue
        is_mix = any(k in code[max(0, m.start()-200):m.start()] for k in ("donut", "构成", "资产", "负债"))
        if not is_mix:
            continue
        checked += 1
        last = items[-1]
        if n < 4 and not ("其他" in last or "其它" in last and n >= 4):
            if n < 4:
                bad += 1
                reds.append("G7 构成图列表 %s 仅%d类（须≥4类真科目拆分，禁「X+其他」二类环图）" % (items[:2], n))
        other_idx = [k for k, it in enumerate(items) if "其他" in it or "其它" in it]
        if other_idx and other_idx[0] != len(items) - 1:
            bad += 1
            reds.append("G7 列表 %s 「其他」未排末位" % items[:2])
    if checked:
        notes.append("G7 构成图列表 %d 个，违规 %d 个" % (checked, bad))
    else:
        notes.append("G7 无构成图列表字面量可查（如 items 为变量拼接，请人工确认）")
    return reds, notes


# ---------- 43号新增：执法面公共件 ----------
def _slides_code(ep_dir):
    """期专属画片脚本源码（与 G6/G7 同一定位规则）。"""
    parent = os.path.dirname(os.path.abspath(ep_dir))
    own = os.path.join(parent, os.path.basename(os.path.abspath(ep_dir)) + "_slides.py")
    code = open(own, encoding="utf-8").read() if os.path.exists(own) else ""
    if not code:
        for fn in sorted(os.listdir(ep_dir)):
            if fn.endswith(".py") and "slides" in fn:
                code += open(os.path.join(ep_dir, fn), encoding="utf-8").read() + "\n"
    return code


def _drawer_body(code, seg_id):
    """截取 def s<seg_id> 的函数体（到下一个顶层 def 为止）。"""
    m = re.search(r"^def s%s\s*\(" % re.escape(str(seg_id)), code, re.M)
    if not m:
        return None
    nxt = re.search(r"^def ", code[m.end():], re.M)
    return code[m.start():m.end() + nxt.start()] if nxt else code[m.start():]


def hook_conclusion_check(ep_dir, segs):
    """G9（42号条文·43号执法）：结论页=金框大卡+支柱卡（pillar_cards 承载），
    禁 rowlist/KPI 卡当结论页主体；钩子页=K线半区+变动面板半区。
    以 theme_base36 组件调用为执法面，适用 import 全局库的新期（37号后）；段数<10 不拦。"""
    reds, notes = [], []
    if len(segs) < 10:
        notes.append("G9 段数 %d<10（容易版/科普片），结论/钩子页版式不拦" % len(segs))
        return reds, notes
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G9 未找到画片脚本"], notes
    if "import theme_base36" not in code:
        notes.append("G9 非 theme_base36 期（存量），结论/钩子页版式只记不拦")
        return reds, notes
    first_id, last_id = str(segs[0]["id"]), str(segs[-1]["id"])
    body_c = _drawer_body(code, last_id)
    if body_c is None:
        reds.append("G9 未找到结论页 drawer s%s" % last_id)
    else:
        if "pillar_cards(" not in body_c:
            reds.append("G9 结论页 s%s 主体未用 pillar_cards（42号：金框大卡+支柱卡）" % last_id)
        if "rowlist(" in body_c:
            reds.append("G9 结论页 s%s 用了 rowlist 文字列表当主体（42号明文禁止）" % last_id)
        if "kpi_row(" in body_c:
            reds.append("G9 结论页 s%s 用了 KPI 卡当主体（42号明文禁止）" % last_id)
        if "pillar_cards(" in body_c and "rowlist(" not in body_c and "kpi_row(" not in body_c:
            notes.append("G9 结论页 s%s = pillar_cards 承载 OK" % last_id)
    body_h = _drawer_body(code, first_id)
    if body_h is None:
        reds.append("G9 未找到钩子页 drawer s%s" % first_id)
    else:
        has_k = re.search(r"candles\(", body_h)
        has_p = re.search(r"panel_row\(|blk4\(", body_h)
        if not (has_k and has_p):
            reds.append("G9 钩子页 s%s 缺 K线半区(%s)或变动面板半区(%s)（42号固定版式）"
                        % (first_id, bool(has_k), bool(has_p)))
        else:
            notes.append("G9 钩子页 s%s = K线半区+变动面板半区 OK" % first_id)
    return reds, notes


def _drawer_bodies(code):
    """按顶层 def 切分画片脚本为 {函数名: 函数体}。"""
    out, ms = {}, list(re.finditer(r"^def (\w+)\s*\(", code, re.M))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(code)
        out[m.group(1)] = code[m.start():end]
    return out


def layout_overlap_check(ep_dir):
    """G5 扩展（44号）：axes 面板两两相交=红；blk4 与 axes 相交=红。
    44号诊断：太古 s6 地域小图叠在 45亿 主图上，两套 y 轴打架、x 标签被柱吞。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G5 相交检查未找到画片脚本"], notes
    num = r"([0-9.]+|B\.[A-Z_]+|AX_CB|CB)"
    CONST = {"B.AX_CB": 0.24, "AX_CB": 0.24, "B.CB": 0.205, "CB": 0.205}

    def val(tok):
        try:
            return float(tok)
        except ValueError:
            return CONST.get(tok)

    def rects(body, pat, axes4=False, h=0.095):
        out = []
        for m in re.finditer(pat, body):
            l, b, w = (val(m.group(i)) for i in (1, 2, 3))
            hh = val(m.group(4)) if axes4 else h
            if None in (l, b, w, hh):
                continue
            out.append((l, b, w, hh))
        return out
    hit = 0
    for fn, body in _drawer_bodies(code).items():
        axes = rects(body, r"axes_panel\(f, \[" + (num + r", ") * 3 + num, axes4=True)
        axes += rects(body, r"candles\(f, \[" + (num + r", ") * 3 + num, axes4=True)
        b4 = rects(body, r"blk4\(f, " + (num + r", ") * 3)
        everything = [("axes", r) for r in axes] + [("blk4", r) for r in b4]
        for i in range(len(everything)):
            for j in range(i + 1, len(everything)):
                (ka, (l1, b1, w1, h1)), (kb, (l2, b2, w2, h2)) = everything[i], everything[j]
                if ka == "blk4" and kb == "blk4":
                    continue
                if l1 < l2 + w2 and l2 < l1 + w1 and b1 < b2 + h2 and b2 < b1 + h1:
                    reds.append("G5 %s 面板相交：%s%s 与 %s%s（重叠即视觉打架，分栏重排）"
                                % (fn, ka, (round(l1, 2), round(b1, 2), round(w1, 2), round(h1, 2)),
                                   kb, (round(l2, 2), round(b2, 2), round(w2, 2), round(h2, 2))))
                    hit += 1
    if hit:
        notes.append("G5 相交检查：发现 %d 处相交" % hit)
    else:
        notes.append("G5 相交检查 OK（axes/blk4 无矩形相交）")
    return reds, notes


def card_font_check(ep_dir):
    """G13（44号）：手搓卡片字号下限——函数体内 ≥2 个 FancyBboxPatch 且存在
    f.text fontsize<15 的正文字面量=红（用 trio_cards/pillar_cards 组件承载）。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G13 未找到画片脚本"], notes
    bad = []
    for fn, body in _drawer_bodies(code).items():
        if body.count("FancyBboxPatch") < 2:
            continue
        small = [float(x) for x in re.findall(r"f\.text\([^)]*fontsize=([0-9.]+)", body)
                 if float(x) < 15]
        if small:
            bad.append("%s(最小%g号)" % (fn, min(small)))
    if bad:
        reds.append("G13 手搓卡片字号<15：%s——卡片必须用组件（trio_cards/pillar_cards），字要大要饱满" % "、".join(bad))
    else:
        notes.append("G13 卡片字号下限 OK（无 <15 号手搓卡）")
    return reds, notes


def pure_text_data_check(ep_dir, segs):
    """G6 收紧（44号，「4+1图」用户裁定）：含金额的段若画面只有 rowlist 无任何图/内容组件
    =纯文字数据页=红；无金额的观点/清单页豁免。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G6 收紧未找到画片脚本"], notes
    bodies = _drawer_bodies(code)
    chart_pat = r"axes_panel\(|candles\(|\.bar\(|\.barh\(|donut\(|timeline_ladder\(|\.plot\("
    flagged = []
    for seg in segs:
        sid = str(seg["id"])
        body = bodies.get("s" + sid)
        if body is None or "rowlist(" not in body:
            continue
        if re.search(chart_pat, body) or "blk4(" in body or "kpi_row(" in body:
            continue
        if AMOUNT_RE.search(seg.get("text") or ""):
            flagged.append("s%s" % sid)
    if flagged:
        reds.append("G6 纯文字数据页（含金额却只有 rowlist 无图）：%s——每页至少1图（44号「4+1图」条款）"
                    % "、".join(flagged))
    else:
        notes.append("G6 纯文字数据页 OK（含金额段均有图/内容组件）")
    return reds, notes


def baseline_quant_check(ep_dir, segs, cfg):
    """G19 基准量化对照（47号立，55号诊断：样板传承失效第五环——45号量化传承表只是条文，
    无执法载体，后续期「读了头注」照样造出失败品）。契约顶层必须带：
      "baseline": {"ref":"<基准期目录>", "segs":N, "chars":N, "cues":N, "slides":N, "dur_sec":N,
                   "waiver":"可选：低于85%的豁免理由"}
    实绩对照：任一指标 <基准85% = 红（有 waiver → 降黄牌留痕）；<100% = 黄。
    第0步从此有执法载体：不抄基准表不许合成。存量期按 C7「按旧版制作」豁免。"""
    reds, warns, notes = [], [], []
    if len(segs) < 10:
        notes.append("G19 段数 %d<10（容易版/科普片），基准对照不适用" % len(segs))
        return reds, warns, notes
    spec = str(cfg.get("spec") or "")
    if "按旧版制作" in spec:
        notes.append("G19 明示按旧版制作，存量不追溯")
        return reds, warns, notes
    bl = cfg.get("baseline")
    if not isinstance(bl, dict) or not all(k in bl for k in ("segs", "chars", "cues")):
        reds.append("G19 契约缺 baseline 量化对照表（第0步未执行）——完整版新期必须在 segments.json "
                    "顶层抄基准期五指标 {ref/segs/chars/cues/slides/dur_sec}，任一指标<基准85%须附 waiver 豁免理由")
        return reds, warns, notes
    waiver = str(bl.get("waiver") or "").strip()
    chars = sum(len(s.get("text", "")) for s in segs)
    cues = sum(len(s.get("states") or []) for s in segs)
    slides_n = len(segs) + cues
    est_dur = chars / 5.4
    pairs = [("段数", len(segs), bl.get("segs")),
             ("总字数", chars, bl.get("chars")),
             ("states", cues, bl.get("cues")),
             ("画片", slides_n, bl.get("slides")),
             ("预估成片s", round(est_dur), bl.get("dur_sec"))]
    hard = soft = 0
    for name, actual, ref in pairs:
        if not ref:
            continue
        ratio = actual / float(ref)
        if ratio < 0.85:
            hard += 1
            msg = "G19 %s 实绩 %s = 基准 %s 的 %.0f%% (<85%%)" % (name, actual, ref, ratio * 100)
            if waiver:
                warns.append(msg + "——waiver 豁免：" + waiver)
            else:
                reds.append(msg + "——回传承层补密度，或写 baseline.waiver 说明豁免理由")
        elif ratio < 1.0:
            soft += 1
            warns.append("G19 %s 实绩 %s = 基准 %s 的 %.0f%%（<100%%，偏薄）" % (name, actual, ref, ratio * 100))
    # G19 第6指标（51号增·64号诊断：构图密度纳入契约，堵四期 8.8→5.6 棘轮）：
    # baseline 可选 "g17_density": 8.8 —— 实绩页均 <85% 同样红/waiver降黄
    ref_d = bl.get("g17_density")
    if ref_d:
        pages_d, _mv = _g17_pages(ep_dir)
        if pages_d:
            avg_d = sum(pages_d.values()) / len(pages_d)
            ratio_d = avg_d / float(ref_d)
            if ratio_d < 0.85:
                hard += 1
                msg_d = "G19 构图密度 实绩 %.1f = 基准 %s 的 %.0f%% (<85%%)" % (avg_d, ref_d, ratio_d * 100)
                if waiver:
                    warns.append(msg_d + "——waiver 豁免：" + waiver)
                else:
                    reds.append(msg_d + "——补右侧明细/芯片成双栏，或写 baseline.waiver")
            elif ratio_d < 1.0:
                soft += 1
                warns.append("G19 构图密度 实绩 %.1f = 基准 %s 的 %.0f%%（<100%%，偏薄）" % (avg_d, ref_d, ratio_d * 100))
            else:
                notes.append("G19 构图密度 实绩 %.1f ≥ 基准 %s（第6指标·51号）" % (avg_d, ref_d))
    if hard == 0 and soft == 0:
        notes.append("G19 基准对照 OK（基准=%s；五指标全部≥基准）" % bl.get("ref", "?"))
    else:
        notes.append("G19 基准对照（基准=%s）：红 %d / 黄 %d" % (bl.get("ref", "?"), hard, soft))
    return reds, warns, notes


def valuation_bands_check(ep_dir, segs):
    """G18 估值四宫格分位带（46号立，52号修复轮·用户钦定估值表达模式）：
    完整版估值章节必须有一页由 ≥4 处 band_panel( 承载（PB/PE 十年·五年 三区制分位带+现值红点，
    theme_base36.band_panel）；缺=红。数据=自算归母口径或百度序列，口径入标题/页脚。存量不追溯。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G18 未找到画片脚本"], notes
    cfg = json.load(open(os.path.join(ep_dir, "segments.json"), encoding="utf-8-sig"))
    val_ids = []
    for name, ids in cfg.get("chapters") or []:
        if "估值" in str(name):
            val_ids += [str(i) for i in (ids or [])]
    if not val_ids:
        notes.append("G18 无估值章节，不适用")
        return reds, notes
    counts = {}
    for sid in val_ids:
        body = _drawer_body(code, sid) or ""
        counts[sid] = body.count("band_panel(")
    if max(counts.values() or [0]) >= 4:
        quad = max(counts, key=counts.get)
        notes.append("G18 估值四宫格 OK：s%s 承载（各估值段 band_panel %s）"
                     % (quad, "/".join("%s:%d" % (k, v) for k, v in counts.items())))
    else:
        reds.append("G18 估值章节缺四宫格分位带（band_panel×4）：估值主视觉必须为 PB/PE 十年·五年 "
                    "三区制分位带+现值红点（46号·用户钦定模式），各段调用数 %s" % counts)
    return reds, notes


def company_history_check(ep_dir, segs):
    """G14（44号）：公司史章节的段，画面必须由 timeline_ladder 阶梯组件或图表承载，
    禁细线+小点裸时间轴（太古 s3 退化版教训：ep01s 阶梯视觉在 37号固化时丢失）。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G14 未找到画片脚本"], notes
    import os as _os
    cfg = json.load(open(_os.path.join(ep_dir, "segments.json"), encoding="utf-8-sig"))
    bodies = _drawer_bodies(code)
    hist_ids = []
    for name, ids in cfg.get("chapters") or []:
        if "公司史" in str(name):
            hist_ids += [str(i) for i in (ids or [])]
    if not hist_ids:
        notes.append("G14 无公司史章节，不适用")
        return reds, notes
    bad = []
    for sid in hist_ids:
        body = bodies.get("s" + sid)
        if body is None:
            bad.append("s%s(无drawer)" % sid)
            continue
        if "timeline_ladder(" in body or re.search(r"axes_panel\(|candles\(|\.bar\(|donut\(", body):
            continue
        bad.append("s%s" % sid)
    if bad:
        reds.append("G14 公司史页未用阶梯组件也无图：%s——用 timeline_ladder（ep01s s3a 阶梯）承载" % "、".join(bad))
    else:
        notes.append("G14 公司史页组件承载 OK（%s）" % "、".join(hist_ids))
    return reds, notes


def audio_contract_check(ep_dir, segs):
    """G12（43号）：TTS 音频 ↔ 契约文本一致。bounds 词序列（规范化拼接）必须等于
    该段 text（规范化）——改文案不重生 tts = 声画脱节 = 红（47号诊断：S6 改 v5 文案
    加地域构成口播，seg6 音频仍是 v4，口播从未念过地域句，画面却画出地域构成）。
    修复方式：删除该段 tts/segN.mp3 与 bounds 后重跑 build（缺音频=合成前正常）。"""
    import re as _re
    reds, notes = [], []

    def _norm(s):
        return _re.sub(r"[^\w]+", "", s or "")
    checked = 0
    for s in segs:
        sid = str(s["id"])
        mp3 = os.path.join(ep_dir, "tts", "seg%s.mp3" % sid)
        bp = os.path.join(ep_dir, "tts", "seg%s.bounds.json" % sid)
        if not (os.path.exists(mp3) and os.path.exists(bp)):
            continue
        checked += 1
        try:
            b = json.load(open(bp, encoding="utf-8-sig"))
            aud = _norm("".join(w.get("text", "") for w in b))
        except Exception as e:
            reds.append("G12 seg%s bounds 不可读（%s）——删该段 tts 重生" % (sid, e))
            continue
        txt = _norm(s.get("text") or "")
        if aud != txt:
            if txt.startswith(aud) and aud:
                diff = txt[len(aud):][:30]
                hint = "音频缺尾：%s…" % diff
            elif aud.startswith(txt) and txt:
                hint = "文本已改短，音频多出尾段"
            else:
                hint = "内容失配"
            reds.append("G12 seg%s 音频为旧文案（%s）——删 tts/seg%s.mp3+.bounds.json 重生再合成"
                        % (sid, hint, sid))
    if checked:
        if any(r.startswith("G12") for r in reds):
            notes.append("G12 音频契约核对 %d 段，失配见红" % checked)
        else:
            notes.append("G12 音频契约一致（%d 段有音频全对齐）" % checked)
    else:
        notes.append("G12 无已生成音频（合成前首跑正常）")
    return reds, notes


def state_asset_check(ep_dir, segs):
    """G10（43号）：契约 states ↔ 画片脚本 HLS 数量一致 + slides/ 状态 PNG 全存在。
    43号诊断：HLS['6'] 只有1态而契约要 s6_1+s6_2，zip 静默截断致 s6_2.png 未渲染。"""
    reds, notes = [], []
    code = _slides_code(ep_dir)
    if not code.strip():
        return ["G10 未找到画片脚本"], notes
    m = re.search(r"\bHLS\s*=\s*\{(.*?)\}", code, re.S)
    if not m:
        return ["G10 画片脚本未找到 HLS 状态映射表"], notes
    hls_block = m.group(1)
    slides_dir = os.path.join(ep_dir, "slides")
    miss_png, mismatch = [], []
    for seg in segs:
        sid = str(seg["id"])
        n_states = len(seg.get("states") or [])
        mm = re.search(r"[\"']%s[\"']\s*:\s*\[([^\]]*)\]" % re.escape(sid), hls_block)
        n_hls = 0
        if mm:
            n_hls = len([x for x in mm.group(1).split(",") if x.strip()])
        if n_states != n_hls:
            mismatch.append("%s 契约%d态≠HLS%d态" % (sid, n_states, n_hls))
        for st in seg.get("states") or []:
            img = st.get("img")
            if img and not os.path.exists(os.path.join(slides_dir, img)):
                miss_png.append(img)
    # 45号补丁（52号教训）：状态帧与底图零差异=假状态——drawer hl 键改名残留/默认高亮/
    # 金边描金都会产出「有文件、无变化」的死状态。MAE(480x270)<0.15=红；PIL 缺失降级 NOTE
    try:
        from PIL import Image
        import numpy as _np
        _has_pil = True
    except Exception:
        _has_pil = False
        notes.append("G10 零差异像素检查跳过（无 PIL/numpy）")
    if _has_pil:
        dead = []
        for s_ in segs:
            basep = os.path.join(slides_dir, s_.get("slide") or "")
            if not os.path.exists(basep):
                continue
            b_ = _np.asarray(Image.open(basep).convert("RGB").resize((480, 270)), dtype=float)
            for st_ in (s_.get("states") or []):
                sp_ = os.path.join(slides_dir, st_.get("img") or "")
                if not os.path.exists(sp_):
                    continue
                im_ = _np.asarray(Image.open(sp_).convert("RGB").resize((480, 270)), dtype=float)
                d_ = float(_np.abs(im_ - b_).mean())
                if d_ < 0.15:
                    dead.append("段%s %s(MAE %.3f)" % (s_.get("id"), st_.get("img"), d_))
        if dead:
            reds.append("G10 状态帧与底图零差异（假状态）：%s——检查 hl 键改名残留/默认高亮/描边同色" % "、".join(dead[:6]))
        else:
            notes.append("G10 状态帧零差异检查 OK（%d 态全部与底图有像素差）" % sum(len(s_.get("states") or []) for s_ in segs))
    if mismatch:
        reds.append("G10 states↔HLS 脱位（zip 会静默截断）：%s" % "；".join(mismatch))
    else:
        notes.append("G10 states↔HLS 数量一致（%d 段）" % len(segs))
    if miss_png:
        reds.append("G10 slides/ 缺契约状态图 %d 张：%s" % (len(miss_png), "、".join(miss_png[:6])))
    else:
        notes.append("G10 契约状态 PNG 全部在盘")
    return reds, notes


def freshness_check(ep_dir):
    """G11（43号）：final*.mp4 已存在时必须不早于工程最新改动（契约/画片脚本/facts/slides）。
    成片早于工程=陈旧成片，登记交付前必须重建。"""
    reds, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    own = os.path.join(parent, os.path.basename(os.path.abspath(ep_dir)) + "_slides.py")
    finals = sorted(f for f in os.listdir(ep_dir) if f.startswith("final") and f.endswith(".mp4"))
    if not finals:
        notes.append("G11 无成片（合成前门正常；合成后重跑本门复核新鲜度）")
        return reds, notes
    eng = []
    for p in (os.path.join(ep_dir, "segments.json"), os.path.join(ep_dir, "facts.json"), own):
        if os.path.exists(p):
            eng.append(p)
    sld = os.path.join(ep_dir, "slides")
    if os.path.isdir(sld):
        eng += [os.path.join(sld, f) for f in os.listdir(sld)]
    if not eng:
        notes.append("G11 无工程文件可比，跳过")
        return reds, notes
    f_t = os.path.getmtime(os.path.join(ep_dir, finals[0]))
    e_t = max(os.path.getmtime(p) for p in eng)
    import datetime as _dt
    fs, es = _dt.datetime.fromtimestamp(f_t), _dt.datetime.fromtimestamp(e_t)
    if f_t < e_t:
        reds.append("G11 成片 %s(%s) 早于工程最新改动(%s)——陈旧成片，先重建再登记交付"
                    % (finals[0], fs.strftime("%H:%M:%S"), es.strftime("%H:%M:%S")))
    else:
        notes.append("G11 成片新鲜度 OK（%s ≥ 工程 %s）" % (fs.strftime("%H:%M:%S"), es.strftime("%H:%M:%S")))
    return reds, notes


def dualaddr_check():
    """SYNC（43号）：theme_base36.py 用户库↔项目副本哈希一致（运行件漂移=红）；
    无论本脚本从哪一址运行，都对全部已知址互查；单侧独有的 .py 工具记 NOTE。"""
    import hashlib
    reds, notes = [], []
    mydir = os.path.dirname(os.path.abspath(__file__))
    cand = [
        mydir,
        os.path.join(os.environ.get("USERPROFILE", ""),
                     ".config", "opencode", "skills", "stock-video", "scripts"),
        r"D:\AI\.opencode\skill\stock-video\scripts",
    ]
    seen, dirs = set(), []
    for d in cand:
        d = os.path.abspath(d)
        if d not in seen and os.path.isdir(d):
            seen.add(d); dirs.append(d)
    if len(dirs) < 2:
        notes.append("SYNC 仅检出单址（%s）" % mydir)
        return reds, notes
    def _md5(p):
        return hashlib.md5(open(p, "rb").read()).hexdigest()
    for name in ("theme_base36.py", "gate_check.py", "SKILL.md"):
        hashes = {}
        for d in dirs:
            p = os.path.join(d, name)
            if not os.path.exists(p) and name == "SKILL.md":
                p = os.path.join(os.path.dirname(d), name)  # SKILL.md 在 SKILL 根，非 scripts/
            if os.path.exists(p):
                hashes.setdefault(_md5(p), []).append(p)
        if len(hashes) > 1:
            reds.append("SYNC %s 双址漂移（%s）——以 SKILL.md 为准回补后再合成"
                        % (name, " ≠ ".join(sorted(hashes))))
        elif hashes:
            notes.append("SYNC %s 全址一致（%d 址）" % (name, len(dirs)))
    mine = set(f for f in os.listdir(dirs[0]) if f.endswith(".py"))
    for d in dirs[1:]:
        theirs = set(f for f in os.listdir(d) if f.endswith(".py"))
        only_a = sorted(mine - theirs)
        only_b = sorted(theirs - mine)
        if only_a:
            notes.append("SYNC 仅 %s 有（建议补齐）：%s" % (os.path.basename(dirs[0]), "、".join(only_a)))
        if only_b:
            notes.append("SYNC 仅 %s 有（建议补齐）：%s" % (os.path.basename(d), "、".join(only_b)))
    return reds, notes



def _int_lit_dicts(body):
    """drawer 内 int 值 hl 映射 dict（键含数字的状态名、值全 int，≥2 对）。"""
    out = []
    for m in re.finditer(r"\{([^{}]+)\}", body):
        pairs = re.findall(r'"([^"]+)"\s*:\s*(-?\d+)', m.group(1))
        if len(pairs) >= 2 and all(re.search(r"\d", k) for k, _v in pairs):
            out.append((m.group(0), pairs))
    return out


def _balanced_call(body, start):
    """从 start（指向开括号）起做括号平衡扫描，返回闭括号位置。"""
    depth = 0
    for j in range(start, min(start + 8000, len(body))):
        ch = body[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _call_span(body, name):
    """找 name( 调用的完整实参span（括号平衡），返回 (实参文本, 起始)。"""
    out = []
    for m in re.finditer(r"(?<![\w])%s\(" % re.escape(name), body):
        j = _balanced_call(body, m.end() - 1)
        if j > 0:
            out.append((body[m.end():j], m.start()))
    return out


def g20_movement_check(ep_dir, segs):
    """G20 讲到哪亮到哪（49号立，57号 s5a卡死/s4a反转/s7b倒挂诊断）：
    a) 卡死：rowlist 行 hi 恒量/常量，N 行只亮 1 行=红；
    b) 覆盖：行 hi 映射 distinct 不足 min(行数-1,3)=红；
    c) 单调：≥3 态 int 映射按键尾数字排序后值非递减（行序=口播序）=红；
    d) donut explode 科目联动：映射命名 ex/explode_map/ex_map，逐态核对
       「at 所在句须含所亮扇区科目名，含其他科目名=反转红」。返回 (reds, warns, notes)。"""
    reds, warns, notes = [], [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    code = ""
    for fn in sorted(os.listdir(parent)):
        if fn.endswith(".py") and "slides" in fn:
            code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
    if not code.strip():
        return reds, warns, notes
    bodies = _drawer_bodies(code)

    def drawer_of(sid):
        for name, body in bodies.items():
            if re.fullmatch(r"s%s[a-z]?" % re.escape(str(sid)), name):
                return body
        return ""

    def _int_dicts(span):
        out = []
        for m in re.finditer(r"\{([^{}]+)\}", span):
            pairs = re.findall(r'"([^"]+)"\s*:\s*(-?\d+)', m.group(1))
            if len(pairs) >= 2 and all(re.search(r"\d", k) for k, _v in pairs):
                out.append((m.group(0), pairs))
        return out

    def _key_tail(k):
        g = re.findall(r"(\d+)", k)
        return int(g[-1]) if g else 0

    for s in segs:
        sid = str(s.get("id"))
        body = drawer_of(sid)
        if not body:
            continue
        states = s.get("states") or []
        # 行数 = rowlist/rl 行字面量元组数 + panel_row 调用数
        rows_n = 0
        hi_dicts = []
        for args, _pos in _call_span(body, "rowlist") + _call_span(body, "rl"):
            rows_n += len(re.findall(r"\(", args.split("hi=")[0])) if "hi=" in args else 0
            m_hi = re.search(r"hi\s*=\s*\{([^{}]+)\}", args)
            if m_hi:
                hi_dicts.append("{" + m_hi.group(1) + "}")
            else:
                m_var = re.search(r"hi\s*=\s*(\w+)(?:\.|\)|,)", args)
                if m_var and m_var.group(1) not in ("None",):
                    m2 = re.search(r"%s\s*=\s*\{([^{}]+)\}" % re.escape(m_var.group(1)), body)
                    if m2 and re.search(r"\"", m2.group(1)):
                        hi_dicts.append("{" + m2.group(1) + "}")
        for args, _pos in _call_span(body, "panel_row"):
            rows_n += 1
        m_const = re.search(r"hi\s*=\s*\(\s*(\d+)\s+if\s+hl\b.*?else\s+None\s*\)", body, re.S)
        if m_const and rows_n >= 3:
            reds.append("G20a2 段%s 行面板常量高亮：hi 恒为第 %s 行（%d 行只亮 1 行）——讲到哪亮到哪，逐行推进"
                        % (sid, m_const.group(1), rows_n))
        for hd in hi_dicts:
            pairs = re.findall(r'"([^"]+)"\s*:\s*(-?\d+)', hd)
            vals = [int(v) for _k, v in pairs]
            distinct = len(set(vals))
            if rows_n >= 3 and distinct < min(rows_n - 1, 3):
                reds.append("G20a 段%s 行面板卡死：%d 行只点亮过 %d 行（%s）——讲到哪亮到哪，逐行推进"
                            % (sid, rows_n, distinct, hd[:70]))
            if len(pairs) >= 3:
                keyed = sorted(pairs, key=lambda kv: _key_tail(kv[0]))
                seq = [int(v) for _k, v in keyed]
                if any(seq[i + 1] < seq[i] for i in range(len(seq) - 1)):
                    reds.append("G20c 段%s 行序倒挂：%s（口播序键 %s）——行序须随口播序单调不回跳"
                                % (sid, seq, [k for k, _v in keyed]))
        for dsrc, pairs in _int_dicts(body):
            if len(pairs) >= 3:
                keyed = sorted(pairs, key=lambda kv: _key_tail(kv[0]))
                seq = [int(v) for _k, v in keyed]
                if any(seq[i + 1] < seq[i] for i in range(len(seq) - 1)):
                    if rows_n and max(int(v) for _k, v in pairs) < rows_n:
                        reds.append("G20c 段%s 映射行序倒挂：%s（口播序键 %s）——行序须随口播序单调不回跳"
                                    % (sid, seq, [k for k, _v in keyed]))
                    else:
                        warns.append("G20c-warn 段%s 高亮序非单调：%s（图表/卡类高亮随口播回跳属正常，人工核）"
                                     % (sid, seq))
        # d) explode 科目联动
        if "donut(" in body:
            m_ex = re.search(r"explode_idx\s*=\s*(\w+|\()", body)
            if m_ex:
                token = m_ex.group(1)
                d = None
                if token == "(":
                    m2 = re.search(r"explode_idx\s*=\s*\(\s*(\{[^}]+\})", body)
                    d = m2.group(1) if m2 else None
                else:
                    m2 = re.search(r"%s\s*=\s*\{([^}]+)\}" % re.escape(token), body)
                    d = m2.group(1) if m2 else None
                    if d is None and token not in ("ex", "explode_map", "ex_map"):
                        reds.append("G20d 段%s donut explode 映射须命名 ex/explode_map/ex_map（现=%s）——否则无法静态核科目联动"
                                    % (sid, token))
                        d = None
                if d:
                    pairs = re.findall(r'"([^"]+)"\s*:\s*(\d+)', d)
                    m_it = re.search(r"donut\(.*?\[((?:\([^)]*\),?\s*)+)\]", body, re.S)
                    items = re.findall(r"\(\s*\"([^\"]+)\"", m_it.group(1)) if m_it else []
                    img2at = {st.get("img", "").replace(".png", ""): st.get("at", "")
                              for st in states}
                    for k, idx in pairs:
                        at = img2at.get(k, "")
                        sent = ""
                        for _a, _b, sp in sentences(s.get("text", "")):
                            if at and at in sp:
                                sent = sp
                                break
                        ii = int(idx)
                        if ii < len(items) and sent:
                            if items[ii] in sent:
                                notes.append("G20d 段%s explode %s→%s 联动正确" % (sid, k, items[ii]))
                            else:
                                hit = [nm for nm in items if nm != items[ii] and nm in sent]
                                if hit:
                                    reds.append("G20d 段%s explode 反转：态%s（口播句含科目「%s」）却点亮「%s」"
                                                % (sid, k, hit[0], items[ii]))
                                else:
                                    notes.append("G20d 段%s explode %s→%s 中性（at句无科目名，人工核）"
                                                 % (sid, k, items[ii]))
    return reds, warns, notes


def _spec_cur():
    skill_md = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md"))
    m = re.search(r"规约版本[:：]\s*SKILL\s*[0-9-]+·([0-9]+)号", open(skill_md, encoding="utf-8").read())
    return m.group(1) + "号" if m else None


def g21_valuation_trio(ep_dir, segs, cur):
    """G21 估值三件套（49号立，57号漏做双锚卡+接住图诊断）：新期（spec 含当前版本号）估值章
    除四宫格外必须含 anchor_pair 双锚卡与「安全边际线」接住图，缺一=红；存量不追溯。"""
    reds, notes = [], []
    spec = ""
    for s in segs:
        spec = str(s.get("spec") or "")
        if spec:
            break
    cfg = os.path.join(ep_dir, "segments.json")
    if os.path.exists(cfg) and not spec:
        spec = str(json.load(open(cfg, encoding="utf-8-sig")).get("spec") or "")
    if not cur or not spec or cur not in spec:
        notes.append("G21 估值三件套：存量期（spec=%s）不追溯" % (spec[:30] or "无"))
        return reds, notes
    parent = os.path.dirname(os.path.abspath(ep_dir))
    code = ""
    for fn in sorted(os.listdir(parent)):
        if fn.endswith(".py") and "slides" in fn:
            code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
    if "band_panel(" not in code:
        return reds, notes
    if "anchor_pair(" not in code:
        reds.append("G21 估值三件套缺双锚卡：估值章须 anchor_pair（资产锚/盈利锚，取高+弃用标注）")
    else:
        notes.append("G21 双锚卡 anchor_pair OK")
    if "安全边际线" not in code:
        reds.append("G21 估值三件套缺接住图：须画「安全边际线 vs 月收盘」历史接住验证（axhline+月线+现值点）")
    else:
        notes.append("G21 接住图（安全边际线）OK")
    return reds, notes


def g22_progressive_mask(ep_dir, segs, cur):
    """G22 渐进披露（49号立）：新期（spec 含当前版本号）凡用 panel_row/rowlist 的数字段，
    调用须启用 mask=True（初态「…」，口播提到才填真值）；缺失=红；存量不追溯。"""
    reds, notes = [], []
    spec = ""
    for s in segs:
        spec = str(s.get("spec") or "")
        if spec:
            break
    if not spec:
        cfgp = os.path.join(ep_dir, "segments.json")
        if os.path.exists(cfgp):
            spec = str(json.load(open(cfgp, encoding="utf-8-sig")).get("spec") or "")
    if not cur or not spec or cur not in spec:
        notes.append("G22 渐进披露：存量期（spec=%s）不追溯" % (spec[:30] or "无"))
        return reds, notes
    parent = os.path.dirname(os.path.abspath(ep_dir))
    code = ""
    for fn in sorted(os.listdir(parent)):
        if fn.endswith(".py") and "slides" in fn:
            code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
    if not re.search(r"(?:panel_row|rowlist|rl)\(", code):
        return reds, notes
    if "mask=True" not in code:
        reds.append("G22 渐进披露未启用：panel_row/rowlist 数字行须 mask=True（初态…，口播提到才填真值）")
    else:
        notes.append("G22 渐进披露 mask=True OK")
    return reds, notes


def semantic_color_warn(ep_dir):
    """语义色映射（49号表达规范）：rowlist/rl 行 ≥3 且全部 2 元组（无色）或色全同=WARN
    （科目语义色：RED 风险/一次性、BLUE 负债或基本盘、GOLD 现金类、TXT 中性——长和 ep01s 实证）。"""
    warns, notes = [], []
    parent = os.path.dirname(os.path.abspath(ep_dir))
    code = ""
    for fn in sorted(os.listdir(parent)):
        if fn.endswith(".py") and "slides" in fn:
            code += open(os.path.join(parent, fn), encoding="utf-8").read() + "\n"
    for m in re.finditer(r"(?:rowlist|rl)\([^)]*?\[([^]]+)\]", code, re.S):
        rows = re.findall(r"\(([^()]+)\)", m.group(1))
        if len(rows) < 3:
            continue
        colors = []
        two_tuple = 0
        for r in rows:
            parts = [p.strip() for p in r.split(",")]
            if len(parts) >= 3:
                colors.append(parts[2])
            elif len(parts) == 2:
                two_tuple += 1
        if two_tuple == len(rows):
            warns.append("语义色缺失：rowlist %d 行全部 2 元组（经包装默认 TXT）——行色应随科目语义取色" % len(rows))
            continue
        if colors and len(set(colors)) == 1:
            warns.append("语义色单一：rowlist %d 行全部同色 %s——应随科目语义取色" % (len(rows), colors[0]))
    if not warns:
        notes.append("语义色：rowlist 行色多样 OK")
    return warns, notes


def run_checks(ep_dir, focus_cli=None):
    reds, notes, warns = [], [], []
    cfg = json.load(open(os.path.join(ep_dir, "segments.json"), encoding="utf-8-sig"))
    segs = cfg["segments"]
    has_states = any(s.get("states") for s in segs)

    # C8 先跑：全段适用，不依赖表段
    r8, n8 = change_format_check(segs)
    reds += r8; notes += n8
    # C8b 变动句声画联动（2026-10-25 用户要求：读数字变化 canvas 必须明显变动）
    r8b, n8b = change_cue_check(segs)
    reds += r8b; notes += n8b

    # G1 三大表齐全 + G2 段内同权
    found = {}
    for label, kws in TABLE_DEFS:
        core = find_table_segment(segs, kws)
        if core is not None:
            found[label] = core
    missing = [lb for lb, _k in TABLE_DEFS if lb not in found]
    if len(segs) >= 10 and missing:
        reds.append("G1 完整版（%d 段）缺三大表段：%s——三大表分析每张表都要有"
                    % (len(segs), "、".join(missing)))
    elif missing:
        notes.append("G1 段数 %d<10（容易版/科普片），未检出表段不拦：%s"
                     % (len(segs), "、".join(missing)) if missing else "G1 三大表齐全")
    else:
        notes.append("G1 三大表段齐全（%s）" % "、".join(found))
    for label, core in found.items():
        fam = segment_family(segs, core)
        r2, n2 = g2_segment_checks(label, fam, has_states)
        reds += r2; notes += n2

    # G3 两半对称（仅资产负债表段）
    if "资产负债表段" in found:
        fam = segment_family(segs, found["资产负债表段"])
        text = fam["text"]
        a_spans = side_spans(text, ASSET_KW)
        l_spans = side_spans(text, LIAB_KW)
        if not a_spans:
            reds.append("G3 资产负债表段资产侧叙述为零（两半对称：资产侧也要讲）")
        if not l_spans:
            reds.append("G3 资产负债表段负债侧叙述为零（两半对称：只有资产半边=不合格）")
        if a_spans and l_spans:
            notes.append("G3 两半叙述：资产侧 %d 字 / 负债侧 %d 字"
                         % (sum(b - a for a, b, _p in a_spans), sum(b - a for a, b, _p in l_spans)))
        r3, n3 = two_side_chart_check(ep_dir)
        reds += r3; notes += n3
        # C5 用资产负债表段族跑（段尾高亮驻留最易在此发生）
        comps, info = rest_highlight_count(ep_dir, fam)
        if comps is None:
            notes.append("C5 跳过（%s）" % info)
        elif comps > 1:
            reds.append("C5 段尾静止帧高亮连通区 %d 处 > 1（%s）" % (comps, info))
        else:
            notes.append("C5 段尾高亮 %d 处" % comps)
    else:
        notes.append("G3/C5 无资产负债表段，两半与段尾检查不适用")

    # G4 焦点词：CLI 覆盖 segments.json focus
    focus = focus_cli if focus_cli is not None else (cfg.get("focus") or [])
    if focus:
        rf, nf = focus_checks(segs, focus)
        reds += rf; notes += nf
    else:
        notes.append("G4 无焦点词（为空=只跑三大表通用标准）")

    # C4 链式继承
    r4, n4 = chain_check(ep_dir)
    reds += r4; notes += n4

    # C7 规约版本标注（43号起加时效执法：spec 须含 SKILL.md 当前版本号，或明写「按旧版制作」）
    spec = str(cfg.get("spec") or "").strip()
    if not spec:
        reds.append("C7 segments.json 缺 spec 字段（标注所依据的 SKILL 版本日期，或「按旧版制作」）")
    else:
        skill_md = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md"))
        cur = None
        if os.path.exists(skill_md):
            mver = re.search(r"规约版本[:：]\s*SKILL\s*[0-9-]+·([0-9]+)号",
                             open(skill_md, encoding="utf-8").read())
            if mver:
                cur = mver.group(1) + "号"
        if cur is None:
            notes.append("C7 规约标注: %s（未读到 SKILL.md 版本行，时效不查）" % spec)
        elif "按旧版制作" in spec:
            notes.append("C7 规约标注: %s（明示按旧版制作，存量不追溯）" % spec)
        elif cur in spec:
            notes.append("C7 规约标注: %s（与权威版本行 %s 一致）" % (spec, cur))
        else:
            reds.append("C7 规约标注过期：spec=%s 不含当前权威版本 %s（重制/新期必须按最新版制作）"
                        % (spec, cur))

    # G5 版式标尺 + 时长闸门（36号立）
    r5, w5, n5 = layout_scale_check(ep_dir)
    reds += r5; warns += w5; notes += n5
    r5d, w5d, n5d = duration_gate(segs)
    reds += r5d; warns += w5d; notes += n5d
    # 45号新增执法面（总量与密度三闸门，52号诊断：合规但贫血）
    r15, w15, n15 = content_volume_gate(segs, cfg)
    reds += r15; warns += w15; notes += n15
    r16, w16, n16 = cue_density_gate(segs)
    reds += r16; warns += w16; notes += n16
    r17, w17, n17 = layout_density_gate(ep_dir)
    reds += r17; warns += w17; notes += n17
    r8p, n8p = c8b_visual_gate(ep_dir, segs)
    reds += r8p; notes += n8p
    r6, n6 = chart_density_check(ep_dir)
    reds += r6; notes += n6
    r7, n7 = donut_completeness_check(ep_dir)
    reds += r7; notes += n7
    # 43号新增执法面
    r9, n9 = hook_conclusion_check(ep_dir, segs)
    reds += r9; notes += n9
    r10, n10 = state_asset_check(ep_dir, segs)
    reds += r10; notes += n10
    r12, n12 = audio_contract_check(ep_dir, segs)
    reds += r12; notes += n12
    # 44号新增执法面（画面密度与图表达）
    r5o, n5o = layout_overlap_check(ep_dir)
    reds += r5o; notes += n5o
    r13, n13 = card_font_check(ep_dir)
    reds += r13; notes += n13
    r6t, n6t = pure_text_data_check(ep_dir, segs)
    reds += r6t; notes += n6t
    r14, n14 = company_history_check(ep_dir, segs)
    reds += r14; notes += n14
    r18, n18 = valuation_bands_check(ep_dir, segs)
    reds += r18; notes += n18
    r19, w19, n19 = baseline_quant_check(ep_dir, segs, cfg)
    reds += r19; warns += w19; notes += n19
    r11, n11 = freshness_check(ep_dir)
    reds += r11; notes += n11
    rs, ns = dualaddr_check()
    reds += rs; notes += ns

    # G20/G21/G22/语义色（49号）
    r20, w20, n20 = g20_movement_check(ep_dir, segs)
    reds += r20; warns += w20; notes += n20
    _cur = _spec_cur()
    r21, n21 = g21_valuation_trio(ep_dir, segs, _cur)
    reds += r21; notes += n21
    r22, n22 = g22_progressive_mask(ep_dir, segs, _cur)
    reds += r22; notes += n22
    wsc, nsc = semantic_color_warn(ep_dir)
    warns += wsc; notes += nsc

    # W1 重做登记（告警不阻塞）
    parent = os.path.dirname(os.path.abspath(ep_dir))
    finals = []
    for root, dirs, files in os.walk(parent):
        for fn in files:
            if fn.startswith("final") and fn.endswith(".mp4"):
                finals.append(os.path.relpath(os.path.join(root, fn), parent))
    has_log = os.path.exists(os.path.join(parent, "变更日志.md"))
    if (len(finals) > 1 or any(x in " ".join(finals) for x in ("final2", "final3"))) and not has_log:
        warns.append("W1 检测到多个成片/重做目录（%s）但无 变更日志.md——整包重做必须先登记原因"
                     % "、".join(finals[:4]))
    return reds, notes, warns


def run_gate(ep_dir, focus_cli=None, full=False):
    """合成前自动质检门。输出默认瘦身（T1·51号）：只回红黄 + 较上次报告新增的 notes；
    --full 才给全量 notes（64号：修复轮 59 条 notes × 每轮全量回读是 token 大头）。
    每次运行追加 <ep>/flow_log.jsonl（G26·51号）：时间/红黄计数/notes数/耗时——复盘免 mtime 考古。"""
    import time as _t
    import datetime as _dt
    _t0 = _t.time()
    print("=== 合成前自动质检门 gate_check ===")
    reds, notes, warns = run_checks(ep_dir, focus_cli)
    prev_notes = set()
    rep = os.path.join(ep_dir, "gate_report.json")
    if os.path.exists(rep):
        try:
            _prev = json.load(open(rep, encoding="utf-8"))
            if isinstance(_prev, dict):
                prev_notes = set(_prev.get("notes") or [])
        except Exception:
            prev_notes = set()
    new_notes = [n for n in notes if n not in prev_notes]
    if full:
        show, tag = notes, "全量%d" % len(notes)
    else:
        show, tag = new_notes, "新增%d/%d" % (len(new_notes), len(notes))
    for n in show:
        print("  PASS/NOTE:", n)
    for w in warns:
        print("  WARN:", w)
    for r in reds:
        print("  GATE RED:", r)
    print("=== 质检门: %d 红, %d 告警 | notes %s（T1瘦身，--full 看全量）| 耗时 %.1fs ==="
          % (len(reds), len(warns), tag, _t.time() - _t0))
    try:
        json.dump({"reds": reds, "notes": notes, "warns": warns},
                  open(rep, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass
    try:
        with open(os.path.join(ep_dir, "flow_log.jsonl"), "a", encoding="utf-8") as _f:
            _f.write(json.dumps({"at": _dt.datetime.now().isoformat(timespec="seconds"),
                                 "reds": len(reds), "warns": len(warns), "notes": len(notes),
                                 "dur_sec": round(_t.time() - _t0, 1)}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if reds:
        sys.exit("GATE RED: 合成被阻止，先修复以上 %d 项" % len(reds))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python gate_check.py <ep目录> [--focus 词1,词2] [--full]")
        sys.exit(2)
    fwords = None
    if "--focus" in sys.argv:
        i = sys.argv.index("--focus")
        fwords = [w for w in (sys.argv[i + 1].split(",") if len(sys.argv) > i + 1 else []) if w.strip()]
    run_gate(sys.argv[1], fwords, full=("--full" in sys.argv))
