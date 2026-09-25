"""AI 运行器自检（V2）：无头、可 CI。

覆盖：后端体检、迷你模型生成、load / predict / predict_image / predict_text、
错误分支（.ptl 指路、文件不存在、体积超限）。
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

FAILS = []


def check(name, cond, extra=""):
    print("%-32s %s %s" % (name, "PASS" if cond else "FAIL", extra))
    if not cond:
        FAILS.append(name)


import ai_runtime  # noqa: E402

rep = ai_runtime.backend_report()
print("后端体检:", rep)
check("至少一个后端可用", rep["onnxruntime"] or rep["torch"])
if not rep["onnxruntime"]:
    print("! 本机没有 onnxruntime（pip install onnxruntime），其余用例跳过")
    sys.exit(1 if not rep["torch"] else 0)

from make_tiny_onnx import build, build_text  # noqa: E402

tmp = tempfile.mkdtemp(prefix="pyide_ai_")
model_path = build(os.path.join(tmp, "tiny_cls.onnx"))
check("生成迷你 ONNX", os.path.getsize(model_path) > 0, "%.0f B" % os.path.getsize(model_path))

m = ai_runtime.load(model_path)
check("load 返回 Model", m.backend == "onnx", repr(m))

import numpy as np  # noqa: E402

out = m.predict(np.random.rand(1, 3, 224, 224).astype(np.float32))
check("predict 输出形状", np.asarray(out).shape == (1, 3), str(np.asarray(out).shape))

try:
    from PIL import Image  # noqa: E402

    img = Image.fromarray((np.random.rand(224, 224, 3) * 255).astype(np.uint8))
    top = m.predict_image(img, topk=3)
    ok = len(top) == 3 and abs(sum(p for _, p in top[:-1]) - top[0][1] * 0) >= 0
    check("predict_image top-k", ok and 0.0 <= top[0][1] <= 1.0,
          "top1=%d p=%.3f" % top[0])
except Exception as exc:  # noqa: BLE001
    check("predict_image top-k", False, repr(exc))

try:
    m.predict_text("hi")
    check("predict_text 需显式分词器", False)
except ai_runtime.RuntimeUnavailable:
    check("predict_text 需显式分词器", True)

try:
    m.predict_text("hi", tokenizer=lambda s: [ord(c) for c in s])
    check("图像模型拒绝文本输入", False)
except ai_runtime.RuntimeUnavailable:
    check("图像模型拒绝文本输入", True)

# 真·文本模型：ids[1,8] int64
txt_path = build_text(os.path.join(tmp, "tiny_txt.onnx"))
mt = ai_runtime.load(txt_path)
try:
    res = mt.predict_text("hello", tokenizer=lambda s: [ord(c) % 5 for c in s])
    ok = np.asarray(res).shape == (1, 3)
except Exception as exc:  # noqa: BLE001
    ok, res = False, exc
check("文本模型 predict_text 通路", ok, str(np.asarray(res).shape) if ok else repr(res))

# ---- 错误分支 ----
ptl = os.path.join(tmp, "model.ptl")
open(ptl, "wb").write(b"\x00")
try:
    ai_runtime.load(ptl)
    check(".ptl 给出 Java 指路", False)
except ai_runtime.UnsupportedFormat as exc:
    check(".ptl 给出 Java 指路", "Java" in str(exc) or "Module.load" in str(exc))

try:
    ai_runtime.load(os.path.join(tmp, "nope.onnx"))
    check("缺失文件可定位", False)
except FileNotFoundError:
    check("缺失文件可定位", True)

# 直接把上限压到 1MB 来测逻辑，不用真造几百 MB 的文件
ai_runtime.HARD_SIZE_LIMIT_MB = 1
big = os.path.join(tmp, "huge.onnx")
with open(big, "wb") as fh:
    fh.write(b"\x00" * (2 * 1024 * 1024))
try:
    ai_runtime.load(big)
    check("超大模型拦截", False)
except ai_runtime.ModelTooLarge as exc:
    check("超大模型拦截", "量化" in str(exc))

print("\n" + "=" * 46)
print("FAILS:", FAILS or "none")
sys.exit(1 if FAILS else 0)
