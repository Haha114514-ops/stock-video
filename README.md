# stock-video

A 股 / 港股个股拆解视频的制作流程：抓财报数据 → 读三张表、写故事 → 旁白配音 → 逐帧动画 → 成片。
它是一个给 AI 编程助手用的 skill（Claude Code、OpenCode 都能用），规则写在 `SKILL.md`，脚本在 `scripts\`。

## 安装

1. 下载本仓库（GitHub Desktop 里选 Clone a repository，或网页上 Code → Download ZIP）。
2. 放到助手能找到 skill 的位置，任选其一：
   - Claude Code：`C:\Users\<你的用户名>\.claude\skills\stock-video\`（所有项目可用），或某个项目里的 `.claude\skills\stock-video\`
   - OpenCode：`C:\Users\<你的用户名>\.config\opencode\skills\stock-video\`
   - 放别处也行，在项目的 `.claude\skills\stock-video\SKILL.md` 里写一行"正本在 <路径>，先读它"指过去。
3. 之后对助手说"做个 XX 的视频"即可。

## 需要先装好

- **Windows**：画面用系统自带的微软雅黑、Bahnschrift 字体（`C:\Windows\Fonts`）。
- **Python 3.10+**，以及：
  ```
  pip install numpy pandas pillow matplotlib requests akshare edge-tts pymupdf playwright
  ```
  竖屏科普片（`build_v4.py`）还要 `playwright install chromium`。
- **ffmpeg**：要能在命令行直接运行 `ffmpeg`（加进 PATH）。
- 配音用微软 Edge 在线语音（edge-tts），需要联网。

## 可选的环境变量

| 变量 | 作用 |
|---|---|
| `STOCK_VIDEO_SKILL` | skill 目录。设了以后，复制出来的 `video.py` 不用手改 `<skill>` |

## 更新

作者改了规则或脚本会推到这里，改了什么写在 `CHANGELOG.md`。GitHub Desktop 里点 Fetch origin → Pull origin 拿最新版。

## 声明

视频内容只解读公开财报，不构成投资建议。`scripts\gsap.min.js` 是 GreenSock 的 GSAP 3.12.5，按其许可证使用。
