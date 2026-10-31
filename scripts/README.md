# stock-video scripts

## 在用

| 文件 | 用途 |
|---|---|
| `motion.py` | 暗色个股片逐帧动画引擎：画布/缓动/图表原语/片头条/字幕/配音/铺底音乐/并行渲染/混音。用法见文件头注与 SKILL.md 第 4~5 步 |
| `components.py` | 54号起：分镜常用组件 `tile / vbars / line_chart / year_labels / hline / val_panel / pct_stats / quote / xfade`，57号补丁十加 `legend`（小图例；红绿不表示涨跌时必加）。56号起另有 facts.py 用的 `put`（数和说法一起冻结到 facts.json 的 `labels`）、`window_1y`（近一年 = 截止日往回 365 天）。两期以上用到的部件再收进来；不收"空卡片占位框" |
| `fx.py` | 56号补丁一起：有含义的动效 `count`（数字变成另一个数）/ `fly`（数从图上飞进算式）/ `equation`（算式一项项拼出）/ `split`（一根条拆段、某段掉出去）/ `drain`（钱按年花掉）/ `zoom`（放大一小块）/ `strike`（划掉）。只新增、不改 motion.py，旧工程不受影响。用法看 `python api_ref.py` |
| `review_pack.py` | 54号起：成片审片包 `python review_pack.py <工程> [--video x.mp4] [--out 目录]` → 每章按句精确抽帧拼图 + `审片包.md`（旁白、念到的东西画面上有没有、内容区静止段、数字对账、56号起：旁白数字 ↔ facts 说法对照、推断句、推算句、观众 / 口径两组审片问题）。给两个独立审片人用 |
| `motion.py` 的 `check` | 55号起：`python video.py check`（preview 末尾自动跑），不渲染，按每条字幕念完前一刻跑分镜，列出"念到的数字画面上没有 / 只有章标题 / 空框"，57号补丁十起加"字太小 / 红绿没图例 / 示意没标" → `output\check.txt`。是清单，不是闸门 |
| `fetch_data.py` | A股个股+同行数据抓取（东财，断连回退新浪）：`python fetch_data.py <代码> <输出目录> [同行代码…] [--notes=科目,…] [--no-numbers / --no-reports]`；下载年报 / 半年报后调用 `report_cut.py` |
| `report_cut.py` | 57号补丁十一：定期报告 PDF → 带页标记的 `_全文.txt`（`=====PDF第N页=====`）、`_管理层讨论与分析.txt`、`_附注_<科目>.txt`（主要会计数据、分季度、关键审计事项、利润分配、所得税、有息负债各项、减值、现金流量表补充资料、分部、期后事项等）、`_目录索引.md`（各节起始页、切好的段、合并报表 / 诉讼 / 关联交易 / 担保的页码、没切到的项）。季报、港股手动跑：`python report_cut.py <PDF> [输出目录] [--notes=科目,…]` |
| `fetch_hk.py` | 港股个股+同行数据抓取（东财 / 百度估值，断连回退新浪）：`python fetch_hk.py <代码> <输出目录> [同行港股代码…]`。三大表金额是人民币折算，公告原文需手动下载（见 方法与口径 §1） |
| `build_v4.py` / `web_template_ep03.html` / `gsap.min.js` | 纸面科普线（竖屏 GSAP 逐帧） |
| `build_v3.py` | 纸面线快速版（静态状态图硬切） |

模板在 `..\templates\`：`故事模板.md`（先算后写）、`video_skeleton.py`（分镜骨架，不带任何一期的章节）。

## 51号旧暗色管线（停用，仅保留查阅）

`build_all.py`、`theme.py`、`theme_base36.py`、`gate_check.py`、`cue_timing_check.py`、`fullframe_accept.py`、`regression_check.py`、`baseline_frame_compare.py`、`make_checklist.py`、`qa_video.py`、`subs.py`、`calibrate.py`。
停用原因见 CHANGELOG 52号。旧版 README 在作者本机备份，不在仓库里。
