# stock-video

A 股 / 港股个股拆解视频的制作流程：抓财报数据 → 读三张表、写故事 → 旁白配音 → 逐帧动画 → 成片。
它是一个给 AI 编程助手用的 skill（Claude Code、OpenCode 都能用），规则写在 `SKILL.md`，脚本在 `scripts/`。
macOS、Windows 都能用（Linux 装好中文字体也行）。

## 安装

1. 下载本仓库（`git clone`，或网页上 Code → Download ZIP）。
2. 放到助手能找到 skill 的位置，任选其一：
   - Claude Code：`~/.claude/skills/stock-video/`（所有项目可用；Windows 是 `C:\Users\<你的用户名>\.claude\skills\stock-video\`），或某个项目里的 `.claude/skills/stock-video/`
   - OpenCode：`~/.config/opencode/skills/stock-video/`
   - 放别处也行，在项目的 `.claude/skills/stock-video/SKILL.md` 里写一行"正本在 <路径>，先读它"指过去，再设环境变量 `STOCK_VIDEO_SKILL`。
3. 装依赖（见下），之后对助手说"做个 XX 的视频"即可。

## 需要先装好

- **Python 3.10~3.13**（太新的版本如 3.14+ 可能还没有 numpy / pandas 的现成安装包）。建议用虚拟环境：
  ```bash
  python3.12 -m venv .venv
  .venv/bin/pip install -r requirements.txt     # Windows：.venv\Scripts\pip install -r requirements.txt
  ```
  竖屏科普片（`build_v4.py`）没装 Chrome / Edge 时还要 `.venv/bin/playwright install chromium`。
- **ffmpeg**：命令行能直接运行 `ffmpeg`、`ffprobe`（macOS：`brew install ffmpeg`；Windows：下载后加进 PATH）。
  - 竖屏科普片烧字幕要 ffmpeg 带 libass。Homebrew 默认的 ffmpeg 不带，可以换成
    `brew tap homebrew-ffmpeg/ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg`；不换也能出片，只是字幕作为外挂 `final.srt`。
  - 横屏个股片的字幕由脚本自己画，不需要 libass。
- **字体**：自动按系统取，不用另装——
  - macOS：苹方 PingFang SC（正文 / 粗体）、DIN Alternate Bold（数字）
  - Windows：微软雅黑、Bahnschrift
  - Linux：思源黑体 Noto Sans CJK（`apt install fonts-noto-cjk`）、DejaVu Sans
- 配音用微软 Edge 在线语音（edge-tts），需要联网。

装好后跑一次，看本机实际用到的字体、ffmpeg、并行数：

```bash
python scripts/sysenv.py
```

## 可选的环境变量

| 变量 | 作用 |
|---|---|
| `STOCK_VIDEO_SKILL` | skill 目录。工程不在装了 skill 的工作区里时，`video.py` 靠它找脚本 |
| `STOCK_VIDEO_FONT_R` / `_B` / `_N` | 正文 / 粗体 / 数字字体，写 `路径` 或 `路径#ttc序号` |
| `STOCK_VIDEO_SUB_FONT` | 竖屏片烧字幕用的字体名 |
| `STOCK_VIDEO_FFMPEG` / `STOCK_VIDEO_FFPROBE` | 指定 ffmpeg / ffprobe（例如另装的带 libass 的版本） |
| `STOCK_VIDEO_JOBS` | 渲染并行进程数（默认 CPU 核数，最多 8；也可 `python video.py render --jobs 4`） |
| `STOCK_VIDEO_BROWSER` | 竖屏片用的浏览器可执行文件 |

## 更新

作者改了规则或脚本会推到这里，改了什么写在 `CHANGELOG.md`。`git pull` 拿最新版。

## 声明

视频内容只解读公开财报，不构成投资建议。`scripts/gsap.min.js` 是 GreenSock 的 GSAP 3.12.5，按其许可证使用。
