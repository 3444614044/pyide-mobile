"""AI 运行器示例：图像分类（V2）

用法：
    1) 把 model.onnx 放进当前目录（或 models/ 子目录）
    2) 在 IDE 里运行本文件，输出面板会打印 top-k

没有模型也能跑：会自动造一个迷你 ONNX 演示整条通路（前提是装了 onnxruntime）。
"""
import os
import sys

import numpy as np

# 直接跑本文件时 sys.path[0] 是 samples/，把工程根目录补进来才能 import ai_runtime
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ai_runtime  # noqa: E402

MODEL_NAMES = ("model.onnx", "model_int8.onnx")
MODEL_DIRS = (".", "models")
MAX_MB = 60


def find_model():
    for d in MODEL_DIRS:
        for n in MODEL_NAMES:
            p = os.path.join(os.getcwd(), d, n)
            if os.path.isfile(p):
                return p
    return None


def main():
    print("== 后端体检 ==")
    rep = ai_runtime.backend_report()
    for k, v in rep.items():
        print("  %-12s %s" % (k, v))
    if not rep["onnxruntime"] and not rep["torch"]:
        print("\n! 两个后端都没有：")
        print("  Pydroid 3 / 桌面：pip install onnxruntime")
        print("  打进 APK：需要 p4a 的 onnxruntime recipe，纯 pip 装不进去")
        return 1

    path = find_model()
    demo = False
    if path is None:
        print("\n没找到 model.onnx，先造个迷你模型演示通路（不是真分类网络）")
        try:
            from make_tiny_onnx import build
            path = build(os.path.join(os.getcwd(), "_demo_tiny.onnx"))
            demo = True
        except Exception as exc:  # noqa: BLE001
            print("! 造不出来（%r）。装 onnx 后重试：pip install onnx" % (exc,))
            return 1

    m = ai_runtime.load(path)
    print("\n== 模型 ==")
    print(" ", m)

    # 造一张 224 的假图（真机上换成 Image.open(你的照片)）
    from PIL import Image
    arr = (np.random.rand(224, 224, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)

    top = m.predict_image(img, topk=3)
    print("\n== predict_image ==")
    for idx, prob in top:
        print("  class %-4d %.4f" % (idx, prob))

    if m.size_mb() > MAX_MB:
        print("\n! %.1f MB 偏大：跑 tools/quantize_onnx.py 做 int8 动态量化" % m.size_mb())

    if demo and os.path.exists(path):
        os.remove(path)
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
