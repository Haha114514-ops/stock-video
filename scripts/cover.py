"""视频封面：成片之外单独出一张 1920×1080 PNG，给发布平台当封面用，不放进成片。

用法：
  python <skill>/scripts/cover.py <工程目录> <公司名> <代码> [--tag 个股拆解] [--sub "三张表 · 读懂这家公司"]
例：
  python cover.py <工程> 鱼跃医疗 002223.SZ
输出：<工程>/output/封面_<公司名>_<代码数字>.png
配色、字体与暗色拆解成片一致（取自 motion.py）。公司名过长时自动缩字号。
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motion import font, TXT, SUB, GOLD, EDGE

W, H = 1920, 1080
X0 = 150                    # 左边距
NAME_MAX_W = W - 2 * X0     # 公司名最大宽度
BG_TOP, BG_BOT = (14, 22, 44), (6, 10, 22)
GRID_COL = (22, 32, 58)


def background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    k = (y / H)[..., None]
    img = np.array(BG_TOP) * (1 - k) + np.array(BG_BOT) * k
    d = np.sqrt((x - 420) ** 2 + (y - 380) ** 2) / 900          # 左上暖光
    img += (np.clip(1 - d, 0, 1) ** 2)[..., None] * np.array([40, 34, 20])
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for gx in range(0, W, 80): dr.line([(gx, 0), (gx, H)], fill=GRID_COL)
    for gy in range(0, H, 80): dr.line([(0, gy), (W, gy)], fill=GRID_COL)
    return im


def name_font(name):
    size = 260
    while size > 120 and font(size, 'b').getlength(name) > NAME_MAX_W:
        size -= 10
    return font(size, 'b')


def make(proj, name, code, tag='个股拆解', sub='三张表 · 读懂这家公司'):
    im = background()
    nf = name_font(name)
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).text((X0, 470), name, font=nf, fill=(120, 90, 30), anchor='ls')
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    im = Image.fromarray(np.clip(np.asarray(im, np.int16) + np.asarray(glow, np.int16), 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    if tag:
        tw = font(40, 'b').getlength(tag)
        dr.rounded_rectangle((X0, 170, X0 + tw + 70, 232), 12, fill=GOLD)
        dr.text((X0 + (tw + 70) / 2, 201), tag, font=font(40, 'b'), fill=BG_TOP, anchor='mm')
    dr.text((X0, 470), name, font=nf, fill=TXT, anchor='ls')
    dr.rectangle((X0, 530, X0 + 180, 538), fill=GOLD)
    dr.text((X0, 690), code, font=font(150, 'n'), fill=GOLD, anchor='ls')
    if sub:
        dr.line([(X0, 900), (W - X0, 900)], fill=EDGE, width=2)
        dr.text((X0, 950), sub, font=font(44, 'r'), fill=SUB, anchor='lm')
    out = os.path.join(proj, 'output')
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, '封面_%s_%s.png' % (name, code.split('.')[0]))
    im.save(p)
    return p


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='出视频封面图（成片之外单独一张）')
    ap.add_argument('proj'); ap.add_argument('name'); ap.add_argument('code')
    ap.add_argument('--tag', default='个股拆解', help='左上角标签，传空串不画')
    ap.add_argument('--sub', default='三张表 · 读懂这家公司', help='底部小字，传空串不画')
    a = ap.parse_args()
    print(make(a.proj, a.name, a.code, a.tag, a.sub))
