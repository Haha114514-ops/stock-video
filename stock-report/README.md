# stock-report

A 股 / 港股个股**图文报告**（PDF）的制作流程。和同仓库的 stock-video（视频）用同一套读表方法、口径和红线：
抓财报数据 → 读三张表、写故事 → 报告稿 → 图表 → PDF。规则在 `SKILL.md`，脚本在 `scripts/`。

## 安装

stock-report 依赖 stock-video（抓数脚本、`方法与口径.md`、`facts_peek.py`、数字对账）。两个并排装：

- Claude Code：把本仓库装在 `~/.claude/skills/stock-video/`，再把 `stock-report/` 这个文件夹复制（或软链接）到 `~/.claude/skills/stock-report/`
- OpenCode：同理放到 `~/.config/opencode/skills/` 下
- 放在别处时设环境变量 `STOCK_VIDEO_SKILL=<stock-video 目录>`

依赖和 stock-video 相同（`requirements.txt`），另加 `markdown`：

```bash
.venv/bin/pip install -r requirements.txt markdown
```

出 PDF 要 Chrome / Edge，或 `playwright install chromium`。之后对助手说"做个 XX 的报告"即可。

## 脚本

| 文件 | 用途 |
|---|---|
| `scripts/rlib.py` | 找 stock-video；facts.py 用的 `put / pct_stats / window_1y`（和 stock-video components.py 同一写法）；`{{键|规格}}` 的格式化 |
| `scripts/rcharts.py` | 报告图表（matplotlib → SVG）：瀑布图、资产负债表两根柱、现金桥、业务构成、多年柱 / 折线 / 横条、估值四宫格、股价 + 参考价。`focus=` 强调，`note=` 角注；暗色 / 白底两套主题 |
| `scripts/build_report.py` | 报告稿.md + facts.json + charts.py → `output/报告.html` + `报告.pdf` |
| `scripts/report_check.py` | 交审 / 出 PDF 前的检查（对应视频的 plan_check）：文件头、`{{键}}`、三表总览、红线、未经审计、数字对账、推断 / 推算 |

模板在 `templates/`：`报告稿模板.md`、`charts_skeleton.py`、`子代理任务书.md`。故事模板直接用 stock-video 的 `templates/故事模板.md`。
