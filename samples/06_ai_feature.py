"""AI 运行器示例：非图像输入（V2）

不是所有端侧模型都吃图像 —— 文本分类、打分、embedding 的输入就是一条小向量。
这里演示两条最省电的用法：batch=1、维度很小、直接 predict()。

真机上把 224/8 换成你自己模型的输入尺寸。
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


def demo_feature(root):
    """图像/特征模型：喂 ndarray，不走 PIL 预处理"""
    from make_tiny_onnx import build
    path = build(os.path.join(root, "_demo_cls.onnx"))
    m = ai_runtime.load(path)
    print("特征模型:", m)
    x = np.random.rand(1, 3, 224, 224).astype(np.float32)
    out = m.predict(x)
    print("  predict -> shape", np.asarray(out).shape,
          "sum=%.4f" % float(np.asarray(out).sum()))
    return path


def demo_text(root, cls_path):
    """文本模型：ids[1,seq] 输入，tokenizer 必须自己给"""
    from make_tiny_onnx import build_text
    path = build_text(os.path.join(root, "_demo_txt.onnx"))
    m = ai_runtime.load(path)
    print("文本模型:", m)
    try:
        m.predict_text("hello")
    except ai_runtime.RuntimeUnavailable as exc:
        print("  未给分词器时的提示:", str(exc).splitlines()[1].strip())
    res = m.predict_text("hello", tokenizer=lambda s: [ord(c) % 5 for c in s])
    print("  predict_text -> shape", np.asarray(res).shape,
          "=", np.asarray(res).ravel().round(3).tolist())

    # 拿错模型喂文本：会明确告诉你该用哪个入口，而不是崩在 C++ 里
    cls = ai_runtime.load(cls_path)
    try:
        cls.predict_text("hello", tokenizer=lambda s: [ord(c) for c in s])
    except ai_runtime.RuntimeUnavailable as exc:
        print("  错用入口时的提示:", str(exc).splitlines()[1].strip())
    return path


def main():
    rep = ai_runtime.backend_report()
    print("onnxruntime:", rep["onnxruntime"], "| torch:", rep["torch"], "| abi:", rep["abi"])
    if not rep["onnxruntime"]:
        print("! 没有 onnxruntime：pip install onnxruntime（APK 需 p4a recipe）")
        return 1

    root = os.getcwd()
    made = []
    try:
        cls_path = demo_feature(root)
        made.append(cls_path)
        made.append(demo_text(root, cls_path))
    except Exception as exc:  # noqa: BLE001
        print("! 演示失败：%r" % (exc,))
        return 1
    finally:
        for p in made:
            if p and os.path.exists(p):
                os.remove(p)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
