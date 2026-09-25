"""PIL 小脚本：生成渐变图 -> 缩放 -> 保存到当前目录（应用私有目录，无需权限）。

验证三件事：Pillow 可用、当前目录可写、numpy<->PIL 互转正常。
"""
import os

import numpy as np
from PIL import Image

w, h = 512, 512
yy, xx = np.mgrid[0:h, 0:w]
img = np.zeros((h, w, 3), dtype=np.uint8)
img[..., 0] = (xx * 255 // w).astype(np.uint8)      # R 横向渐变
img[..., 1] = (yy * 255 // h).astype(np.uint8)      # G 纵向渐变
img[..., 2] = ((xx + yy) * 255 // (w + h)).astype(np.uint8)

im = Image.fromarray(img)
small = im.resize((224, 224), Image.BILINEAR)       # 端侧输入常见尺寸
out = os.path.join(os.getcwd(), "thumb_224.jpg")
small.save(out, quality=85)

print("cwd      :", os.getcwd())
print("writable :", os.access(os.getcwd(), os.W_OK))
print("saved    :", out, os.path.getsize(out), "bytes")
print("size     :", small.size, "mode:", small.mode)
print("OK")
