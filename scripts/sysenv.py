# -*- coding: utf-8 -*-
"""sysenv.py —— 跟本机有关的设置集中在这里（字体、ffmpeg、并行数、skill 目录），各脚本不再各自写死。


macOS / Windows / Linux 各有一组默认候选，按顺序取第一个存在的；都可以用环境变量覆盖：
  STOCK_VIDEO_FONT_R / _B / _N   正文 / 粗体 / 数字字体，写 "路径" 或 "路径#ttc序号"
  STOCK_VIDEO_SUB_FONT           烧字幕（libass）用的字体名
  STOCK_VIDEO_FFMPEG / _FFPROBE  ffmpeg / ffprobe 可执行文件
  STOCK_VIDEO_JOBS               渲染并行进程数（默认 CPU 核数，最多 8）
  STOCK_VIDEO_SKILL              skill 目录（video.py 骨架找脚本用）
python sysenv.py 打印本机实际用到的值。"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
MAC, WIN = sys.platform == 'darwin', sys.platform.startswith('win')

# ---------- 字体 ----------
# (路径, ttc 序号)。苹方 PingFang.ttc：2 = SC Regular，8 = SC Semibold；冬青黑 / 华文黑体兜底。
_MAC_FONTS = {
    'r': [('/System/Library/Fonts/PingFang.ttc', 2), ('/System/Library/Fonts/Hiragino Sans GB.ttc', 0),
          ('/System/Library/Fonts/STHeiti Light.ttc', 0)],
    'b': [('/System/Library/Fonts/PingFang.ttc', 8), ('/System/Library/Fonts/Hiragino Sans GB.ttc', 2),
          ('/System/Library/Fonts/STHeiti Medium.ttc', 0)],
    'n': [('/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf', 0),
          ('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 0), ('/System/Library/Fonts/Helvetica.ttc', 1)],
}
_WIN = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
_WIN_FONTS = {
    'r': [(os.path.join(_WIN, 'msyh.ttc'), 0), (os.path.join(_WIN, 'simhei.ttf'), 0)],
    'b': [(os.path.join(_WIN, 'msyhbd.ttc'), 0), (os.path.join(_WIN, 'simhei.ttf'), 0)],
    'n': [(os.path.join(_WIN, 'bahnschrift.ttf'), 0), (os.path.join(_WIN, 'arialbd.ttf'), 0)],
}
_LINUX_FONTS = {
    'r': [('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 2),
          ('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc', 2),
          ('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', 0)],
    'b': [('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 2),
          ('/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc', 2),
          ('/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', 0)],
    'n': [('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 0),
          ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 0)],
}
_ORDER = [_MAC_FONTS, _WIN_FONTS, _LINUX_FONTS] if MAC else [_WIN_FONTS, _MAC_FONTS, _LINUX_FONTS] if WIN \
    else [_LINUX_FONTS, _MAC_FONTS, _WIN_FONTS]
_ENV = {'r': 'STOCK_VIDEO_FONT_R', 'b': 'STOCK_VIDEO_FONT_B', 'n': 'STOCK_VIDEO_FONT_N'}
_KIND = {'r': '正文', 'b': '粗体', 'n': '数字'}


def font_file(kind):
    """kind = r / b / n → (路径, ttc 序号)；找不到就报错并说明怎么指定"""
    v = os.environ.get(_ENV[kind])
    if v:
        p, _, i = v.partition('#')
        if not os.path.exists(p): raise FileNotFoundError(f'{_ENV[kind]} 指向的字体不存在：{p}')
        return p, int(i or 0)
    for table in _ORDER:
        for c in table[kind]:
            if os.path.exists(c[0]): return c
    raise FileNotFoundError(f'找不到{_KIND[kind]}字体（{sys.platform}）：设环境变量 {_ENV[kind]}="字体路径" 或 "路径#ttc序号"')


# libass 按字体名找；macOS 用苹方，Windows 用雅黑，Linux 用思源黑
SUB_FONT = os.environ.get('STOCK_VIDEO_SUB_FONT') or ('PingFang SC' if MAC else 'Microsoft YaHei' if WIN else 'Noto Sans CJK SC')

# ---------- ffmpeg ----------
def _tool(name):
    p = os.environ.get(f'STOCK_VIDEO_{name.upper()}') or shutil.which(name)
    if not p:
        hint = 'brew install ffmpeg' if MAC else '装好 ffmpeg 并加进 PATH'
        raise FileNotFoundError(f'找不到 {name}：{hint}，或设环境变量 STOCK_VIDEO_{name.upper()}')
    return p


class _Lazy:
    """第一次用到才去找，import 本模块不会因为没装 ffmpeg 就失败"""
    def __init__(self, name): self.name, self.v = name, None
    def __fspath__(self): return str(self)
    def __str__(self):
        if self.v is None: self.v = _tool(self.name)
        return self.v


FFMPEG, FFPROBE = _Lazy('ffmpeg'), _Lazy('ffprobe')


def ffmpeg(*args): return [str(FFMPEG), *args]
def ffprobe(*args): return [str(FFPROBE), *args]


_LIBASS = None
def has_libass():
    """ffmpeg 是否带 ass / subtitles 滤镜（Homebrew 默认的 ffmpeg 没带，竖屏片烧字幕要用）"""
    global _LIBASS
    if _LIBASS is None:
        try:
            out = subprocess.run(ffmpeg('-hide_banner', '-filters'), capture_output=True, text=True).stdout
            _LIBASS = any(l.split()[1:2] == ['ass'] for l in out.splitlines() if len(l.split()) > 1)
        except Exception:
            _LIBASS = False
    return _LIBASS


# ---------- 并行 ----------
def jobs(cap=8):
    v = os.environ.get('STOCK_VIDEO_JOBS')
    return max(1, int(v)) if v else max(1, min(cap, os.cpu_count() or 1))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for k in 'rbn':
        try: print(f'字体 {_KIND[k]}：', font_file(k))
        except Exception as e: print(f'字体 {_KIND[k]}：', e)
    print('字幕字体：', SUB_FONT)
    for t in (FFMPEG, FFPROBE):
        try: print(f'{t.name}：', str(t))
        except Exception as e: print(f'{t.name}：', e)
    print('ffmpeg 带 libass：', has_libass())
    print('并行进程：', jobs())
    print('skill 目录：', SKILL_DIR)
