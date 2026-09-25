"""numpy 小脚本：顺手测一下这台机器的 numpy 算力上限。

手机上的合理预期：ARM CPU、单线程、输入 <=224 或特征维度很小。
这里故意跑 224x224 矩阵乘，是「上限参考」，不是推荐用法。
"""
import os
import platform
import sys
import time

import numpy as np

print("python  :", sys.version.split()[0])
print("numpy   :", np.__version__)
print("machine :", platform.machine(), "| cpus:", os.cpu_count())

n = 224
a = np.random.rand(n, n).astype(np.float32)
b = np.random.rand(n, n).astype(np.float32)

t0 = time.perf_counter()
c = a @ b
dt = time.perf_counter() - t0
mflops = (2 * n ** 3) / dt / 1e6 if dt else 0.0
print(f"matmul {n}x{n} float32: {dt * 1000:.1f} ms  (~{mflops:.0f} MFLOPS)")
print(f"result sum={float(c.sum()):.3f}  buffer={c.nbytes / 1024:.0f} KiB")

# 这才是手机该干的活：小特征向量
x = np.random.randn(1, 128).astype(np.float32)
t0 = time.perf_counter()
for _ in range(1000):
    y = np.tanh(x @ np.random.randn(128, 128).astype(np.float32))
dt = (time.perf_counter() - t0) / 1000 * 1e3
print(f"1x128 -> 128 dense+tanh: {dt:.3f} ms/次  out[0]={float(y[0][0]):.4f}")
print("OK")
